import logging
import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.RequestModels import *
from backend.Parameters import *
from backend.Poi import *
from backend.ReverseGeocoding import *
from backend.Isochrones import *
from backend.Nodes import *
from backend.Neighbourhoods import *
from backend.db import db
from backend.auth import create_access_token, get_current_user
from backend.users import create_user, authenticate_user, update_user_preferences, get_user_preferences

logging.basicConfig(
    #level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

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
    """
        Ritorna la pagina principale del frontend.

        ### Dettagli
        Questa rotta serve il file `index.html` dal progetto frontend, se presente.
        Utilizzata principalmente per l’accesso iniziale all’applicazione.

        ### Response
        - **200**: Restituisce la pagina HTML se il file esiste.
        - **404**: Restituisce un JSON con `{"error": "File not found"}` se non esiste il file `index.html`.

        ### Esempio di utilizzo
        ```bash
        # GET sulla root dell'app
        curl -X GET http://localhost:8000/
        ```
    """
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

@app.get("/compareAreas")
async def serve_compareAreas():
    file_path = os.path.join(VIEWS_DIR, "compareAreas.html")
    if not os.path.exists(file_path):
        return {"error": "File not found", "path": file_path}
    return FileResponse(file_path)

@app.get("/personalArea")
async def serve_personalArea():
    file_path = os.path.join(VIEWS_DIR, "personal.html")
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
    """
        Calcola e restituisce i dati dell'isocrona di tipo "walk" per un punto specifico.

        ### Dettagli
        - Prende in ingresso latitudine, longitudine, minuti e velocità per eseguire il calcolo dell'isocrona a piedi.
        - Prima individua il `node_id` del nodo più vicino alle coordinate fornite.
        - Successivamente calcola l'isocrona corrispondente in base a **min** e **vel**.

        ### Parametri:
        - **request**: `IsochroneRequest`
          - `coords` (Coordinates): latitudine e longitudine del punto di partenza.
          - `min` (int): minuti per i quali calcolare l'isocrona.
          - `vel` (int): velocità (in km/h).

        ### Esempio di chiamata
        ```bash
        curl -X POST \\
            -H "Content-Type: application/json" \\
            -d '{
                "coords": {"lat": 45.0703, "lon": 7.6869},
                "min": 10,
                "vel": 3
            }' \\
            http://localhost:8000/api/get_isochrone
        ```

        ### Esempio di risposta
        ```json
        {
            "node_id": 1227233452,
            "convex_hull": {
                "coordinates": [
                    [
                        [
                            7.6792319,
                            45.0608158
                        ],
                        ...
                    ]
                ],
                "bbox": [
                    7.6738336,
                    45.0608158,
                    7.6910168,
                    45.0733403
                ]
            }
        }
        ```

        ### Errori:
        - **404**: Nodo non trovato o isocrona non disponibile.
        - **500**: Errore interno del server.
    """
    logging.info(f"Valori coordinate per isocrona walk: lat={request.coords.lat}, lon={request.coords.lon}")

    try:
        status_code1, message, node_id = get_id_node_by_coordinates(request.coords)

        if status_code1 == 200:
            #print("Nodo trovato",node_id)
            status_code, message, result = get_isocronewalk_by_node_id(
                node_id=node_id,
                minute=request.min,
                velocity=request.vel
            )
            #print(status_code, message, result )
            #print(1)
            if status_code == 200:
                #print(2)
                #print(result)
                return result
            else:
                #print(3)
                raise HTTPException(status_code=status_code, detail=message)
            #print(4)

        else:
            raise HTTPException(status_code=status_code1, detail=message)

    except HTTPException as http_exc:
        # Rilancia l'eccezione HTTP senza modifiche
        print(http_exc)
        raise http_exc
    except Exception as e:
        # Log dell'errore non HTTP e restituzione di un errore generico
        #print(5)
        logging.error(f"Errore inatteso 5: {str(e)}")
        raise HTTPException(status_code=500, detail="Errore interno del server")


@app.post("/api/get_pois_isochrone")
def get_pois_data_in_isochrone(request: PoisRequest):
    """
            Restituisce la lista dei POI (Points Of Interest) raggiungibili entro una certa isocrona a piedi.

            ### Dettagli
            - Prende in ingresso le coordinate iniziali, il tempo (in minuti), la velocità (km/h) e le categorie richieste.
            - Dato il nodo più vicino (in base alle coordinate), restituisce la lista di POI filtrati in base alla distanza massima
              percorribile e alle categorie fornite.

            ### Parametri:
            - **request**: `PoisRequest`
              - `coords` (Coordinates): Coordinate di latitudine e longitudine.
              - `min` (int): Numero di minuti per l'isocrona.
              - `vel` (int): Velocità di percorrenza (km/h).
              - `categories` (List[str]): Lista di categorie da filtrare.

            ### Esempio di chiamata
            ```bash
            curl -X POST \\
                -H "Content-Type: application/json" \\
                -d '{
                    "coords": {"lat": 45.0703, "lon": 7.6869},
                    "min": 15,
                    "vel": 5,
                    "categories": ["restaurant","beauty_and_spa"]
                }' \\
                http://localhost:8000/api/get_pois_isochrone
            ```

            ### Esempio di risposta
            ```json
            [
                {
                    "poi_id": "08f1f984030131a103c98f5eca19fbd9",
                    "distance": 201.467,
                    "location": {
                        "type": "Point",
                        "coordinates": [
                            7.6823526,
                            45.068414
                        ]
                    },
                    "names": {
                        "common": null,
                        "primary": "Scat_to",
                        "rules": null
                    },
                    "categories": {
                        "primary": "restaurant",
                        "alternate": null
                    }
                },
                {
                    "poi_id": "08f1f9840301875b03a8ad08e477a497",
                    "distance": 207.983,
                    "location": {
                        "type": "Point",
                        "coordinates": [
                            7.6835984,
                            45.0683603
                        ]
                    },
                    ...
                }
            ]
            ```

            ### Errori:
            - **404**: Nodo non trovato o nessun POI disponibile.
            - **500**: Errore interno del server.
    """
    logging.info(f"Valori coordinate per pois in isocrone: lat={request.coords.lat}, lon={request.coords.lon}")
    #print("get_pois_isochrone ")
    try:
        status_code1, message, node_id = get_id_node_by_coordinates(request.coords)
        #print("get_id_node_by_coordinates ",status_code1,node_id)

        if status_code1 == 200:
            logging.info("Nodo trovato, ottenimento POI...")
            #print("Nodo trovato, ottenimento POI...")

            status_code2, message2, pois_list, total_count = get_detailed_pois_by_node_id(
                node_id, request.min, request.vel, request.categories
            )
            #print("get_detailed_pois_by_node_id ", status_code2, node_id)

            if status_code2 == 200:
                # Se vuoi loggare o usare total_count qui, puoi farlo:
                logging.info(f"Numero totale di POI filtrati: {total_count}")
                #print(f"Numero totale di POI filtrati: {total_count}")
                # Ma al frontend ritorni solo la lista dei pois
                return pois_list
            else:
                print(f"errore di altro tipo 90")

                # Se c'è un errore di altro tipo, lo gestisci come preferisci
                raise HTTPException(status_code=status_code2, detail=message2)

        else:
            print(f"errore di altro tipo 91")

            # HTTP 404 o 500 se get_id_node_by_coordinates fallisce
            raise HTTPException(status_code=status_code1, detail=message)

    except HTTPException as http_exc:
        raise http_exc  # Rilancia l'errore HTTP senza modificarlo
    except Exception as e:
        logging.error(f"Errore inatteso 92: {str(e)}")
        raise HTTPException(status_code=500, detail="Errore interno del server")


@app.post("/api/get_isochrone_parameters")
def get_isochrone_parameters(req: PoisRequest):
    """
        Calcola alcuni parametri avanzati per l'isocrona, tra cui:
        - Proximity
        - Density
        - Entropy
        - Poi Accessibility

        ### Dettagli
        1. Calcola l'isocrona in base a **coords**, **min** e **vel**.
        2. Recupera i POI entro l'isocrona.
        3. Calcola parametri di area, prossimità, densità e varietà di POI (entropy).

        ### Parametri:
        - **req**: `PoisRequest`
          - `coords` (Coordinates): latitudine e longitudine
          - `min` (int): minuti per cui calcolare l'isocrona
          - `vel` (int): velocità di percorrenza (km/h)
          - `categories` (List[str]): categorie di interesse per valutare i parametri

        ### Esempio di chiamata
        ```bash
        curl -X POST \\
            -H "Content-Type: application/json" \\
            -d '{
                "coords": {"lat": 45.0703, "lon": 7.6869},
                "min": 15,
                "vel": 5,
                "categories": ["restaurant","beauty_and_spa"]
            }' \\
            http://localhost:8000/api/get_isochrone_parameters
        ```

        ### Esempio di risposta
        ```json
        {
            "proximity": 19.74864,
            "proximity_score": 0.32914400000000005,
            "density_score": 1,
            "entropy_score": 0.06265984760267532,
            "closeness": 0.8043968515904784,
            "poi_accessibility": 0.4639346158675585
        }
        ```

        ### Errori:
        - **404**: Isocrona o POI non trovati.
        - **500**: Errore interno del server.
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
        #print("2) /api/get_pois_isochrone")
        status_code2, message2, pois_resp, total_count = get_detailed_pois_by_node_id(
            node_id, req.min, req.vel, req.categories
        )
        print("2.5)     if not isinstance(pois_resp, list):")

        if not isinstance(pois_resp, list):
            raise HTTPException(status_code=404, detail="PoIs not found")

        #print("Entra")
        # 3) Calcolo parametri
        #print("3) Calcolo parametri")

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
        Restituisce il `node_id` di rete stradale più vicino alle coordinate fornite.

        ### Dettagli
        - Prende in ingresso coordinate (lat, lon) e ricerca nel database il nodo (nella collezione `nodes`)
          geograficamente più vicino.

        ### Parametri:
        - **coords**: `Coordinates`
          - `lat` (float): latitudine
          - `lon` (float): longitudine

        ### Response
        - Restituisce un dizionario contenente `{"node_id": <valore>}` se trovato.

        ### Esempio di utilizzo
        ```bash
        curl -X POST \\
            -H "Content-Type: application/json" \\
            -d '{
                "lat": 45.0703,
                "lon": 7.6869
            }' \\
            http://localhost:8000/api/get_node_id
        ```

        ### Errori:
        - **404**: Nessun nodo trovato nelle vicinanze.
        - **500**: Errore interno del server.
    """
    try:
        status_code, message, node_id = get_id_node_by_coordinates(coords)
        if status_code == 200:
            return {"node_id": node_id}
        else:
            raise HTTPException(status_code=status_code, detail=message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/get_all_neighbourhoods")
async def get_all_neighbourhoods_endpoint(city: str = None):
    """
    Restituisce tutti i quartieri disponibili nel database per una città specifica.

    ### Dettagli
    - Recupera tutti i quartieri dalla collezione `neighbourhood_polygon`.
    - Valida che la città richiesta sia supportata (attualmente solo Torino).
    - Converte le coordinate da formato MongoDB [lon, lat] a formato Leaflet [lat, lon].
    - Restituisce i dati strutturati per la visualizzazione su mappa.

    ### Parametri:
    - **city** (str, opzionale): Nome della città per cui recuperare i quartieri

    ### Response
    Lista di oggetti quartiere contenenti:
    - `id`: ID del quartiere
    - `coordinates`: Array di coordinate del poligono in formato Leaflet
    - `bbox`: Bounding box del quartiere
    - `properties`: Proprietà aggiuntive del quartiere

    ### Esempio di utilizzo
    ```bash
    curl -X GET "http://localhost:8000/api/get_all_neighbourhoods?city=Torino"
    ```

    ### Esempio di risposta
    ```json
    [
        {
            "id": 1,
            "coordinates": [
                [
                    [45.0703, 7.6869],
                    [45.0704, 7.6870],
                    ...
                ]
            ],
            "bbox": [7.6869, 45.0703, 7.6870, 45.0704],
            "properties": {}
        }
    ]
    ```

    ### Errori:
    - **404**: Nessun quartiere trovato per la città specificata o città non supportata.
    - **500**: Errore interno del server.
    """
    try:
        status_code, message, neighbourhoods = get_all_neighbourhoods(city)
        if status_code == 200:
            return neighbourhoods
        else:
            raise HTTPException(status_code=status_code, detail=message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/get_neighbourhoods_by_coordinates")
async def get_neighbourhoods_by_coordinates_endpoint(coords: Coordinates):
    """
    Trova i quartieri che contengono un punto specifico.

    ### Dettagli
    - Prende in ingresso coordinate (lat, lon) e ricerca i quartieri che contengono quel punto.
    - Se la query geospaziale fallisce, restituisce tutti i quartieri disponibili.

    ### Parametri:
    - **coords**: `Coordinates`
      - `lat` (float): latitudine
      - `lon` (float): longitudine

    ### Response
    Lista di oggetti quartiere che contengono il punto specificato.

    ### Esempio di utilizzo
    ```bash
    curl -X POST \\
        -H "Content-Type: application/json" \\
        -d '{
            "lat": 45.0703,
            "lon": 7.6869
        }' \\
        http://localhost:8000/api/get_neighbourhoods_by_coordinates
    ```

    ### Errori:
    - **404**: Nessun quartiere trovato per le coordinate specificate.
    - **500**: Errore interno del server.
    """
    try:
        status_code, message, neighbourhoods = get_neighbourhoods_by_coordinates(coords.lat, coords.lon)
        if status_code == 200:
            return neighbourhoods
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

    #print("Query result:", poi)

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


######## AUTHENTICATION ENDPOINTS

@app.post("/api/auth/register", response_model=User)
async def register_user(user: UserCreate):

    try:
        created_user = create_user(user) # crea l'utente nel db, se gia presente ritorna None
        if created_user:
            return created_user
        else:
            raise HTTPException(status_code=400, detail="Email already registered")
    except HTTPException: #bubbling up dell'errore
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/auth/token", response_model=Token)
async def login_user(user: UserLogin):
    # autentica e restituisce JWT token
    
    try:
        # Verifica credenziali utente nel database
        authenticated_user = authenticate_user(user.email, user.password)
        if not authenticated_user:
            # Se credenziali non valide, restituisce errore 401
            raise HTTPException(
                status_code=401,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Crea token JWT con l'email 
        access_token = create_access_token(data={"sub": authenticated_user.email})
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/auth/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)): # Depends: prima di tutto esegue get_current_user, che usa come parametro
    # il parametro current_user è di tipo User
    """
    richiede autenticazione JWT
    Restituisce le informazioni dell'utente corrente
    
    ### Headers:
    - **Authorization**: Bearer <token>
    
    """
    return current_user


# semplicemente chiama update_user_preferences
@app.post("/api/auth/preferences")
async def save_user_preferences(
    preferences: UserPreferences,
    current_user: User = Depends(get_current_user)
):
    """
    Save user preferences (time, travel mode, services)
    Requires authentication
    
    ### Body:
    - **min** (int): time in minutes (5, 10, 15, 20)
    - **vel** (int): velocity in km/h (3, 5, 12, 20)
    - **categories** (List[str]): array of service IDs
    """
    try:
        success = update_user_preferences(current_user.email, preferences.model_dump()) # salva nel db l'oggetto dizionario
        if success:
            return {"message": "Preferences saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save preferences")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/auth/preferences", response_model=UserPreferences)
async def get_user_preferences_endpoint(current_user: User = Depends(get_current_user)):
    """
    Get user preferences (time, travel mode, services)
    Requires authentication
    """

    try:
        preferences = get_user_preferences(current_user.email)
        if preferences:
            return UserPreferences(**preferences)
        else:
            # se non trova le preferenze, restituisce le default
            return UserPreferences(
                min=15,
                vel=5,
                categories=[]
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
