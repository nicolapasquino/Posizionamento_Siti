"""Funzioni comuni della web app: lettura dei punti, interrogazione del Catasto, mappa, esportazione.

Stessa logica di mappa_punti_v1.1.ipynb.
Dati catastali: © Agenzia delle Entrate – licenza CC BY 4.0.
"""
from __future__ import annotations

import html
import io
import re
import time
from concurrent.futures import ThreadPoolExecutor

import folium
import pandas as pd
import requests
from branca.element import MacroElement, Template
from folium.plugins import Fullscreen, MeasureControl

WMS_URL = "https://wms.cartografia.agenziaentrate.gov.it/inspire/wms/ows01.php"
ATTR_CATASTO = "Cartografia catastale © Agenzia delle Entrate (CC BY 4.0)"
MAX_PUNTI = 1000          # limite per file, per non sovraccaricare il servizio pubblico
PARALLELI = 4             # richieste contemporanee al Catasto

# nomi di colonna accettati (dopo minuscole e rimozione spazi)
ALIAS = {
    "nome": ("nome", "name", "descrizione", "punto", "id"),
    "lat": ("lat", "latitudine", "latitude"),
    "lon": ("lon", "lng", "long", "longitudine", "longitude"),
}
COLONNE_CATASTO = ["comune_belfiore", "foglio", "allegato", "sviluppo", "particella", "rif_catastale", "note"]


# ---------------------------------------------------------------------------
# Lettura
# ---------------------------------------------------------------------------
def _leggi_csv(dati: bytes) -> pd.DataFrame:
    for codifica in ("utf-8-sig", "cp1252"):          # cp1252: CSV salvati da Excel italiano
        try:
            testo = dati.decode(codifica)
            break
        except UnicodeDecodeError:
            continue
    intestazione = testo.splitlines()[0] if testo.strip() else ""
    sep = ";" if ";" in intestazione else "\t" if "\t" in intestazione else ","
    return pd.read_csv(io.StringIO(testo), sep=sep, dtype=str, skipinitialspace=True)


def leggi_punti(dati: bytes, nome_file: str) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Legge un CSV (separatore ; , o tab) o un Excel. Restituisce (punti validi, righe scartate, avvisi)."""
    if nome_file.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(dati))
    else:
        df = _leggi_csv(dati)
    df.columns = [str(c).strip().lower() for c in df.columns]

    rinomina = {}
    for std, alias in ALIAS.items():
        trovata = next((c for c in df.columns if c in alias), None)
        if trovata is not None and std not in df.columns:
            rinomina[trovata] = std
    df = df.rename(columns=rinomina)

    mancanti = [c for c in ("lat", "lon") if c not in df.columns]
    if mancanti:
        raise ValueError(f"Colonne mancanti: {', '.join(mancanti)}. Colonne trovate: {', '.join(df.columns)}")

    avvisi = []
    if "nome" not in df.columns:
        df.insert(0, "nome", [f"P{i + 1}" for i in range(len(df))])
        avvisi.append("Colonna 'nome' assente: i punti sono stati numerati P1, P2, …")
    df["nome"] = df["nome"].fillna("").astype(str).str.strip()

    # accetta anche la virgola come separatore decimale (es. "40,85")
    for c in ("lat", "lon"):
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ".").str.strip(), errors="coerce")
    scartati = df[df[["lat", "lon"]].isna().any(axis=1)]
    df = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)

    fuori = ~(df["lat"].between(35, 48) & df["lon"].between(6, 19))
    if fuori.any():
        invertiti = df["lat"].between(6, 19) & df["lon"].between(35, 48)
        if invertiti[fuori].all():
            avvisi.append("Le colonne lat e lon sembrano invertite (la latitudine in Italia è tra 35 e 48). "
                          "Controlla il file.")
        else:
            avvisi.append(f"{int(fuori.sum())} punti sono fuori dall'Italia: per questi il Catasto non darà risultati.")
    return df, scartati, avvisi


# ---------------------------------------------------------------------------
# Interrogazione del Catasto (WMS GetFeatureInfo)
# ---------------------------------------------------------------------------
_RIGA = re.compile(r"<th[^>]*>([^<]+)</th>\s*<td>([^<]*)</td>")
_RIF = re.compile(r"^(?P<comune>[A-Z]\d{3})_(?P<foglio>\d{4})(?P<allegato>\w)(?P<sviluppo>\w)(?:\.(?P<particella>.+))?$")


def _feature_info(lat, lon, layer, d=0.0002, tentativi=10):
    """Interroga il WMS catastale nel punto (lat, lon). EPSG:4258 in WMS 1.3.0 => BBOX lat,lon.

    Il server a volte risponde con una ServiceException (con HTTP 200): va riconosciuta e si
    riprova. requests.get apre una connessione nuova a ogni chiamata, quindi ogni tentativo
    può arrivare a una macchina diversa del server.
    """
    params = dict(SERVICE="WMS", VERSION="1.3.0", REQUEST="GetFeatureInfo",
                  LAYERS=layer, QUERY_LAYERS=layer, STYLES="", CRS="EPSG:4258",
                  BBOX=f"{lat-d},{lon-d},{lat+d},{lon+d}", WIDTH=101, HEIGHT=101, I=50, J=50,
                  INFO_FORMAT="text/html", FEATURE_COUNT=1)
    for _ in range(tentativi):
        r = requests.get(WMS_URL, params=params, timeout=30)
        r.raise_for_status()
        if "ServiceException" not in r.text:
            return dict(_RIGA.findall(r.text))
        time.sleep(1)
    raise RuntimeError(f"il server catastale ha risposto con errore a tutti i {tentativi} tentativi")


def catasto(lat, lon):
    out = dict(comune_belfiore=None, foglio=None, allegato=None, sviluppo=None,
               particella=None, rif_catastale=None, note=None)
    try:
        part = _feature_info(lat, lon, "CP.CadastralParcel")
        rif = part.get("NationalCadastralReference")
        if not rif:  # punto su strada/acqua: niente particella, provo almeno il foglio
            zona = _feature_info(lat, lon, "CP.CadastralZoning")
            rif = zona.get("NationalCadastralZoningReference")
            out["note"] = "nessuna particella (strada, acque o area non censita)" if rif else "fuori copertura"
        if rif:
            out["rif_catastale"] = rif
            m = _RIF.match(rif)
            if m:
                g = m.groupdict()
                out.update(comune_belfiore=g["comune"], foglio=int(g["foglio"]),
                           allegato=g["allegato"], sviluppo=g["sviluppo"], particella=g["particella"])
    except Exception as e:
        out["note"] = f"errore: {e}"
    return out


def con_errore(df: pd.DataFrame) -> pd.Series:
    """Righe la cui interrogazione è fallita (da riprovare)."""
    if "note" not in df.columns:
        return pd.Series(False, index=df.index)
    return df["note"].fillna("").astype(str).str.startswith("errore")


def arricchisci(df: pd.DataFrame, righe=None, avanzamento=None) -> pd.DataFrame:
    """Aggiunge le colonne catastali. `righe`: maschera delle righe da (ri)calcolare (default: tutte).
    `avanzamento(fatti, totale)` viene chiamata dopo ogni punto."""
    df = df.copy()
    for c in COLONNE_CATASTO:
        if c not in df.columns:
            df[c] = None
    df[COLONNE_CATASTO] = df[COLONNE_CATASTO].astype(object)
    indici = df.index[pd.Series(righe, index=df.index).to_numpy()] if righe is not None else df.index
    with ThreadPoolExecutor(PARALLELI) as ex:
        futuri = {i: ex.submit(catasto, df.at[i, "lat"], df.at[i, "lon"]) for i in indici}
        for n, (i, f) in enumerate(futuri.items(), start=1):
            for c, v in f.result().items():
                df.at[i, c] = v
            if avanzamento:
                avanzamento(n, len(futuri))
    return df


# ---------------------------------------------------------------------------
# Mappa
# ---------------------------------------------------------------------------
class CrsWms4258(MacroElement):
    """Fa chiedere a un L.tileLayer.wms le immagini in EPSG:4258 (gradi).

    Il WMS catastale non offre EPSG:3857 (OpenStreetMap). Usa solo l'API pubblica di Leaflet:
    l'opzione `crs` viene letta quando il layer entra nella mappa, quindi se folium lo ha già
    aggiunto lo si toglie e lo si rimette. Il layer va creato con version="1.1.1" (BBOX lon,lat).
    """
    _template = Template("""
    {% macro script(this, kwargs) %}
    (function () {
        var lyr = {{ this.layer.get_name() }}, mappa = {{ this._parent.get_name() }};
        lyr.options.crs = L.extend({}, L.CRS.EPSG4326, {code: "EPSG:4258"});
        if (mappa.hasLayer(lyr)) { mappa.removeLayer(lyr); mappa.addLayer(lyr); }
    })();
    {% endmacro %}
    """)

    def __init__(self, layer):
        super().__init__()
        self._name = "CrsWms4258"
        self.layer = layer


def _wms_catasto(nome, layers, opacity=1.0, min_zoom=0):
    return folium.WmsTileLayer(
        url=WMS_URL, layers=layers, fmt="image/png", transparent=True, version="1.1.1",
        name=nome, overlay=True, control=True, show=True, opacity=opacity,
        min_zoom=min_zoom, max_zoom=22, attr=ATTR_CATASTO)


def _testo(x) -> str:
    """Valore di cella come testo ('' se vuoto o NaN; 7.0 -> '7')."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def crea_mappa(df: pd.DataFrame) -> folium.Map:
    """Mappa OSM/satellite con fogli e particelle catastali (fogli da zoom 12, particelle da 17)."""
    m = folium.Map(location=[df["lat"].mean(), df["lon"].mean()], zoom_start=15,
                   tiles=None, control_scale=True, max_zoom=22)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", max_zoom=22, max_native_zoom=19).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satellite (Esri)", max_zoom=22, max_native_zoom=19, show=False,
    ).add_to(m)
    for lyr in (_wms_catasto("Catasto – fogli", "CP.CadastralZoning", min_zoom=12),
                _wms_catasto("Catasto – particelle", "CP.CadastralParcel,codice_plla", opacity=0.8, min_zoom=17)):
        lyr.add_to(m)
        m.add_child(CrsWms4258(lyr))

    punti = folium.FeatureGroup(name="Punti").add_to(m)
    con_catasto = "rif_catastale" in df.columns
    for r in df.itertuples():
        nome = html.escape(str(r.nome))
        righe = [f"<b>{nome}</b>", f"lat {r.lat:.6f}, lon {r.lon:.6f}"]
        if con_catasto:
            rif, part, note = (_testo(x) for x in (r.rif_catastale, r.particella, r.note))
            if rif:
                righe.append(f"Comune <b>{html.escape(_testo(r.comune_belfiore))}</b> · "
                             f"Foglio <b>{html.escape(_testo(r.foglio))}</b>"
                             + (f" · Particella <b>{html.escape(part)}</b>" if part else ""))
            if note:
                righe.append(f"<i>{html.escape(note)}</i>")
        folium.Marker(
            [r.lat, r.lon], tooltip=nome,
            popup=folium.Popup("<br>".join(righe), max_width=320),
            icon=folium.Icon(color="red", icon="map-marker", prefix="fa"),
        ).add_to(punti)

    if len(df) > 1:
        m.fit_bounds([[df["lat"].min(), df["lon"].min()], [df["lat"].max(), df["lon"].max()]], padding=(30, 30))
    folium.LayerControl(collapsed=False).add_to(m)
    MeasureControl(primary_length_unit="meters", primary_area_unit="sqmeters").add_to(m)
    Fullscreen().add_to(m)
    return m


# ---------------------------------------------------------------------------
# Esportazione
# ---------------------------------------------------------------------------
def _per_esportare(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "foglio" in out.columns:
        out["foglio"] = pd.to_numeric(out["foglio"], errors="coerce").astype("Int64")
    return out


def excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    _per_esportare(df).to_excel(buf, index=False)
    return buf.getvalue()


def csv_bytes(df: pd.DataFrame) -> bytes:
    """CSV per Excel in italiano: separatore ';', virgola decimale, UTF-8 con BOM."""
    return _per_esportare(df).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
