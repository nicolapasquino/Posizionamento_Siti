# Guida alla pubblicazione della web app "Punti e Catasto"

Versione 1.3.0 – 15/11/2026

Questa guida spiega come mettere online la web app in due modi:

- **A. Streamlit Community Cloud**: gratuito, pronto in circa 15 minuti, non serve un server.
- **B. Server del dipartimento**: l'app gira su una macchina dell'ateneo, con un indirizzo dell'ateneo.

Le due strade sono indipendenti: si può seguire solo quella che interessa.

## Quale scegliere

| | A. Community Cloud | B. Server del dipartimento |
|---|---|---|
| Costo | gratuito | macchina e tempo del servizio informatico |
| Tempo di attivazione | circa 15 minuti | qualche ora, più i tempi del servizio informatico |
| Competenze | account GitHub, nessun comando | amministrazione di un server Linux |
| Indirizzo | `https://<nome>.streamlit.app` | `https://catasto.dipartimento.it` o `https://www.dipartimento.it/catasto/` |
| Dove passano i dati | server negli Stati Uniti (Streamlit/Snowflake) | server dell'ateneo |
| Accesso | pubblico, oppure privato con inviti via email (una sola app privata per account) | regolato dall'ateneo (rete interna, VPN, pubblico) |
| Disponibilità | va in sospensione dopo 12 ore senza visite e si riattiva su richiesta | sempre attiva |
| Risorse | limitate (indicativamente fino a 2,7 GB di memoria) | quelle della macchina |
| Adatta a | didattica, dimostrazioni, uso occasionale | consulenze, dati riservati, uso continuativo |

In entrambi i casi le coordinate dei punti vengono inviate anche al servizio WMS dell'Agenzia delle Entrate: è così che l'app ricava foglio e particella.

## Contenuto del pacchetto

Il file `mappa_punti_webapp_v1.3.0.zip` contiene la cartella `mappa_punti_webapp`:

| file | serve per |
|---|---|
| `app.py`, `catasto_punti.py` | l'applicazione |
| `requirements.txt` | elenco delle librerie Python |
| `.streamlit/config.toml` | impostazioni di Streamlit (cartella che inizia con un punto: vedi la nota in A.2) |
| `punti_esempio.csv` | file di prova, usato per la verifica finale |
| `deploy/catasto.service` | servizio systemd (solo modalità B) |
| `deploy/nginx-catasto.conf`, `deploy/apache-catasto.conf` | configurazioni del server web (solo modalità B) |
| `README.md`, `GUIDA_PUBBLICAZIONE.md` | documentazione |

---

# A. Streamlit Community Cloud

Servono un account **GitHub** (gratuito) e circa 15 minuti. Non si usa il terminale: tutto avviene dal browser.

## A.1 Creare un account GitHub

