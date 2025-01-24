import logging
import os
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.ReverseGeocoding import reverse_geocoding, Place
from backend.Isochrones import get_isocronewalk_by_node_id
from backend.Nodes import get_id_node_by_coordinates
from backend.db import db

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

class IsochroneRequest(BaseModel):
    node_id: int
    minute: int
    velocity: int

class SearchProximityRequest(BaseModel):
    coords: Coordinates
    min: int
    vel: int


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

@app.post("/api/search_proximity")
def search_proximity(request: SearchProximityRequest):
    logging.info(f"Valori coordinate per isocrona walk: lat={request.coords.lat}, lon={request.coords.lon}")

    try:
        status_code1, message, node_id = get_id_node_by_coordinates(request.coords)

        if status_code1 == 200:
            print("Nodo trovato")
            status_code, message, result = get_isocronewalk_by_node_id(
                node_id=node_id,
                minute=request.min,
                velocity=request.vel
            )
            if status_code == 200:
                return result
            else:
                raise HTTPException(status_code=status_code, detail=message)
        else:
            raise HTTPException(status_code=status_code1, detail=message)

    except HTTPException as http_exc:
        # Rilancia l'eccezione HTTP senza modifiche
        raise http_exc
    except Exception as e:
        # Log dell'errore non HTTP e restituzione di un errore generico
        logging.error(f"Errore inatteso: {str(e)}")
        raise HTTPException(status_code=500, detail="Errore interno del server")



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
    


######## API DI TESTING

@app.post("/api/get_isochrone_walk")
async def get_isochrone_walk(request: IsochroneRequest):
    """
    Estrae l'isocrona camminabile in base ai parametri forniti.

    Parametri:
    ----------
    - **request**: `IsochroneRequest`
        - `node_id` (int): ID del nodo.
        - `minute` (int): Minuti per calcolare l'isocrona.
        - `velocity` (int): Velocità di spostamento.

    Risposta:
    ---------
    Un dizionario contenente:
    - `node_id`: ID del nodo.
    - `concave_hull`: Dettagli sulla geometria del percorso (coordinate e bounding box).

    Errori:
    -------
    - **404**: Dati non trovati.
    - **500**: Errore interno.

    """
    try:
        status_code, message, result = get_isocronewalk_by_node_id(
            node_id=request.node_id,
            minute=request.minute,
            velocity=request.velocity
        )

        if status_code == 200:
            return result
        else:
            raise HTTPException(status_code=status_code, detail=message)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint per trovare il nodo più vicino a un punto specifico
@app.post("/api/nodes/nearest/")
async def find_nearest_node(coords: Coordinates):
    collection = db["nodes"]
    nearest_node = collection.find_one({
        "location": {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [coords.lon, coords.lat]  # GeoJSON [lon, lat]
                }
            }
        }
    })

    if nearest_node:
        return {
            "node_id": nearest_node["node_id"],
            "lat": nearest_node['location']['coordinates'][1],
            "lon": nearest_node['location']['coordinates'][0]
        }
    else:
        raise HTTPException(status_code=404, detail="No node found near the given point.")

@app.post("/api/get_node_id")
async def get_node_id(coords: Coordinates):
    """
    Get node_id from coordinates
    """
    try:
        status_code, message, node_id = get_id_node_by_coordinates(coords)
        if status_code == 200:
            return {"node_id": node_id}
        else:
            raise HTTPException(status_code=status_code, detail=message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint per trovare il poi specifico date le coordinate
@app.post("/api/pois/single_poi/")
async def find_poi_by_coordinates(coords: Coordinates):
    collection = db["pois"]

    # Query per trovare il primo nodo con le coordinate esatte
    poi = collection.find_one({
        "location.coordinates": [coords.lat, coords.lon]  # attenzione a posizionamento lat/lon
    })

    print("Query result:", poi)

    if poi:
        return {
            "pois_id": poi["pois_id"],
            "name": poi["names"]["primary"],
            "categories": poi["categories"]["primary"],
            "lat": poi["location"]["coordinates"][0],  # Estrae latitudine
            "lon": poi["location"]["coordinates"][1]   # Estrae longitudine
        }
    else:
        raise HTTPException(status_code=404, detail="No node found at the given coordinates.")