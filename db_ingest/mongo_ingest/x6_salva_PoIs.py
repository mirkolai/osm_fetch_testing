from tkinter.font import names

from pymongo.errors import DuplicateKeyError
import glob
import osmnx as ox
from pymongo import MongoClient
import geopandas as gpd
from pathlib import Path
import numpy as np

from db_ingest import utils

"""
Questo script importa i Point of Interest di ciascun comune nella collezione MongoDB [pois].

Obiettivo:
- Salvare tutte le informazioni sui PoI in un database MongoDB.
- Consentire query geospaziali, come trovare i PoI più vicini a un determinato punto geografico.
- Gestire duplicati tramite un indice unico su `pois_id`.

Dati in ingresso:
-----------------
- File Feather compressi nella cartella `output` con pattern:
  "{city_code}_PoI.feather.zstd"
- Ogni file contiene almeno:
    - `id`: identificativo del PoI
    - `geometry`: punto geografico
    - `names`: nomi del PoI
    - `categories`: categorie primarie e secondarie

Struttura dei documenti MongoDB:
--------------------------------
{
    "pois_id": "<ID univoco del PoI>",
    "location": { 
        "type": "Point",
        "coordinates": [<lon>, <lat>]  # GeoJSON
    },
    "names": {...},
    "categories": {
        "primary": "...",
        "alternate": ["...", "..."]
    }
}


"""


# Create a connection using MongoClient. You can import MongoClient or use pymongo.MongoClient
client = MongoClient(utils.CONNECTION_STRING)
db = client[utils.MONGO_DB_NAME]  # Nome del database
collection = db["pois"]  # Nome della collezione

collection.create_index([("pois_id", 1)], unique=True)

# Creare l'indice geospaziale su "location"
collection.create_index([("location", "2dsphere")])

for gzip_filename in glob.glob(f"db_ingest/graphml/* PoI.feather.zstd"):
    city_code =  gzip_filename.split("/")[-1].replace(f" PoI.feather.zstd", " ").strip()

    if not utils.should_process_city(city_code):
        print(f"Skip {city_code} (non in CITY_CODE_FILTER)")
        continue
    poi_data=gpd.read_feather(gzip_filename)
    print(city_code)
    services = [
        {"id": feature["id"],
         "lat": feature["geometry"].x,
         "lon": feature["geometry"].y,
         "names": feature["names"],
         "categories": feature["categories"]
         }
        for _, feature in poi_data.iterrows()
    ]

    services_gdf = gpd.GeoDataFrame(
        services,
        geometry=gpd.points_from_xy([s["lon"] for s in services], [s["lat"] for s in services]),
        crs="EPSG:4326"
    )
    for _, data in services_gdf.iterrows():
        try:

            if data["categories"] is None:
                primary = None
                alternate = None
            elif data["categories"]["alternate"] is None:
                primary = data["categories"]["primary"]
                alternate = None
            else:
                primary = data["categories"]["primary"]
                alternate = [x for x in data["categories"]["alternate"]]

            # Tenta di inserire il documento
            print(f"Inserisco il PoI con ID {data['id']}")
            print(f"Coordinate: {data['lon']}, {data['lat']}")
            print(f"Primary: {primary}, Alternate: {alternate}")
            print(f"Names: {data['names']}")
            if isinstance(data["names"].get("rules"), np.ndarray):
                data["names"]["rules"] = data["names"]["rules"].tolist()
            collection.insert_one({
                "pois_id": data["id"],
                "location": {  # Campo GeoJSON
                    "type": "Point",
                    "coordinates": [data["lon"], data["lat"]]  # GeoJSON richiede [lon, lat]
                },
                "names": data["names"],
                "categories": {
                    "primary": primary,
                    "alternate": alternate
                }

            })
        except DuplicateKeyError:
            print(f"Il PoI con ID {data['id']} esiste già. Ignorato.")
            ...

            # Ignora l'errore se il nodo esiste già
            #print(f"Il nodo con ID {data['id']} esiste già. Ignorato.")


