# User Study - Linea di Flusso

Questo documento descrive ilnuovo flusso dell'applicazione per lo user study sulla accessibilità urbana.

## Guida al Flusso

L'applicazione segue un flusso strutturato in 7 step:

### Step 1: Benvenuto (`/userstudy/welcome`)
- Pagina di benvenuto e introduzione allo studio
- **Azione**: Crea una nuova sessione anonima
- **Output**: `session_id` salvato nel `sessionStorage`
- **Pulsante**: "Inizia lo Studio" → Step 2

### Step 2: Primo Questionario (`/userstudy/questionnaire1`)
- **Domande**: Dati demografici (età, genere, istruzione, occupazione, trasporti, abitazione, area urbana)
- **Salvataggio**: Endpoint `/api/userstudy/demographics/submit`
- **Pulsante**: "Avanti" → Step 3

### Step 3: Secondo Questionario (`/userstudy/questionnaire2`)
- **Domande**: Percezione iniziale del quartiere (pre-esplorazione)
  - Accessibilità (0-5)
  - Vicinanza media (minuti)
  - Vicinanza massima (minuti)
  - Densità (0-5)
  - Varietà (0-5)
  - Connettività (0-5)
- **Salvataggio**: Endpoint `/api/userstudy/preexploration/submit`
- **Pulsante**: "Avanti" → Step 4

### Step 4: Selezione Via (`/userstudy/search`)
- **Funzione**: Ricerca e selezione di una via sulla mappa
- **Funzionalità**:
  - Ricerca geocoding con Nominatim
  - Selezione di un indirizzo/via
  - Visualizzazione sul marker sulla mappa
- **Salvataggio**: Endpoint `/api/userstudy/street/select`
  - Street name
  - Coordinate (lat/lon)
- **Pulsante**: "Avanti" → Step 5

### Step 5: Selezione Categorie (`/userstudy/personal`)
- **Funzione**: Configurazione parametri di ricerca
- **Selezioni**:
  - Tempo di viaggio: 5, 10, 15, 20 minuti
  - Modalità di viaggio: A piedi, Con bastone
  - Categorie di servizi (supermarket, ristorante, farmacia, ospedale, scuola, biblioteca, palestra, parco, banca, posta, bus stop)
- **Salvataggio**: Endpoint `/api/userstudy/categories/select`
  - categories (array)
  - travel_time (int)
  - travel_mode (string)
- **Pulsante**: "Avanti" → Step 6

### Step 6: Visualizzazione Risultati (`/userstudy/results`)
- **Funzione**: Mappa con isochrone e grafico spider
- **Dati Mostrati**:
  - Via selezionata
  - Marcatore sulla mappa
  - Cerchio di isochrone (raggio basato su tempo di viaggio)
  - Grafico spider con analisi dei servizi
- **Azioni**:
  - Endpoint `/api/userstudy/results/viewed` per registrare la visualizzazione
  - Recupera i dati della sessione via `/api/userstudy/session/get`
- **Pulsante**: "Avanti" → Step 7

### Step 7: Terzo Questionario (`/userstudy/questionnaire3`)
- **Domande**: Percezione post-esplorazione (stesse domande del Step 3, più domande aggiuntive)
  - Stesse 6 domande di valutazione (Accessibility, Proximity, Density, Variety, Closeness)
  - Impatto della piattaforma sulla comprensione (0-5)
  - Revisione dell'opinione (0-5)
  - Commenti finali (testo libero)
- **Salvataggio**: Endpoint `/api/userstudy/postexploration/submit`
- **Pulsante**: "Avanti" → Step 8

### Step 8: Ringraziamenti (`/userstudy/thanks`)
- **Funzione**: Conclusione dello studio
- **Azioni**:
  - Endpoint `/api/userstudy/session/complete` per marcare la sessione come completata
  - Opzione di download dei dati in JSON
  - Link alla home page
- **Storage**: SessionID rimane nel `sessionStorage` fino alla chiusura della finestra

## Modello di Dati Salvati

Ogni sessione viene salvata in MongoDB con la seguente struttura:

