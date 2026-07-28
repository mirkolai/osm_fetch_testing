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


""" Questo script genera i confini dei quartieri all’interno di ciascun comune, basandosi su un clustering dei nodi (incroci) della rete stradale pedonale (es. output/001001_walk.graphml.gz).

Il clustering è eseguito utilizzando Infomap, un algoritmo di community detection che individua gruppi di nodi connessi sulla base di percorsi di random walk.
In pratica, i nodi della rete vengono raggruppati in quartieri (neighbourhoods) coerenti dal punto di vista topologico e spaziale.

Per ogni comune, i risultati vengono salvati nella collezione [neighbourhood_polygon]

Struttura dei dati salvati

Ogni documento della collezione ha la seguente struttura:

{
    "PRO_COM_T": "<city_code>",
    "neighbourhoods": [
        {
            "id": "<neighbourhood_id>",
            "geometry": {
                "convex_hull": { ... },   // geometria dell’inviluppo convesso
                "concave_hull": { ... }   // geometria dell’inviluppo concavo
            },
            "nodes": [ ... ]              // lista dei nodi appartenenti al quartiere
        },
        ...
    ]
}


"""

# Create a connection using MongoClient. You can import MongoClient or use pymongo.MongoClient
client = MongoClient(utils.CONNECTION_STRING)
db = client[utils.MONGO_DB_NAME]  # Nome del database
collection = db["neighbourhood_polygon"]  # Nome della collezione


collection.drop()

collection.create_index([("PRO_COM_T", 1)], unique=True)


for gzip_filename in glob.glob("db_ingest/graphml/* walk.graphml.gz"):
    city_code =  gzip_filename.split("/")[-1].replace(" walk.graphml.gz", " ").strip()

    if not utils.should_process_city(city_code):
        print(f"Skip {city_code} (non in CITY_CODE_FILTER)")
        continue

    print(gzip_filename)


    G = ox.load_graphml(gzip_filename)


    neighborhoods, node_module = utils.compute_real_neighborhood(G)

    list_of_neighborhoods=[]

    # Dizionario per raggruppare chiavi per valore
    grouped_node_module = {}

    for key, value in node_module.items():

        # Se il valore non esiste nel dizionario di output, inizializza una lista
        if value not in grouped_node_module:
            grouped_node_module[value] = []

        # Aggiungi la chiave alla lista del valore corrispondente
        grouped_node_module[value].append(key)

    for neighborhood_id, geometries in neighborhoods.items():
        list_of_neighborhoods.append(
            {
                "id": neighborhood_id,
                "geometry": {
                    "convex_hull": geometries["convex_hull"].__geo_interface__,
                    "concave_hull":  geometries["concave_hull"].__geo_interface__,
                },
                "nodes": grouped_node_module[neighborhood_id],
            }
        )

    city_data = {
        "PRO_COM_T": city_code,
        "neighbourhoods": list_of_neighborhoods
    }

    # Inserisci nel database MongoDB
    try:
        collection.insert_one(city_data)  # Inserisce il documento
    except Exception as e:
        print(f"Errore nell'inserimento del comune {city_code}")


