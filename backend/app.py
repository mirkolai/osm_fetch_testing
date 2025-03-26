import logging
import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.RequestModels import *
from backend.Parameters import *
from backend.Poi import *
from backend.ReverseGeocoding import *
from backend.Isochrones import *
from backend.Nodes import *
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

@app.get("/discoverArea")
async def serve_discoverArea():
    file_path = os.path.join(VIEWS_DIR, "discoverArea.html")
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


@app.post("/api/get_isochrone")
def search_proximity(request: IsochroneRequest):
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


@app.post("/api/get_pois_isochrone")
def get_pois_data_in_isochrone(request: PoisRequest):
    """
    Endpoint per ottenere i POI dettagliati associati a un node_id.
    """

    logging.info(f"Valori coordinate per pois in isocrone: lat={request.coords.lat}, lon={request.coords.lon}")

    try:
        status_code1, message, node_id = get_id_node_by_coordinates(request.coords)

        if status_code1 == 200:
            logging.info("Nodo trovato, ottenimento POI...")

            status_code2, message2, pois_list, total_count = get_detailed_pois_by_node_id(
                node_id, request.min, request.vel, request.categories
            )

            if status_code2 == 200:
                # Se vuoi loggare o usare total_count qui, puoi farlo:
                logging.info(f"Numero totale di POI filtrati: {total_count}")
                # Ma al frontend ritorni solo la lista dei pois
                return pois_list
            else:
                # Se c'è un errore di altro tipo, lo gestisci come preferisci
                raise HTTPException(status_code=status_code2, detail=message2)

        else:
            # HTTP 404 o 500 se get_id_node_by_coordinates fallisce
            raise HTTPException(status_code=status_code1, detail=message)

    except HTTPException as http_exc:
        raise http_exc  # Rilancia l'errore HTTP senza modificarlo
    except Exception as e:
        logging.error(f"Errore inatteso: {str(e)}")
        raise HTTPException(status_code=500, detail="Errore interno del server")


@app.post("/api/get_isochrone_parameters")
def get_isochrone_parameters(req: PoisRequest):
    """
    Esempio di rotta che calcola i parametri di isocrona
    """
    try:
        status_code1, message, node_id = get_id_node_by_coordinates(req.coords)
        status_code, message, iso_resp = get_isocronewalk_by_node_id(
            node_id=node_id,
            minute=req.min,
            velocity=req.vel
        )
        # iso_resp ha la shape: { "node_id":..., "convex_hull": { "coordinates": [...], ... } }
        if not iso_resp or "convex_hull" not in iso_resp:
            raise HTTPException(status_code=404, detail="Isochrone not found")

        # 2) /api/get_pois_isochrone
        status_code2, message2, pois_resp, total_count = get_detailed_pois_by_node_id(
            node_id, req.min, req.vel, req.categories
        )

        if not isinstance(pois_resp, list):
            raise HTTPException(status_code=404, detail="PoIs not found")

        print("Entra")
        # 3) Calcolo parametri
        result = compute_isochrone_parameters(
            pois_data=pois_resp,
            isochrone_data=iso_resp,
            vel=req.vel,
            total_pois=total_count,
            max_minutes=60,
            categories=req.categories
        )
        return result

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


######## API DI TESTING

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


# Endpoint per trovare il poi specifico date le coordinate
@app.post("/api/pois/test_single_poi/")
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
            "lon": poi["location"]["coordinates"][1]  # Estrae longitudine
        }
    else:
        raise HTTPException(status_code=404, detail="No node found at the given coordinates.")
