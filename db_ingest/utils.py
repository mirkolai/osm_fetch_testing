import os
from pathlib import Path

from pyproj import Transformer
import networkx as nx
import geopandas as gpd
from shapely.geometry import MultiPoint
from infomap import Infomap

_ENV_LOADED = False


def _load_env_file():
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

    _ENV_LOADED = True


def get_env(name, default=None):
    _load_env_file()
    return os.getenv(name, default)


# Mongo usato dagli script ingest lanciati in locale.
CONNECTION_STRING = get_env("MONGO_URL_LOCAL", get_env("MONGO_URL", "mongodb://user:pass@localhost:27017"))
MONGO_DB_NAME = get_env("MONGO_DB", "15minute")
#walking 5 km
#cycling 12.5 and 26.5 km/h


TRAVEL_SPEEDS={
    "walk":[3,5],
    "bike":[12,20]
}
TRAVEL_TIMES={
    "walk":[5,10,15,20],
    "bike":[5,10,15,20]
}

MAX_TRAVEL_TIME=max(max(times) for times in TRAVEL_TIMES.values())
MAX_TRAVEL_SPEED=max(max(speeds) for speeds in TRAVEL_SPEEDS.values())


def _parse_city_code_filter() -> list:
    """Legge CITY_CODE_FILTER da .env come lista di codici ISTAT (separati da virgola).
    
    Esempio in .env:
        CITY_CODE_FILTER=001272,001001,001002
    
    Se vuota o non impostata, tutti i comuni vengono processati.
    """
    raw = get_env("CITY_CODE_FILTER", "").strip()
    if not raw:
        return []
    return [code.strip().zfill(6) for code in raw.split(",") if code.strip()]


# Lista di codici ISTAT da processare (vuota = tutti i comuni).
CITY_CODE_FILTER: list = _parse_city_code_filter()


def should_process_city(city_code: str) -> bool:
    """Ritorna True se il comune deve essere processato.
    
    Se CITY_CODE_FILTER è vuota, processa tutti i comuni.
    Altrimenti processa solo i comuni con codice ISTAT nella lista.
    """
    if not CITY_CODE_FILTER:
        return True
    normalized = str(city_code).strip().zfill(6)
    return normalized in CITY_CODE_FILTER


def get_extended_bebop_from_graph(G, max_distance_meters):
    """
    Obtain an extended Bounding Box of Points (BeBOP) from a graph.

    Parameters:
    subG (networkx.Graph): The graph from which to compute the BeBOP.
    max_distance_meters (float): Maximum distance to extend the bounding box by, in meters.

    Returns:
    shapely.geometry.box: The extended bounding box.
    """
    # Extract node coordinates (longitude, latitude)
    node_coords = [(data['x'], data['y']) for _, data in G.nodes(data=True)]

    if len(node_coords) == 0:
        raise ValueError("The graph has no nodes.")

    # Create the initial bounding box
    min_x, min_y, max_x, max_y = (min(p[0] for p in node_coords),
                                  min(p[1] for p in node_coords),
                                  max(p[0] for p in node_coords),
                                  max(p[1] for p in node_coords))

    # Convert bounding box coordinates to projected coordinates (meters)
    transformer = Transformer.from_crs("epsg:4326", "epsg:3857", always_xy=True)
    min_x_proj, min_y_proj = transformer.transform(min_x, min_y)
    max_x_proj, max_y_proj = transformer.transform(max_x, max_y)

    # Extend the bounding box in projected coordinates
    buffer_x = max_distance_meters
    buffer_y = max_distance_meters

    min_x_proj -= buffer_x
    max_x_proj += buffer_x
    min_y_proj -= buffer_y
    max_y_proj += buffer_y

    # Convert extended bounding box back to geographic coordinates
    min_x, min_y = transformer.transform(min_x_proj, min_y_proj, direction='INVERSE')
    max_x, max_y = transformer.transform(max_x_proj, max_y_proj, direction='INVERSE')

    # OSMnx 2 expects bbox as (left, bottom, right, top)
    extended_bbox = (min_x, min_y, max_x, max_y)

    return extended_bbox


def get_bbox_from_graph(G):
    """
    Calcola il bounding box da un grafo OSMnx.

    Args:
        G (networkx.MultiDiGraph): Il grafo caricato da OSMnx.

    Returns:
        tuple: Bounding box come (west, south, east, north).
    """
    # Estrai le coordinate dei nodi
    lons = [data['x'] for node, data in G.nodes(data=True)]
    lats = [data['y'] for node, data in G.nodes(data=True)]

    # Calcola i limiti
    west = min(lons)
    east = max(lons)
    south = min(lats)
    north = max(lats)

    return west, south, east, north


