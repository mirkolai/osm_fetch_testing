from pymongo.errors import DuplicateKeyError
import glob
import osmnx as ox
from pymongo import MongoClient
from pathlib import Path
import sys
from db_ingest import utils

"""
Questo script salva nella collezione MongoDB nodes tutte le informazioni relative agli incroci delle reti pedonali e ciclabili dei comuni italiani.

Lo scopo principale è permettere, ad esempio, di trovare rapidamente il nodo più vicino a un determinato punto geografico.

Dati in ingresso

Le reti vengono recuperate dalla cartella output, utilizzando il codice del comune come riferimento:

Tipo di rete	File di input
Percorso pedonale esteso	001001_walk_extended.graphml.gz
Percorso ciclabile esteso	001001_bike_extended.graphml.gz


Ogni documento nella collezione nodes contiene almeno le seguenti informazioni:

{
    "node_id": "<ID univoco del nodo>",
    "location": {
        "type": "Point",            // Formato GeoJSON
        "coordinates": [<lon>, <lat>]  // GeoJSON richiede [longitudine, latitudine]
    }
}

"""


# Create a connection using MongoClient. You can import MongoClient or use pymongo.MongoClient
client = MongoClient(utils.CONNECTION_STRING)
db = client[utils.MONGO_DB_NAME]  # Nome del database
collection = db["nodes"]  # Nome della collezione


collection.create_index("node_id", unique=True)
# Creare l'indice geospaziale su "location"
collection.create_index([("location", "2dsphere")])
print("Indice geospaziale 2dsphere creato su 'location'.")
for travel_type in utils.TRAVEL_SPEEDS.keys():
    for gzip_filename in glob.glob(f"db_ingest/graphml/* {travel_type} extended.graphml.gz"):
        city_code =  gzip_filename.split("/")[-1].replace(f" {travel_type} extended.graphml.gz", " ").strip()

        if not utils.should_process_city(city_code):
            print(f"Skip {city_code} (non in CITY_CODE_FILTER)")
            continue

        print(gzip_filename)


        graph = ox.load_graphml(gzip_filename)

        for node_id, data in graph.nodes(data=True):
            try:
                # Tenta di inserire il documento
                collection.insert_one({
                    "node_id": node_id,
                    "location": {  # Campo GeoJSON
                        "type": "Point",
                        "coordinates": [data["x"], data["y"]]  # GeoJSON richiede [lon, lat]
                    }
                })
            except DuplicateKeyError:
                ...
                # Ignora l'errore se il nodo esiste già


