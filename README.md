
# FastAPI Application

Benvenuto! Questa guida ti aiuterà a configurare l'ambiente e a eseguire questa applicazione **FastAPI** sulla tua macchina.

---

## **Requisiti**

Prima di iniziare, assicurati di avere i seguenti requisiti:

- **Python** 3.7 o superiore installato.
- Accesso al terminale (PowerShell su Windows, terminale su macOS/Linux).

Per verificare la versione di Python, esegui:
```bash
python --version
```

---

## **Installazione**

Segui i passaggi sottostanti per configurare l'ambiente e avviare l'applicazione.

### **1. Clona o scarica il progetto**

Se il progetto è ospitato su un repository (es. GitHub):
```bash
git clone <URL_DEL_REPOSITORY>
cd <NOME_CARTELLA_PROGETTO>
```

Se hai ricevuto un file `.zip`, estrai il contenuto in una directory di tua scelta e accedi alla directory.

---

### **2. Crea un ambiente virtuale**

1. Nel terminale, crea un ambiente virtuale:
   ```bash
   python -m venv .venv
   ```
   Questo creerà una directory chiamata `.venv` all'interno del progetto.

2. Attiva l'ambiente virtuale:
   - **Windows**:
     ```bash
     .venv\Scripts\activate
     ```
   - **macOS/Linux**:
     ```bash
     source .venv/bin/activate
     ```

   Dopo l'attivazione, dovresti vedere il nome dell'ambiente virtuale (ad esempio, `.venv`) all'inizio del prompt del terminale.

---

### **3. Installa le dipendenze**

Con l'ambiente virtuale attivo, installa le dipendenze richieste.

Se non è presente, puoi installare manualmente i pacchetti richiesti:
```bash
pip install fastapi uvicorn
```

---

### **4. Avvia l'applicazione**

Con l'ambiente virtuale attivo, esegui l'applicazione con il comando:
```bash
uvicorn backend.app:app --reload
```

#### Spiegazione del comando:
- **`backend.app`**: Specifica il percorso del file `app.py` che contiene l'applicazione. Se il file si trova in un'altra posizione, modifica il percorso di conseguenza.
- **`--reload`**: Abilita il ricaricamento automatico durante lo sviluppo, così le modifiche al codice saranno applicate senza riavviare manualmente il server.

---

### **5. Verifica il funzionamento**

1. Apri un browser e vai a:
   - **[http://127.0.0.1:8000](http://127.0.0.1:8000)**: Verifica l'endpoint principale dell'app.
   - **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**: Esplora la documentazione interattiva Swagger UI.
   - **[http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)**: Esplora la documentazione ReDoc.

---

### **6. Disattiva l'ambiente virtuale**

Quando hai terminato, puoi disattivare l'ambiente virtuale con:
```bash
deactivate
```
### **SetUp database**
Assicurati di avere installato docker.
Se possiedi la cartella db_init inseriscila nella cartella principale (root)
all'interno della cartella db_init inserisci il file docker-compose che ti è stato inviato.
apri un terminale in db_init ed esegui il comando
```bash
docker-compose up
```
opzionalmente con un applicazione come datagrip puoi visualizzare il DB inserendo i dati che trovi nel docker-compose

### **Dev Fast Start**
Una volta setuppato tutto per i successivi avii basterà avviare docker sul proprio dispositivo poi fare i seguenti due comandi:
in db_init:
```bash
docker-compose up
```
e nella root:
```bash
uvicorn backend.app:app --reload
```


NOTE LORENZO PALEARI:

per ora ho messo questo sistema per vedere se ho nel DB la città, poi dovrei migliorarlo:
neighbourhoods.py, riga 24: if city_name and city_name.lower() not in ['torino', 'turin']:

