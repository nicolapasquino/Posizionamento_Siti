# Punti su mappa e Catasto – web app (versione 1.0)

Web app che riceve un file **CSV o Excel** con le colonne `nome`, `lat`, `lon` (gradi decimali, WGS84), mostra i punti su una mappa OpenStreetMap con i fogli e le particelle catastali e, per ogni punto, ricava **comune (codice Belfiore), foglio e particella**. I risultati si scaricano come Excel, CSV o mappa HTML.

Usa la stessa logica di `mappa_punti_v1.1.ipynb`. Chi la usa ha bisogno solo di un browser.

## Contenuto

| file | a cosa serve |
|---|---|
| `app.py` | interfaccia web (Streamlit) |
| `catasto_punti.py` | lettura dei punti, interrogazione del Catasto, mappa, esportazione |
| `requirements.txt` | librerie Python da installare sul server |
| `.streamlit/config.toml` | impostazioni di Streamlit (dimensione massima dei file, niente statistiche d'uso) |
| `punti_esempio.csv` | file di prova (6 punti a Torre del Greco) |

## Perché serve un server

I servizi del Catasto non autorizzano le chiamate dirette da pagine web di altri siti (non inviano gli header CORS). Una pagina HTML statica potrebbe mostrare la mappa, ma non leggere foglio e particella. Per questo l'app gira su un server Python, che interroga il Catasto al posto del browser.

## Provarla sul proprio computer (serve Python 3.10 o successivo)

```bash
pip install -r requirements.txt
```

```bash
streamlit run app.py
```

Si apre il browser su `http://localhost:8501`.

## Pubblicarla per chi non ha Python

### Opzione A – Streamlit Community Cloud (gratuito)

1. Crea un repository GitHub con i file di questa cartella (compresa `.streamlit/`).
2. Su [share.streamlit.io](https://share.streamlit.io) accedi con GitHub, crea una nuova app indicando repository, ramo e `app.py` come file principale.
3. Dopo il deploy l'app ha un indirizzo `https://<nome>.streamlit.app` da distribuire.

L'app va in sospensione dopo un periodo di inattività e si riattiva al primo accesso, in meno di un minuto. Controlla nelle impostazioni dell'app chi può accedervi.

### Opzione B – server del dipartimento

Su un server Linux con Python 3.10 o successivo:

```bash
pip install -r requirements.txt
```

```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

Per un servizio stabile conviene avviarla come servizio di sistema (systemd) e pubblicarla dietro un reverse proxy (nginx o Apache) con HTTPS. Il proxy deve inoltrare anche le connessioni WebSocket, che Streamlit usa per aggiornare la pagina.

## File di ingresso

- CSV con separatore `;`, `,` o tabulazione; la virgola decimale è accettata (`40,7869`). Va bene il CSV salvato da Excel in italiano.
- Oppure Excel (`.xlsx`).
- Colonne: `nome`, `lat`, `lon`. Sono accettati anche `latitudine`/`longitudine`, `lng`, `name`. Se manca `nome`, i punti vengono numerati P1, P2, …
- L'app avvisa se lat e lon sembrano invertite o se ci sono punti fuori dall'Italia.
- Massimo 1000 punti per file (`MAX_PUNTI` in `catasto_punti.py`).

## File di uscita

- **Excel** e **CSV** (separatore `;`, virgola decimale, per Excel in italiano) con le colonne aggiunte `comune_belfiore`, `foglio`, `allegato`, `sviluppo`, `particella`, `rif_catastale`, `note`.
- **Mappa HTML** interattiva: si apre con qualsiasi browser, senza installare nulla.

Nella mappa i fogli compaiono da zoom 12, le particelle da zoom 17 e i numeri di particella da zoom 18.

## Cose da sapere

- **Errori del server catastale**: circa metà delle connessioni riceve sempre un errore. L'app lo riconosce e riprova fino a 10 volte per richiesta. Se un punto resta in errore, compare il pulsante **Riprova questi punti**.
- **Tempi**: nelle prove, 6 punti hanno richiesto 12–25 secondi (4 richieste in parallelo).
- **Precisione**: il risultato dipende dalla precisione delle coordinate (con 4 decimali circa ±5 m) e dalla cartografia catastale. È indicativo e non sostituisce una visura.
- **Riservatezza**: le coordinate vengono inviate al servizio dell'Agenzia delle Entrate e passano per il server che ospita l'app.
- **Codice condiviso con il notebook**: la logica è copiata da `mappa_punti_v1.1.ipynb`. Se la modifichi in un punto, aggiornala anche nell'altro, oppure fai importare `catasto_punti.py` al notebook.
- Il servizio non copre le province di Trento e Bolzano (catasto tavolare).

Dati catastali: © Agenzia delle Entrate – licenza CC BY 4.0.
