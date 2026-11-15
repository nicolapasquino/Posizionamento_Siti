"""Funzioni comuni della web app: lettura dei punti, interrogazione del Catasto, mappa, esportazione.

Stessa logica di mappa_punti_v1.5.ipynb: le funzioni sono copiate identiche nel notebook,
quindi ogni modifica va riportata in entrambi (aggiornando le versioni).
Dati catastali: © Agenzia delle Entrate – licenza CC BY 4.0.
"""
from __future__ import annotations

import html
import io
import math
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import folium
import pandas as pd
import requests
from branca.element import MacroElement, Template
from folium.plugins import Fullscreen, MeasureControl
from shapely.geometry import MultiPolygon, Point, Polygon

WMS_URL = "https://wms.cartografia.agenziaentrate.gov.it/inspire/wms/ows01.php"
ATTR_CATASTO = "Cartografia catastale © Agenzia delle Entrate (CC BY 4.0)"
MAX_PUNTI = 1000          # limite per file, per non sovraccaricare il servizio pubblico
PARALLELI = 4             # richieste contemporanee al Catasto
WFS_URL = "https://wfs.cartografia.agenziaentrate.gov.it/inspire/wfs/owfs01.php"
MAX_RAGGIO_CERCHIO = 50000     # metri: raggio massimo del cerchio sulla mappa
MAX_RAGGIO_PARTICELLE = 500    # metri: oltre, troppe particelle da scaricare e disegnare

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