```json
{
  "session_id": "uuid-string",
  "created_at": "timestamp",
  "demographics": {
    "age_group": "string",
    "gender": "string",
    "education_level": "string",
    "education_field": "string",
    "occupation": "string",
    "transport_modes": ["array", "of", "strings"],
    "housing_type": "string",
    "urban_area": "string"
  },
  "demographics_completed_at": "timestamp",
  "preexploration": {
    "accessibility": 0-5,
    "proximity_avg_minutes": int,
    "proximity_max_minutes": int,
    "density": 0-5,
    "entropy": 0-5,
    "closeness": 0-5
  },
  "preexploration_completed_at": "timestamp",
  "selected_street": "string",
  "selected_coordinates": {
    "lat": float,
    "lon": float
  },
  "street_selected_at": "timestamp",
  "selected_categories": ["array", "of", "categories"],
  "travel_time": int,
  "travel_mode": "string",
  "categories_selected_at": "timestamp",
  "results_viewed_at": "timestamp",
  "postexploration": {
    "accessibility": 0-5,
    "proximity_avg_minutes": int,
    "proximity_max_minutes": int,
    "density": 0-5,
    "entropy": 0-5,
    "closeness": 0-5,
    "platform_understanding_help": 0-5,
    "opinion_revision": 0-5,
    "additional_comments": "string"
  },
  "postexploration_completed_at": "timestamp",
  "thanked_at": "timestamp",
  "current_step": int,
  "updated_at": "timestamp"
}
```

## Endpoint API

### Gestione Sessioni

- `POST /api/userstudy/session/create` → Crea nuova sessione
- `POST /api/userstudy/session/get` → Recupera dati sessione
- `POST /api/userstudy/session/complete` → Marca sessione come completata

### Questionari

- `POST /api/userstudy/demographics/submit` → Salva dati demografici
- `POST /api/userstudy/preexploration/submit` → Salva pre-esplorazione
- `POST /api/userstudy/postexploration/submit` → Salva post-esplorazione

### Selezioni

- `POST /api/userstudy/street/select` → Salva via selezionata
- `POST /api/userstudy/categories/select` → Salva categorie e impostazioni
- `POST /api/userstudy/results/viewed` → Registra visualizzazione risultati

### Admin

- `GET /api/userstudy/sessions/all` → Recupera tutte le sessioni (debug/analytics)

## Accesso

- **Punto di ingresso**: [http://localhost:8000/userstudy/welcome](http://localhost:8000/userstudy/welcome)
- **Entrypoint alternativo**: Puoi aggiungere un link dalla homepage principale

## Implementazione Tecnica

### Backend
- Framework: FastAPI
- Database: MongoDB
- Modelli: `UserStudySessionModel`, `DemographicsResponse`, `PreexplorationResponse`, `PostexplorationResponse`

### Frontend
- Linguaggio: HTML5 + JavaScript + Bootstrap 5
- Mappe: Leaflet.js
- Grafici: D3.js
- Geocoding: API Nominatim

### Gestione di Sessione
- Tipo: Anonimo (sessionId UUID)
- Storage: `sessionStorage` (browser) + MongoDB (server)
- Durata: Session lasts until browser closes (sessionStorage)

## Considerazioni per lo Sviluppo

1. **GDPR Compliance**: I dati sono completamente anonimizzati - non vengono salvati dati personali
2. **Accessibility**: Le pagine sono progettate con bootstrap e supportano screen reader
3. **Mobile**: Layout responsive per dispositivi mobili
4. **Error Handling**: Tutti gli endpoint hanno gestione degli errori
5. **User Experience**: Indicatori di progresso a ogni step, messaggi di errore chiari

## Testing del Flusso

Per testare il flusso completo:

1. Apri il browser e vai a `/userstudy/welcome`
2. Completa ogni step seguendo le istruzioni
3. Al termine, scarica o condividi i dati della sessione
4. Verifica in MongoDB che la sessione sia stata salvata
5. Usa l'endpoint admin `/api/userstudy/sessions/all` per visualizzare tutte le sessioni

## Troubleshooting

### Session not found error
- Assicurati che `sessionStorage` sia abilitato nel browser
- Elimina i cookies e prova di nuovo
- Controlla che il session_id sia valido

### Database connection error
- Verifica che MongoDB sia in esecuzione
- Controlla `MONGO_URL` in `backend/db.py`
- Verifica le credenziali

### API errors
- Controlla la console del browser per i messaggi di errore
- Verifica che FastAPI sia in esecuzione
- Controlla i log del backend
