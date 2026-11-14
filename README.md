# Punti su mappa e Catasto – web app (versione 1.2.0)

Web app che riceve un file **CSV o Excel** con le colonne `nome`, `lat`, `lon` (gradi decimali, WGS84), mostra i punti su una mappa OpenStreetMap con i fogli e le particelle catastali e, per ogni punto, ricava **comune (codice Belfiore), foglio e particella**. I risultati si scaricano come Excel, CSV o mappa HTML.

Usa la stessa logica di `mappa_punti_v1.4.ipynb`. Chi la usa ha bisogno solo di un browser.

## Contenuto

| file | a cosa serve |
|---|---|
| `app.py` | interfaccia web (Streamlit) |
| `catasto_punti.py` | lettura dei punti, interrogazione del Catasto, mappa, esportazione |
| `requirements.txt` | librerie Python da installare sul server |
| `.streamlit/config.toml` | impostazioni di Streamlit (dimensione massima dei file, niente statistiche d'uso) |
| `punti_esempio.csv` | file di prova (6 punti a Torre del Greco) |
| `GUIDA_PUBBLICAZIONE.md` | guida alla pubblicazione (Community Cloud e server del dipartimento) |
| `deploy/` | modelli per il server: servizio systemd, configurazioni nginx e Apache |

## Perché serve un server

I servizi del Catasto non autorizzano le chiamate dirette da pagine web di altri siti (non inviano gli header CORS). Una pagina HTML statica potrebbe mostrare la mappa, ma non leggere foglio e particella. Per questo l'app gira su un server Python, che interroga il Catasto al posto del browser.

## Provarla sul proprio computer (serve Python 3.11 o successivo)

```bash
pip install -r requirements.txt
```

```bash
streamlit run app.py
```

Si apre il browser su `http://localhost:8501`.

## Pubblicarla per chi non ha Python

Le istruzioni passo passo sono in **`GUIDA_PUBBLICAZIONE.md`**, per due modalità:

- **Streamlit Community Cloud**: gratuito, con un account GitHub, senza server.
- **Server del dipartimento**: Linux con systemd e nginx o Apache, usando i modelli nella cartella `deploy/`.

## File di ingresso

- CSV con separatore `;`, `,` o tabulazione; la virgola decimale è accettata (`40,7869`). Va bene il CSV salvato da Excel in italiano.
- Oppure Excel (`.xlsx`).
- Colonne: `nome`, `lat`, `lon`. Sono accettati anche `latitudine`/`longitudine`, `lng`, `name`. Se manca `nome`, i punti vengono numerati P1, P2, …
- L'app avvisa se lat e lon sembrano invertite o se ci sono punti fuori dall'Italia.
- Massimo 1000 punti per file (`MAX_PUNTI` in `catasto_punti.py`).

## File di uscita

- **Excel** e **CSV** (separatore `;`, virgola decimale, per Excel in italiano) con le colonne aggiunte `comune_belfiore`, `foglio`, `allegato`, `sviluppo`, `particella`, `rif_catastale`, `note`.
- **Mappa HTML** interattiva: si apre con qualsiasi browser, senza installare nulla.

Nella mappa i fogli compaiono da zoom 12, le particelle da zoom 17 e i numeri di particella da zoom 18. Dal pannello dei layer si possono accendere anche i fabbricati (da zoom 17) e le strade e acque (da zoom 14) del Catasto, spenti all'apertura.

## Cose da sapere

- **Errori del server catastale**: circa metà delle connessioni riceve sempre un errore. L'app lo riconosce e riprova fino a 10 volte per richiesta. Se un punto resta in errore, compare il pulsante **Riprova questi punti**.
- **Tempi**: nelle prove, 6 punti hanno richiesto 12–25 secondi (4 richieste in parallelo).
- **Precisione**: il risultato dipende dalla precisione delle coordinate (con 4 decimali circa ±5 m) e dalla cartografia catastale. È indicativo e non sostituisce una visura.
- **Smartphone e tablet**: la pagina si adatta allo schermo. Sulla mappa un dito scorre la pagina e due dita spostano la mappa; a schermo intero un dito sposta la mappa. Nella tabella nome, foglio e particella sono le prime colonne.
- **Riservatezza**: le coordinate vengono inviate al servizio dell'Agenzia delle Entrate e passano per il server che ospita l'app.
- **Codice condiviso con il notebook**: le funzioni di `catasto_punti.py` sono copiate identiche in `mappa_punti_v1.4.ipynb`. Ogni modifica va riportata in entrambi, aggiornando le versioni.
- Il servizio non copre le province di Trento e Bolzano (catasto tavolare).

Dati catastali: © Agenzia delle Entrate – licenza CC BY 4.0.

## Storico revisioni

- **1.2.0** – Nel pannello dei layer anche i fabbricati (da zoom 17) e le strade e acque (da zoom 14) del Catasto, spenti all'apertura e semitrasparenti. Allineata al notebook 1.4.
- **1.1.0** – Uso da smartphone e tablet: un dito scorre la pagina e due dita spostano la mappa (a schermo intero un dito sposta la mappa), la scala grafica non viene più coperta dalle attribuzioni, nella tabella nome, foglio e particella sono le prime colonne. Sul computer la mappa non cambia. Allineata al notebook 1.3.
- **1.0.2** – `leggi_punti` accetta il parametro facoltativo `foglio_excel`, per avere funzioni identiche al notebook 1.2. Nessun cambiamento visibile nell'app.
- **1.0.1** – Aggiunti la guida alla pubblicazione e i modelli per il server (`deploy/`).
- **1.0** – Versione iniziale.
