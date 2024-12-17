import os
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pymongo import MongoClient

from backend.ReverseGeocoding import reverse_geocoding, Place

app = FastAPI()

# Calcolo corretto dei percorsi basato sulla tua struttura
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
PUBLIC_DIR = os.path.join(FRONTEND_DIR, "public")
VIEWS_DIR = os.path.join(FRONTEND_DIR, "views")

# Monta i file statici
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")
app.mount("/views", StaticFiles(directory=VIEWS_DIR), name="views")

# Modello per i dati del nodo
class Node(BaseModel):
    node_id: int
    lat: float
    lon: float


class Coordinates(BaseModel):
    lat: float
    lon: float


class ReverseGeocodingRequest(BaseModel):
    text: str

@app.get("/")
async def serve_frontend():
    file_path = os.path.join(VIEWS_DIR, "index.html")
    if not os.path.exists(file_path):
        return {"error": "File not found", "path": file_path}
    return FileResponse(file_path)


@app.get("/search")
async def serve_search():
    file_path = os.path.join(VIEWS_DIR, "search.html")
    if not os.path.exists(file_path):
        return {"error": "File not found", "path": file_path}
    return FileResponse(file_path)


@app.post("/api/reverse_geocoding")
def app_reverse_geocoding(request: ReverseGeocodingRequest) -> List[Place]:
    """
    Ricerca indirizzi tramite Nominatim e restituisce la posizione geocodificata.

    Questo endpoint consente di cercare indirizzi utilizzando un input di testo (ad esempio, una città).
    L'implementazione utilizza il servizio di geocoding Nominatim basato su OpenStreetMap.

    Parametri:
    ----------
    - **request**: `ReverseGeocodingRequest`
        - `text` (str): Città o query per effettuare la ricerca.

    Risposta:
    ---------
    Una lista di oggetti `Place` contenente:
    - `name` (str): Nome dell'indirizzo o luogo.
    - `importance` (float): Indicatore di rilevanza.
    - `coordinates` (List[float]): Latitudine e longitudine (es. `[44.826012649999996, 8.202686328987273]`).

    Risposta di esempio:
    ---------------------
    ```json
    [
        {
            "name": "Asti, Piemonte, Italia",
            "importance": 0.7086021965813384,
            "coordinates": [
                44.826012649999996,
                8.202686328987273
            ]
        },
        {
            "name": "Asti, Piemonte, 14100, Italia",
            "importance": 0.5965846969089829,
            "coordinates": [
                44.900542,
                8.2068876
            ]
        }
    ]
    ```

    Errori:
    -------
    - **400**: Parametri non validi.
    - **500**: Errore interno o servizio Nominatim non disponibile.

    Eccezioni:
    ----------
    In caso di errore, restituisce un oggetto `HTTPException` con dettagli sul problema.

    """
    status_code, message, result = reverse_geocoding(request.text)

    if status_code == 200:
        return result
    else:
        raise HTTPException(status_code=status_code,
                            detail=[{
                                "loc": [],
                                "msg": message,
                                "type": status_code}])