def leggi_punti(dati: bytes, nome_file: str, foglio_excel=0) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Legge un CSV (separatore ; , o tab) o un Excel. Restituisce (punti validi, righe scartate, avvisi).

    `foglio_excel`: foglio di lavoro da leggere (indice o nome), solo per i file Excel.
    """
    if nome_file.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(dati), sheet_name=foglio_excel)
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
# Cerchio intorno a un punto: particelle che vi cadono (servizio WFS del Catasto)
# ---------------------------------------------------------------------------
_CRS_WFS = "urn:ogc:def:crs:EPSG::6706"     # RDN2008 (ETRF2000), ordine assi lat,lon
_GML = "{http://www.opengis.net/gml/3.2}"
_CP = "{http://mapserver.gis.umn.edu/mapserver}"
_NON_PARTICELLE = re.compile(r"^(STRADA|ACQUA)", re.IGNORECASE)   # strade e acque non sono particelle
COLONNE_PARTICELLE = ["comune_belfiore", "foglio", "allegato", "sviluppo", "particella", "rif_catastale",
                      "area_m2", "area_nel_cerchio_m2", "quota_nel_cerchio_pct", "interamente_dentro",
                      "distanza_dal_centro_m"]


def _piano_locale(lat0, lon0):
    """Coordinate piane in metri (x verso est, y verso nord) con origine in (lat0, lon0).

    Usa i raggi di curvatura dell'ellissoide GRS80 nell'origine: entro 1 km l'errore
    resta sotto 0,2 m, molto meno dell'accuratezza della cartografia catastale.
    """
    a, e2 = 6378137.0, 0.00669438002290
    s = math.sin(math.radians(lat0))
    w = math.sqrt(1 - e2 * s * s)
    kx = math.radians(1) * a / w * math.cos(math.radians(lat0))   # metri per grado di longitudine
    ky = math.radians(1) * a * (1 - e2) / w ** 3                   # metri per grado di latitudine
    return kx, ky


def _wfs_particelle(lat, lon, raggio_m, pagina=5000, tentativi=10):
    """Particelle nel quadrato circoscritto al cerchio: lista di (riferimento, etichetta, poligoni).

    Ogni poligono è una lista di anelli (esterno e buchi) di coppie (lat, lon). Scarica a pagine
    e, come per il WMS, riconosce le risposte di errore del server e riprova.
    """
    kx, ky = _piano_locale(lat, lon)
    dlat, dlon = 1.02 * raggio_m / ky, 1.02 * raggio_m / kx
    trovate, inizio = {}, 0
    while True:
        params = dict(SERVICE="WFS", VERSION="2.0.0", REQUEST="GetFeature", TYPENAMES="CP:CadastralParcel",
                      SRSNAME=_CRS_WFS, COUNT=pagina, STARTINDEX=inizio,
                      BBOX=f"{lat-dlat},{lon-dlon},{lat+dlat},{lon+dlon},{_CRS_WFS}")
        for _ in range(tentativi):
            r = requests.get(WFS_URL, params=params, timeout=120)
            r.raise_for_status()
            if "ExceptionReport" not in r.text[:2000]:
                break
            time.sleep(1)
        else:
            raise RuntimeError(f"il servizio WFS del Catasto ha risposto con errore a tutti i {tentativi} tentativi")
        radice = ET.fromstring(r.content)
        totale = radice.get("numberMatched", "unknown")   # "unknown" quando il server non lo calcola
        membri = 0
        for p in radice.iter(f"{_CP}CadastralParcel"):
            membri += 1
            poligoni = []
            for poly in p.iter(f"{_GML}Polygon"):
                anelli = []
                for pos in poly.iter(f"{_GML}posList"):
                    v = [float(x) for x in pos.text.split()]
                    anelli.append(list(zip(v[0::2], v[1::2])))
                poligoni.append(anelli)
            rif = p.findtext(f"{_CP}NATIONALCADASTRALREFERENCE")
            trovate[rif] = (rif, p.findtext(f"{_CP}LABEL"), poligoni)
        inizio += membri
        if membri == 0 or (totale.isdigit() and inizio >= int(totale)):
            return list(trovate.values())


def particelle_nel_cerchio(lat, lon, raggio_m):
    """Particelle catastali che cadono, anche solo in parte, nel cerchio di centro (lat, lon).

    Restituisce (tabella, geojson): la tabella ha una riga per particella con aree e distanze
    calcolate sulla geometria della mappa catastale (non sono le superfici catastali ufficiali);
    il GeoJSON serve per disegnarle sulla mappa. Strade e acque sono escluse.
    """
    if raggio_m > MAX_RAGGIO_PARTICELLE:
        raise ValueError(f"raggio troppo grande per cercare le particelle (massimo {MAX_RAGGIO_PARTICELLE} m)")
    kx, ky = _piano_locale(lat, lon)

    def piano(anello):
        return [((lo - lon) * kx, (la - lat) * ky) for la, lo in anello]

    centro = Point(0, 0)
    cerchio = centro.buffer(raggio_m, 64)
    righe, feats = [], []
    for rif, etichetta, poligoni in _wfs_particelle(lat, lon, raggio_m):
        if not poligoni or _NON_PARTICELLE.match(etichetta or ""):
            continue
        geom = MultiPolygon([Polygon(piano(p[0]), [piano(b) for b in p[1:]]) for p in poligoni])
        if not geom.is_valid:
            geom = geom.buffer(0)
        if geom.is_empty or not geom.intersects(cerchio):
            continue
        area, dentro = geom.area, geom.intersection(cerchio).area
        riga = dict(comune_belfiore=None, foglio=None, allegato=None, sviluppo=None, particella=etichetta,
                    rif_catastale=rif, area_m2=round(area, 1), area_nel_cerchio_m2=round(dentro, 1),
                    quota_nel_cerchio_pct=round(100 * dentro / area, 1) if area else None,
                    interamente_dentro="sì" if cerchio.contains(geom) else "no",
                    distanza_dal_centro_m=round(geom.distance(centro), 1))
        m = _RIF.match(rif or "")
        if m:
            riga.update(comune_belfiore=m["comune"], foglio=int(m["foglio"]),
                        allegato=m["allegato"], sviluppo=m["sviluppo"])
        righe.append(riga)
        feats.append({"type": "Feature",
                      "geometry": {"type": "MultiPolygon",
                                   "coordinates": [[[[lo, la] for la, lo in anello] for anello in p] for p in poligoni]},
                      "properties": {"particella": etichetta, "foglio": riga["foglio"], "rif_catastale": rif,
                                     "quota_nel_cerchio_pct": riga["quota_nel_cerchio_pct"],
                                     "interamente_dentro": riga["interamente_dentro"]}})
    tabella = pd.DataFrame(righe, columns=COLONNE_PARTICELLE)
    if len(tabella):
        ordine = pd.to_numeric(tabella["particella"], errors="coerce")
        tabella = (tabella.assign(_n=ordine).sort_values(["foglio", "_n", "particella"], na_position="last")
                   .drop(columns="_n").reset_index(drop=True))
    return tabella, {"type": "FeatureCollection", "features": feats}


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


class AdattamentiMobile(MacroElement):
    """Rende la mappa comoda su smartphone e tablet; sul computer non cambia nulla.

    1. Sui dispositivi touch, quando la mappa è incorporata in una pagina (web app, notebook),
       un dito scorre la pagina e due dita spostano la mappa (plugin leaflet-gesture-handling,
       messaggi già in italiano). A schermo intero, o nella mappa HTML aperta da sola, un dito
       sposta la mappa come di consueto.
    2. Sugli schermi stretti, se le attribuzioni vanno su più righe e coprirebbero la scala
       grafica, la scala viene alzata sopra di esse.
    """
    _template = Template("""
    {% macro header(this, kwargs) %}
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet-gesture-handling@1.2.2/dist/leaflet-gesture-handling.min.css"/>
        <script src="https://cdn.jsdelivr.net/npm/leaflet-gesture-handling@1.2.2/dist/leaflet-gesture-handling.min.js"></script>
    {% endmacro %}
    {% macro script(this, kwargs) %}
    (function () {
        var mappa = {{ this._parent.get_name() }};
        var touch = L.Browser.mobile || (window.matchMedia && window.matchMedia("(pointer: coarse)").matches);
        var incorporata = window.self !== window.top;
        function gesti(schermoIntero) {
            if (!mappa.gestureHandling) { return; }
            if (touch && incorporata && !schermoIntero) { mappa.gestureHandling.enable(); }
            else { mappa.gestureHandling.disable(); }
        }
        gesti(false);
        mappa.on("enterFullscreen", function () { gesti(true); });
        mappa.on("exitFullscreen", function () { gesti(false); });

        function sistemaScala() {
            var att = mappa.attributionControl && mappa.attributionControl.getContainer();
            var sx = mappa.getContainer().querySelector(".leaflet-bottom.leaflet-left");
            if (!att || !sx) { return; }
            sx.style.bottom = "";
            var a = att.getBoundingClientRect(), s = sx.getBoundingClientRect();
            if (a.left < s.right && a.top < s.bottom) { sx.style.bottom = a.height + "px"; }
        }
        mappa.whenReady(sistemaScala);
        mappa.on("resize layeradd layerremove", function () { setTimeout(sistemaScala, 0); });
    })();
    {% endmacro %}
    """)

    def __init__(self):
        super().__init__()
        self._name = "AdattamentiMobile"


def _wms_catasto(nome, layers, opacity=1.0, min_zoom=0, show=True):
    return folium.WmsTileLayer(
        url=WMS_URL, layers=layers, fmt="image/png", transparent=True, version="1.1.1",
        name=nome, overlay=True, control=True, show=show, opacity=opacity,
        min_zoom=min_zoom, max_zoom=22, attr=ATTR_CATASTO)


def _testo(x) -> str:
    """Valore di cella come testo ('' se vuoto o NaN; 7.0 -> '7')."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def _numero(x, decimali=0) -> str:
    """Numero all'italiana: 31415.9 -> '31.416', con decimali la virgola."""
    return f"{x:,.{decimali}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def _aggiungi_cerchio(m, cerchio):
    """Disegna il cerchio e, se presenti, le particelle che vi cadono (sopra il cerchio, così
    restano cliccabili). `cerchio`: dict con lat, lon, raggio (m), nome e, facoltativo, particelle
    (GeoJSON di particelle_nel_cerchio)."""
    lat, lon, raggio = cerchio["lat"], cerchio["lon"], cerchio["raggio"]
    area = math.pi * raggio ** 2
    righe = [f"Cerchio di <b>{_numero(raggio, 0 if float(raggio).is_integer() else 1)} m</b> "
             f"intorno a <b>{html.escape(str(cerchio['nome']))}</b>",
             f"centro: lat {lat:.6f}, lon {lon:.6f}",
             f"area: {_numero(area)} m² ({_numero(area / 1e4, 2)} ha)"]
    particelle = cerchio.get("particelle")
    if particelle is not None:
        feats = particelle["features"]
        intere = sum(1 for f in feats if f["properties"]["interamente_dentro"] == "sì")
        righe.append(f"{len(feats)} particelle nel cerchio, {intere} per intero")
    gruppo = folium.FeatureGroup(name=f"Cerchio di {_numero(raggio)} m").add_to(m)
    folium.Circle([lat, lon], radius=raggio, color="#1f6feb", weight=2.5, fill=True, fill_opacity=0.08,
                  popup=folium.Popup("<br>".join(righe), max_width=320)).add_to(gruppo)
    folium.CircleMarker([lat, lon], radius=3, color="#1f6feb", fill=True, fill_opacity=1).add_to(gruppo)
    if particelle is not None and particelle["features"]:
        folium.GeoJson(
            particelle, name="Particelle nel cerchio",
            style_function=lambda f: {"color": "#b03a2e", "weight": 1.2, "fillColor": "#e74c3c",
                                      "fillOpacity": 0.4 if f["properties"]["interamente_dentro"] == "sì" else 0.15},
            highlight_function=lambda f: {"weight": 3, "fillOpacity": 0.6},
            tooltip=folium.GeoJsonTooltip(["particella", "foglio", "quota_nel_cerchio_pct"],
                                          aliases=["Particella", "Foglio", "% nel cerchio"]),
        ).add_to(m)
    kx, ky = _piano_locale(lat, lon)
    m.fit_bounds([[lat - raggio / ky, lon - raggio / kx], [lat + raggio / ky, lon + raggio / kx]], padding=(20, 20))


