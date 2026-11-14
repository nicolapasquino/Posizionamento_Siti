"""Web app: punti da CSV/Excel su mappa OpenStreetMap + Catasto, con comune, foglio e particella.

Avvio locale:   streamlit run app.py
"""
import hashlib
from pathlib import Path

import streamlit as st

import catasto_punti as cp

VERSIONE = "1.2.0"

st.set_page_config(page_title="Punti e Catasto", page_icon="🗺️", layout="wide")
st.title("Punti su mappa e Catasto")
st.markdown(
    "Carica un file **CSV** o **Excel** con le colonne **`nome`**, **`lat`**, **`lon`** "
    "(gradi decimali, WGS84). Il CSV può usare `;` o `,` come separatore e la virgola come "
    "separatore decimale. L'app mostra i punti sulla mappa e, per ciascuno, ricava dal Catasto "
    "**comune (codice Belfiore), foglio e particella**."
)

with st.sidebar:
    st.header("Informazioni")
    st.markdown(
        "- Le particelle compaiono sulla mappa da **zoom 17**, i numeri da **zoom 18**.\n"
        "- Dal pannello dei layer si accendono anche i **fabbricati** (da zoom 17) e le **strade e acque** "
        "(da zoom 14) del Catasto.\n"
        "- Il servizio non copre le province di Trento e Bolzano (catasto tavolare).\n"
        "- Le coordinate vengono inviate al servizio WMS dell'Agenzia delle Entrate.\n"
        f"- Massimo {cp.MAX_PUNTI} punti per file.\n\n"
        "Dati catastali: © Agenzia delle Entrate, licenza CC BY 4.0. "
        "Il risultato è indicativo e non sostituisce una visura catastale."
    )
    st.caption(f"Versione {VERSIONE}")

file = st.file_uploader("File dei punti", type=["csv", "txt", "xlsx", "xls"])
interroga = st.checkbox("Ricava comune, foglio e particella dal Catasto", value=True)
if file is None:
    st.stop()

dati = file.getvalue()
try:
    punti, scartati, avvisi = cp.leggi_punti(dati, file.name)
except Exception as e:  # file illeggibile o colonne mancanti
    st.error(f"Impossibile leggere il file: {e}")
    st.stop()

for a in avvisi:
    st.warning(a)
if len(scartati):
    st.warning(f"{len(scartati)} righe senza coordinate valide sono state scartate:")
    st.dataframe(scartati, hide_index=True)
if punti.empty:
    st.error("Nessun punto con coordinate valide.")
    st.stop()
if len(punti) > cp.MAX_PUNTI:
    st.error(f"Il file contiene {len(punti)} punti: il massimo è {cp.MAX_PUNTI}. Dividilo in più file.")
    st.stop()

# --- elaborazione (una sola volta per file e opzione; i pulsanti di download non la ripetono) ---
chiave = (hashlib.sha1(dati).hexdigest(), interroga)
if st.session_state.get("chiave") != chiave:
    st.info(f"{len(punti)} punti letti.")
    if not st.button("Elabora", type="primary"):
        st.stop()
    risultato = punti
    if interroga:
        barra = st.progress(0.0, text="Interrogazione del Catasto…")
        risultato = cp.arricchisci(
            punti, avanzamento=lambda i, n: barra.progress(i / n, text=f"Interrogazione del Catasto: {i} di {n}"))
        barra.empty()
    st.session_state.update(chiave=chiave, risultato=risultato)
    st.rerun()  # ridisegna la pagina senza il pulsante Elabora

risultato = st.session_state["risultato"]

errori = cp.con_errore(risultato)
if errori.any():
    st.warning(f"Per {int(errori.sum())} punti il server del Catasto non ha risposto correttamente.")
    if st.button("Riprova questi punti"):
        barra = st.progress(0.0, text="Nuovo tentativo…")
        risultato = cp.arricchisci(
            risultato, righe=errori,
            avanzamento=lambda i, n: barra.progress(i / n, text=f"Nuovo tentativo: {i} di {n}"))
        st.session_state["risultato"] = risultato
        st.rerun()

# --- risultati ---
st.subheader(f"Risultati ({len(risultato)} punti)")
# prima le colonne principali: sullo smartphone si vedono senza scorrere la tabella di lato
prime = [c for c in ("nome", "foglio", "particella", "note") if c in risultato.columns]
st.dataframe(risultato, hide_index=True, width="stretch",
             column_order=prime + [c for c in risultato.columns if c not in prime])

html_mappa = cp.crea_mappa(risultato).get_root().render()
if hasattr(st, "iframe"):
    st.iframe(html_mappa, height=620)
else:  # versioni di Streamlit precedenti a st.iframe
    import streamlit.components.v1 as components
    components.html(html_mappa, height=620)

base = Path(file.name).stem
c1, c2, c3 = st.columns(3)
c1.download_button("Scarica Excel", cp.excel_bytes(risultato), f"{base}_con_catasto.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   width="stretch")
c2.download_button("Scarica CSV", cp.csv_bytes(risultato), f"{base}_con_catasto.csv",
                   mime="text/csv", width="stretch")
c3.download_button("Scarica mappa (HTML)", html_mappa.encode("utf-8"), f"{base}_mappa.html",
                   mime="text/html", width="stretch")
st.caption("La mappa HTML si apre con qualsiasi browser, senza installare nulla.")
