from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import OperationFailure
import geopandas as gpd

from shapely.geometry import MultiPolygon, Polygon
import geopandas as gpd
import osmnx as ox
import networkx as nx
from db_ingest import utils
import glob


"""
Questo script genera i confini dei quartieri all’interno di ciascun comune,
basandosi su un clustering dei nodi della rete stradale pedonale.

I risultati vengono salvati nella collezione:
    neighbourhood_polygon

Struttura:

{
    "PRO_COM_T": "<city_code>",
    "neighbourhoods": [
        {
            "id": "<neighbourhood_id>",
            "geometry": {
                "convex_hull": { ... },
                "concave_hull": { ... }
            },
            "nodes": [ ... ]
        },
        ...
    ]
}
"""


# Connessione a MongoDB
client = MongoClient(utils.CONNECTION_STRING)
db = client[utils.MONGO_DB_NAME]
collection = db["neighbourhood_polygon"]


# NON cancelliamo la collezione.
# L'indice garantisce che possa esistere un solo documento
# per ogni comune.
collection.create_index([("PRO_COM_T", 1)], unique=True)


for gzip_filename in glob.glob("db_ingest/graphml/* walk.graphml.gz"):

    city_code = (
        gzip_filename
        .split("/")[-1]
        .replace(" walk.graphml.gz", "")
        .strip()
    )

    if not utils.should_process_city(city_code):
        print(f"Skip {city_code} (non in CITY_CODE_FILTER)")
        continue

    print(f"Processing {city_code}: {gzip_filename}")

    # Carica il grafo
    G = ox.load_graphml(gzip_filename)

    # Calcola i quartieri
    neighborhoods, node_module = utils.compute_real_neighborhood(G)

    # Raggruppa i nodi per quartiere
    grouped_node_module = {}

    for node_id, neighborhood_id in node_module.items():

        if neighborhood_id not in grouped_node_module:
            grouped_node_module[neighborhood_id] = []

        grouped_node_module[neighborhood_id].append(node_id)

    # Costruisce la lista dei quartieri
    list_of_neighborhoods = []

    for neighborhood_id, geometries in neighborhoods.items():

        list_of_neighborhoods.append(
            {
                "id": neighborhood_id,
                "geometry": {
                    "convex_hull": geometries["convex_hull"].__geo_interface__,
                    "concave_hull": geometries["concave_hull"].__geo_interface__,
                },
                "nodes": grouped_node_module.get(neighborhood_id, []),
            }
        )

    # Documento relativo al comune
    city_data = {
        "PRO_COM_T": city_code,
        "neighbourhoods": list_of_neighborhoods,
    }

    # Inserisce il documento se non esiste.
    # Se esiste già, lo aggiorna senza toccare gli altri comuni.
    try:

        result = collection.update_one(
            {"PRO_COM_T": city_code},
            {"$set": city_data},
            upsert=True,
        )

        if result.upserted_id is not None:
            print(f"  -> Comune {city_code} inserito")
        elif result.modified_count > 0:
            print(f"  -> Comune {city_code} aggiornato")
        else:
            print(f"  -> Comune {city_code} già aggiornato")

    except Exception as e:
        print(f"Errore nell'inserimento/aggiornamento del comune {city_code}: {e}")


client.close()