import subprocess


# Funzione per eseguire il comando e ottenere l'output in una variabile
def run_overture_download(filename, west, south, east, north):
    # Definisci il comando
    command = [
        "overturemaps",
        "download",
        "--bbox", f"{west},{south}, {east}, {north}",  # BBox per il bounding box
        "-f", "geojson",  # Formato di output
        "--type", "place",  # Tipo di dati da scaricare
        "-o", filename  # Nome del file di output
    ]

    # Esegui il comando e cattura l'output
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)

        print("Comando eseguito con successo!")

        return  True
    except subprocess.CalledProcessError as e:
        print(f"Errore nell'esecuzione del comando: {e}")
        print("Error output:", e.stderr)  # Mostra eventuali errori
        return False  # Se c'è un errore, restituisci False


def trova_citta_per_punto(collection,lon, lat):
    # Crea il punto da cercare
    point = {"type": "Point", "coordinates": [lon, lat]}

    # Esegui la query geospaziale
    results = collection.find({
        "geometry": {
            "$geoIntersects": {
                "$geometry": point
            }
        }
    })

    # Restituisci i risultati (i codici delle città)
    for result in results:
        print(f"Codice Comune: {result['PRO_COM_T']}, Nome Comune: {result['COMUNE']}")


def compute_real_neighborhood(G):

    max_depth = 3


    mapping_realid2fakeid = {}
    mapping_fakeid2realid = {}
    for i, node in enumerate(G.nodes()):
        mapping_realid2fakeid[node] = i
        mapping_fakeid2realid[i] = node

    # Percentuale minima per cluster
    MIN_PERCENTAGE = 5 #!!!!!!!

    # Numero totale di nodi
    total_nodes = G.number_of_nodes()
    #print(f"Totale nodi: {total_nodes}")


    # Identifica le componenti connesse
    connected_components = list(nx.connected_components(G.to_undirected()))

    # Filtra le componenti significative
    significant_components = [
        component for component in connected_components
        if len(component) / total_nodes * 100 >= MIN_PERCENTAGE
    ]

    #print(f"Numero totale di componenti: {len(connected_components)}")
    #print(f"Componenti significative (>{MIN_PERCENTAGE}%): {len(significant_components)}")
    hulls = {}
    node_modules = {}
    count_modules=0
    modules = {}

    # Itera sulle componenti connesse significative
    for component_idx, component in enumerate(significant_components):
        #print(f'Analizzo la componente connessa {component_idx + 1}/{len(significant_components)}...')
        #print(f'ci sono  {len(component)} nodi...')
        subgraph = G.subgraph(component)
        H = nx.relabel_nodes(subgraph, mapping_realid2fakeid, copy=True)
        im = Infomap(silent=True, seed=1987)
        im.add_networkx_graph(H, weight="length")
        im.run()
        if max_depth>im.max_depth:
            max_depth=im.max_depth
        depth=1
        while depth < max_depth:
            #print(depth)

            nodes = im.get_nodes(depth_level=depth)
            #print(component_idx,depth,len(set(im.get_modules(depth_level=depth).values())))
            if len(set(im.get_modules(depth_level=depth).values()))>3 or depth==max_depth:
                #print("salva")

                for node in nodes:
                    #print(node.module_id,node.module_id + count_modules)
                    node_modules[str(mapping_fakeid2realid[node.node_id])] = node.module_id + count_modules

                    if node.module_id + count_modules not in modules:
                        modules[node.module_id + count_modules] = []
                    modules[node.module_id + count_modules].append((G._node[mapping_fakeid2realid[node.node_id]]['x'],
                                                                    G._node[mapping_fakeid2realid[node.node_id]]['y']))
                for module_id, points in modules.items():

                    if module_id not in hulls:
                        hulls[module_id] = {}

                    s = gpd.GeoSeries([MultiPoint(points)], crs='EPSG:4326')
                    hull = s.convex_hull
                    hulls[module_id ]['convex_hull'] = hull
                    hull = s.concave_hull(ratio=0.1)
                    hulls[module_id ]['concave_hull'] = hull
                #print(node_modules)

                count_modules += len(modules)
                depth=max_depth
            depth+=1


    #print(len(hulls.keys()))
    return hulls, node_modules