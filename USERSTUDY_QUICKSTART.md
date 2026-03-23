# User Study - Guida al Deployment e Testing

## Quick Start

### 1. Attiva l'ambiente virtuale

```bash
cd /home/mirko/Documents/github/osm_fetch_testing
source .venv/bin/activate
```

### 2. Installa dipendenze (se necessario)

```bash
pip install -r backend/requirements.txt
```

### 3. Avvia l'applicazione

```bash
uvicorn backend.app:app --reload
```

L'app dovrebbe partire su `http://localhost:8000`

### 4. Accedi allo user study

Apri il browser e vai a: **http://localhost:8000/userstudy/welcome**

## Flusso di Test Completo

Segui i 7 step dello user study:

1. **Welcome** - Clicca "Inizia lo Studio"
2. **Questionnaire 1** - Compila i dati demografici
3. **Questionnaire 2** - Valuta il tuo quartiere (pre-esplorazione)
4. **Search** - Seleziona una via sulla mappa
5. **Personal** - Scegli categorie e parametri
6. **Results** - Visualizza i risultati sulla mappa
7. **Questionnaire 3** - Valuta di nuovo il quartiere (post-esplorazione)
8. **Thanks** - Completa lo studio

## Verifica dei Dati

Dopo completare lo user study, controlla che i dati siano stati salvati:

### Via MongoDB

```bash
# Connettiti a MongoDB
mongo -u user -p pass

# Seleziona il database
use 15minute

# Visualizza le sessioni
db.userstudy_sessions.find()

# Conta le sessioni completate
db.userstudy_sessions.countDocuments({"thanked_at": {$exists: true, $ne: null}})
```

### Via API

```bash
curl -X GET http://localhost:8000/api/userstudy/sessions/all
```

## Documenti di Riferimento

- **Flusso completo**: Vedi [USERSTUDY_FLOW.md](USERSTUDY_FLOW.md)
- **README app**: Vedi [README.md](README.md)

## Troubleshooting

### Errore: "Session not found"
- Assicurati che `sessionStorage` sia abilitato nel browser
- Apri la console del browser (F12) per vedere i messaggi di errore
- Controlla che l'URL sia corretto

### Errore: "Database connection error"
- Verifica che MongoDB sia in esecuzione
- Controlla la variabile `MONGO_URL` in `backend/db.py`
- Se usi Docker: `docker-compose up -d mongodb`

### Errore: "Isochrone calculation failed"
- Questo è normale - la pagina dei risultati mosterà comunque la mappa e il grafico
- L'isochrone è visualizzato come un cerchio approssimativo

### API returns 500 error
- Controlla i log di FastAPI nel terminale
- Verifica che MongoDB sia accessibile
- Controlla la syntax del JSON inviato

## Funzionalità Aggiuntive

### Download dati sessione
- Pagina di ringraziamenti: Clicca "Scarica i Tuoi Dati"
- Scarica un file JSON con tutti i dati della sessione

### Recupero di una sessione specifica
```bash
curl -X POST http://localhost:8000/api/userstudy/session/get \
  -H "Content-Type: application/json" \
  -d '{"session_id": "YOUR_SESSION_ID"}'
```

## Prossimi Passi

1. ✓ Deploy - Testa localmente
2. ✓ Testing - Verifica il flusso completo
3. ✓ Data - Esporta risultati da MongoDB
4. ✓ Analysis - Analizza le risposte dei questionari
5. ✓ Refinement - Apporta modifiche basate sui feedback

## Note Importanti

- I dati sono **completamente anonimizzati** - nessun dato personale viene conservato
- Session ID è una **UUID casuale** senza identificatori personali
- Tutti i dati sono conservati in MongoDB sotto la collezione `userstudy_sessions`
- L'app supporta **multiple sessioni simultanee**

## Branch Git

- **Branch principale**: `main`
- **Branch user study**: `userstudy`

```bash
# Per passare al branch user study
git checkout userstudy

# Per tornare al main
git checkout main
```

## Supporto

Per domande o problemi relativi all'implementazione dello user study, contatta il maintainer del progetto.