def crea_mappa(df: pd.DataFrame, cerchio=None) -> folium.Map:
    """Mappa OSM/satellite con fogli e particelle catastali (fogli da zoom 12, particelle da 17).

    Fabbricati (da zoom 17) e strade e acque (da zoom 14) del Catasto sono disponibili
    nel pannello dei layer, spenti all'apertura. Con `cerchio` (vedi _aggiungi_cerchio) disegna
    anche il cerchio intorno a un punto e la mappa si centra su di esso.
    """
    m = folium.Map(location=[df["lat"].mean(), df["lon"].mean()], zoom_start=15,
                   tiles=None, control_scale=True, max_zoom=22)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", max_zoom=22, max_native_zoom=19).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satellite (Esri)", max_zoom=22, max_native_zoom=19, show=False,
    ).add_to(m)
    for lyr in (_wms_catasto("Catasto – fogli", "CP.CadastralZoning", min_zoom=12),
                _wms_catasto("Catasto – particelle", "CP.CadastralParcel,codice_plla", opacity=0.8, min_zoom=17),
                _wms_catasto("Catasto – fabbricati", "fabbricati", opacity=0.6, min_zoom=17, show=False),
                _wms_catasto("Catasto – strade e acque", "strade,acque", opacity=0.6, min_zoom=14, show=False)):
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

    if cerchio:
        _aggiungi_cerchio(m, cerchio)
    elif len(df) > 1:
        m.fit_bounds([[df["lat"].min(), df["lon"].min()], [df["lat"].max(), df["lon"].max()]], padding=(30, 30))
    folium.LayerControl(collapsed=False).add_to(m)
    MeasureControl(primary_length_unit="meters", primary_area_unit="sqmeters").add_to(m)
    Fullscreen().add_to(m)
    m.add_child(AdattamentiMobile())
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


def particelle_da_esportare(tabella: pd.DataFrame, nome, lat, lon, raggio_m) -> pd.DataFrame:
    """Tabella delle particelle nel cerchio con, in testa, centro e raggio del cerchio."""
    out = tabella.copy()
    for i, (colonna, valore) in enumerate((("centro", nome), ("lat_centro", lat), ("lon_centro", lon),
                                           ("raggio_m", raggio_m))):
        out.insert(i, colonna, valore)
    return out


def csv_bytes(df: pd.DataFrame) -> bytes:
    """CSV per Excel in italiano: separatore ';', virgola decimale, UTF-8 con BOM."""
    return _per_esportare(df).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