Se non ne hai già uno, registrati su [github.com](https://github.com). Puoi usare l'email dell'ateneo.

## A.2 Creare il repository con i file dell'app

1. Estrai lo zip sul tuo computer.
2. Su GitHub fai clic su **+** (in alto a destra) e poi su **New repository**.
3. Scegli un nome, per esempio `mappa-punti-catasto`.
4. Scegli la visibilità:
   - **Public**: l'app sarà pubblica, chiunque abbia il link potrà usarla. Il codice non contiene password o dati riservati, quindi è una scelta sicura.
   - **Private**: l'app sarà privata e potrai invitare le persone per email. Streamlit consente **una sola app privata per account**.
5. Fai clic su **Create repository**.
6. Nella pagina del repository vuoto fai clic sul link **uploading an existing file**.
7. Trascina nella pagina **il contenuto** della cartella `mappa_punti_webapp`, non la cartella stessa: `app.py`, `catasto_punti.py`, `requirements.txt`, `punti_esempio.csv`, i file `.md` e le cartelle `.streamlit` e `deploy`.
8. Fai clic su **Commit changes**.

Al termine, nella pagina del repository `app.py` e `requirements.txt` devono comparire **al primo livello**, non dentro una sottocartella.

> **Nota sulla cartella `.streamlit`.** Su macOS il Finder nasconde le cartelle il cui nome inizia con un punto: premi **Cmd + Maiusc + .** per vederle. Se la cartella non viene caricata, in GitHub scegli **Add file → Create new file**, scrivi come nome `.streamlit/config.toml` e incolla il contenuto del file. L'app funziona anche senza questa cartella: serve solo a limitare la dimensione dei file caricati a 10 MB.

## A.3 Collegare Streamlit a GitHub

1. Vai su [share.streamlit.io](https://share.streamlit.io) e fai clic su **Continue to sign-in**, poi su **Continue with GitHub**.
2. In alto a sinistra fai clic su **Workspaces**, poi su **Connect GitHub account** e su **Authorize streamlit**.
3. Se il repository è **privato** serve un'autorizzazione in più. Fai clic sul tuo nome utente, poi su **Settings → Linked accounts**. Sotto *Source control* fai clic su **Connect here** e su **Authorize streamlit**.

Per pubblicare devi essere amministratore del repository: lo sei, se l'hai creato tu.

## A.4 Pubblicare l'app

1. Fai clic su **Create app** (in alto a destra).
2. Alla domanda *Do you already have an app?* rispondi **Yup, I have an app**.
3. Compila i campi:
   - **Repository**: `tuo-utente/mappa-punti-catasto`
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **App URL** (facoltativo): il nome che vuoi, per esempio `catasto-unina`, che diventa `https://catasto-unina.streamlit.app`
4. In **Advanced settings** lascia la versione di Python predefinita (3.12, quella provata). Il campo *Secrets* va lasciato vuoto. Fai clic su **Save**.
5. Fai clic su **Deploy**.

La prima installazione richiede qualche minuto. Poi l'app si apre all'indirizzo scelto.

## A.5 Verifica

Esegui la **verifica finale** descritta in fondo alla guida.

## A.6 Gestione

- **Condividere**: distribuisci l'indirizzo `https://<nome>.streamlit.app`. Per un'app privata usa il pulsante **Share** e inserisci le email degli invitati. Gli invitati accedono con Google o con un link ricevuto per email.
- **Sospensione**: dopo 12 ore senza visite l'app va in sospensione. Il primo visitatore vede la pagina *"Zzzz. This app has gone to sleep due to inactivity"*: deve fare clic su **Yes, get this app back up!** e attendere circa un minuto.
- **Aggiornare**: modifica o ricarica i file nel repository GitHub. L'app si aggiorna da sola in pochi istanti; se cambia `requirements.txt`, si reinstalla.
- **Log e riavvio**: apri l'app e fai clic su **Manage app** (in basso a destra). Da lì si vedono i messaggi del server e si riavvia l'app. Nel menu dell'app, nella pagina dei workspace, ci sono anche **Reboot**, **Settings** e **Delete**.
- **Risorse**: se compare il messaggio *"This app has gone over its resource limits"*, l'app ha superato la memoria disponibile. Con file fino a 1000 punti non dovrebbe succedere. Streamlit concede gratuitamente più risorse alle organizzazioni educative, su richiesta.
- **Statistiche**: su Community Cloud Streamlit raccoglie comunque le statistiche d'uso anonime, anche se `config.toml` le disattiva.

---

# B. Server del dipartimento

I comandi sono per **Ubuntu 24.04 o Debian 12**, che hanno Python 3.12 e 3.11. Ubuntu 22.04 non va bene così com'è: il suo Python 3.10 è troppo vecchio per le versioni attuali di Streamlit e pandas. La procedura è stata provata su Ubuntu 24.04 con Python 3.12, Streamlit 1.67, nginx 1.24 e Apache 2.4.58.

Lo schema è:

```
browser ──HTTPS──▶ nginx o Apache (porta 443) ──▶ Streamlit (127.0.0.1:8501) ──▶ WMS Agenzia delle Entrate
```

Streamlit ascolta solo sulla macchina stessa (`127.0.0.1`). Dall'esterno si raggiunge solo attraverso il server web, che gestisce il certificato HTTPS.

## B.1 Cosa chiedere al servizio informatico

- [ ] Una macchina Linux (anche virtuale), preferibilmente Ubuntu 24.04 o Debian 12, con **Python 3.11 o successivo**, 1–2 GB di RAM e 5 GB di disco.
- [ ] L'indirizzo, in una di queste due forme:
  - **variante A**: un nome dedicato, per esempio `catasto.dipartimento.unina.it`;
  - **variante B**: una sottocartella di un sito esistente, per esempio `https://www.dipartimento.unina.it/catasto/`.
- [ ] Un certificato HTTPS per quel nome: quello dell'ateneo, oppure Let's Encrypt se la macchina è raggiungibile da internet.
- [ ] Il permesso di uscire su internet verso `wms.cartografia.agenziaentrate.gov.it` e `wfs.cartografia.agenziaentrate.gov.it` (porta 443): il secondo serve per le particelle nel cerchio. Durante l'installazione serve anche l'accesso a `pypi.org` e `files.pythonhosted.org`. Se l'uscita passa per un **proxy dell'ateneo**, fatti dare l'indirizzo.
- [ ] Firewall: in ingresso solo le porte 80 e 443. La porta 8501 **non** va aperta.
- [ ] Chi potrà usare l'app: solo la rete interna o la VPN dell'ateneo, oppure tutti.

I passi seguenti richiedono i permessi di amministratore (`sudo`). Se li esegue il servizio informatico, basta consegnare questa sezione e la cartella `deploy`.

## B.2 Installazione

**1. Pacchetti di sistema.** Installa il server web che preferisci, nginx oppure Apache (`apache2` al posto di `nginx`):

```bash
sudo apt update
sudo apt install -y python3-venv unzip nginx
```

**2. Utente dedicato.** L'app gira con un utente senza privilegi:

```bash
sudo adduser --system --group --home /opt/catasto catasto
```

**3. Copia dei file.** Dal tuo computer copia lo zip sul server:

```bash
scp mappa_punti_webapp_v1.3.0.zip utente@server:/tmp/
```

Poi, sul server:

```bash
cd /tmp && unzip -o mappa_punti_webapp_v1.3.0.zip
sudo mkdir -p /opt/catasto/app
sudo cp -r /tmp/mappa_punti_webapp/. /opt/catasto/app/
sudo chown -R catasto:catasto /opt/catasto
```

**4. Ambiente Python e librerie.** Le librerie vanno in un ambiente separato, senza toccare il Python di sistema:

```bash
sudo -u catasto python3 -m venv /opt/catasto/venv
sudo -u catasto /opt/catasto/venv/bin/pip install --upgrade pip
sudo -u catasto /opt/catasto/venv/bin/pip install -r /opt/catasto/app/requirements.txt
```

Se il server esce su internet tramite un proxy, aggiungi prima di `pip` l'opzione `--proxy http://proxy.esempio.it:3128`.

## B.3 Prova manuale

```bash
sudo -u catasto sh -c 'cd /opt/catasto/app && /opt/catasto/venv/bin/streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true'
```

Il comando entra nella cartella dell'app come utente `catasto`: Streamlit legge le impostazioni da `.streamlit/config.toml` nella cartella da cui parte.

Da un secondo terminale sullo stesso server:

```bash
curl http://127.0.0.1:8501/_stcore/health
```

Deve rispondere `ok`. Per la **variante B** (sottocartella) aggiungi `--server.baseUrlPath catasto` dopo `--server.headless true` e usa `http://127.0.0.1:8501/catasto/_stcore/health`.

Ferma la prova con **Ctrl + C**.

## B.4 Avvio automatico con systemd

Il servizio fa partire l'app all'accensione e la riavvia se si interrompe.

```bash
sudo cp /opt/catasto/app/deploy/catasto.service /etc/systemd/system/catasto.service
```

Prima di attivarlo, controlla il file (`sudo nano /etc/systemd/system/catasto.service`):

- **Variante B**: aggiungi `--server.baseUrlPath catasto` in fondo alla riga `ExecStart`.
- **Proxy dell'ateneo**: togli il `#` dalla riga `Environment="HTTPS_PROXY=..."` e indica l'indirizzo del proxy.

Poi attivalo:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now catasto
systemctl status catasto
```

Lo stato deve essere `active (running)`. Ripeti il controllo di B.3 con `curl`.

## B.5 Server web (reverse proxy)

Il server web riceve le richieste HTTPS e le passa a Streamlit. Streamlit usa una connessione **WebSocket** per aggiornare la pagina: il server web deve inoltrarla, e i file in `deploy/` sono già configurati per farlo.

### Con nginx

**Variante A, nome dedicato:**

```bash
sudo cp /opt/catasto/app/deploy/nginx-catasto.conf /etc/nginx/sites-available/catasto
sudo nano /etc/nginx/sites-available/catasto
```

Nel file sostituisci `catasto.dipartimento.it` con il nome vero nelle due righe `server_name` e indica i percorsi del certificato (`ssl_certificate`, `ssl_certificate_key`). Poi:

```bash
sudo ln -s /etc/nginx/sites-available/catasto /etc/nginx/sites-enabled/catasto
sudo nginx -t
sudo systemctl reload nginx
```

`nginx -t` deve rispondere *syntax is ok* e *test is successful*.

**Variante B, sottocartella di un sito esistente:**

1. Nel file `deploy/nginx-catasto.conf` copia il blocco `map ... { ... }` nel blocco `http` di nginx, per esempio in un nuovo file `/etc/nginx/conf.d/websocket.conf`.
2. Copia il blocco `location /catasto/ { ... }` (in fondo al file, senza i `#`) dentro il blocco `server` del sito esistente.
3. Verifica che il servizio sia avviato con `--server.baseUrlPath catasto` (B.4).
4. Esegui `sudo nginx -t` e `sudo systemctl reload nginx`.

### Con Apache

Serve Apache 2.4.47 o successivo (Ubuntu 24.04 e Debian 12 vanno bene). Abilita i moduli:

```bash
sudo a2enmod ssl proxy proxy_http proxy_wstunnel headers
```

**Variante A, nome dedicato:**

```bash
sudo cp /opt/catasto/app/deploy/apache-catasto.conf /etc/apache2/sites-available/catasto.conf
sudo nano /etc/apache2/sites-available/catasto.conf
```

Nel file sostituisci `catasto.dipartimento.it` con il nome vero nelle righe `ServerName` e `Redirect` e indica i percorsi del certificato. Poi:

```bash
sudo a2ensite catasto
sudo apache2ctl configtest
sudo systemctl reload apache2
```

`configtest` deve rispondere *Syntax OK*.

**Variante B, sottocartella:** copia le due righe `ProxyPass /catasto/ ...` e `ProxyPassReverse /catasto/ ...` (in fondo al file, senza i `#`) nel `VirtualHost` del sito esistente. Verifica che il servizio sia avviato con `--server.baseUrlPath catasto`, poi esegui `configtest` e `reload` come sopra.

### Certificato con Let's Encrypt (facoltativo)

Se la macchina è raggiungibile da internet e l'ateneo non fornisce un certificato:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d catasto.dipartimento.unina.it
```

Con Apache usa `python3-certbot-apache` e `certbot --apache`. Certbot aggiorna da solo la configurazione e rinnova il certificato.

## B.6 Verifica

Esegui la **verifica finale** descritta in fondo alla guida, all'indirizzo pubblico, per esempio `https://catasto.dipartimento.unina.it` o `https://www.dipartimento.unina.it/catasto/`.

## B.7 Gestione

**Log dell'app** (errori, avvii, riavvii):

```bash
sudo journalctl -u catasto -f
```

**Riavvio:**

```bash
sudo systemctl restart catasto
```

**Aggiornamento a una nuova versione.** Copia il nuovo zip in `/tmp` come in B.2, poi:

```bash
cd /tmp && unzip -o mappa_punti_webapp_vX.Y.zip
sudo cp -r /tmp/mappa_punti_webapp/. /opt/catasto/app/
sudo chown -R catasto:catasto /opt/catasto/app
sudo -u catasto /opt/catasto/venv/bin/pip install -r /opt/catasto/app/requirements.txt
sudo systemctl restart catasto
```

Se avevi modificato `/etc/systemd/system/catasto.service` o la configurazione del server web, quei file non vengono toccati dall'aggiornamento.

## B.8 Problemi frequenti

| sintomo | causa probabile | soluzione |
|---|---|---|
| La pagina resta grigia, con riquadri vuoti, e non si carica mai | il server web non inoltra il WebSocket | usa i file di `deploy/` senza togliere le righe `Upgrade`/`Connection` (nginx) o `upgrade=websocket` (Apache); con Apache verifica che `proxy_wstunnel` sia attivo |
| *502 Bad Gateway* (nginx) o *503 Service Unavailable* (Apache) | l'app non è in esecuzione | `systemctl status catasto` e `journalctl -u catasto -n 50` |
| Pagina bianca o *404* nella variante B | sottocartella diversa tra server web e Streamlit | il nome dopo `--server.baseUrlPath` deve coincidere con quello di `location`/`ProxyPass` (qui `catasto`) |
| Il caricamento del file fallisce con errore *413* | file più grande del limite del server web | `client_max_body_size` in nginx (nel modello è già 10 MB, come in `config.toml`) |
| Tutti i punti hanno la nota *errore: …* | il server non raggiunge il servizio dell'Agenzia | dal server: `curl -sI "https://wms.cartografia.agenziaentrate.gov.it/inspire/wms/ows01.php?SERVICE=WMS&REQUEST=GetCapabilities"`; se serve un proxy, impostalo nel servizio (B.4) |
| Il cerchio funziona, ma includendo le particelle compare *Non è stato possibile scaricare le particelle* | il server non raggiunge il servizio WFS dell'Agenzia | dal server: `curl -sI "https://wfs.cartografia.agenziaentrate.gov.it/inspire/wfs/owfs01.php?SERVICE=WFS&REQUEST=GetCapabilities"`; chiedi al servizio informatico di aprire l'uscita verso questo indirizzo |
| Nei log compare *CERTIFICATE_VERIFY_FAILED* | il proxy dell'ateneo ispeziona il traffico HTTPS | chiedi al servizio informatico il certificato del proxy e aggiungi nel servizio `Environment="REQUESTS_CA_BUNDLE=/percorso/certificato.pem"` |
| Alcuni punti hanno la nota *errore: …* | errori temporanei del servizio dell'Agenzia | pulsante **Riprova questi punti** nell'app |

---

# Verifica finale (entrambe le modalità)

1. Apri l'indirizzo dell'app: compare la pagina **Punti su mappa e Catasto**. Nella barra laterale si legge **Versione 1.3.0**.
2. Carica il file `punti_esempio.csv` del pacchetto e fai clic su **Elabora**.
3. Entro circa mezzo minuto compare la tabella **Risultati (6 punti)**. Per esempio, *Villa delle Ginestre* deve risultare **foglio 3, particella 325** (riferimento `L259_000300.325`).
4. Nella mappa ingrandisci fino a vedere le particelle (da zoom 17) e i loro numeri (da zoom 18).
5. Prova i tre pulsanti **Scarica Excel**, **Scarica CSV** e **Scarica mappa (HTML)**: i file devono scaricarsi e aprirsi.

Se tutti i passi riescono, l'app è pronta per essere distribuita.
