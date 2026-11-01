from pymongo import MongoClient
import glob
import osmnx as ox
from db_ingest import utils


"""
Questo script salva nella collezione MongoDB "nodes" le informazioni
relative agli incroci delle reti pedonali e ciclabili.

Se il nodo non esiste:
    -> viene inserito

Se il nodo esiste già:
    -> viene aggiornato con le nuove coordinate

Gli altri documenti del database non vengono modificati né cancellati.
"""


# Connessione MongoDB
client = MongoClient(utils.CONNECTION_STRING)
db = client[utils.MONGO_DB_NAME]
collection = db["nodes"]


# Indice univoco sul nodo
collection.create_index(
    [
        ("node_id", 1),
        ("network_mode", 1),
        ("city_code", 1)
    ],
    unique=True
)
# Indice geospaziale
collection.create_index([("location", "2dsphere")])

print("Indice geospaziale 2dsphere creato su 'location'.")


for travel_type in utils.TRAVEL_SPEEDS.keys():
    print(f"Processing travel_type: {travel_type}")
    for gzip_filename in glob.glob(
        f"db_ingest/graphml/* {travel_type}.graphml.gz"
    ):

        city_code = (
            gzip_filename
            .split("/")[-1]
            .replace(
                f" {travel_type}.graphml.gz",
                ""
            )
            .strip()
        )

        if not utils.should_process_city(city_code):
            print(f"Skip {city_code} (non in CITY_CODE_FILTER)")
            continue

        print(f"Processing {city_code}: {gzip_filename}")

        graph = ox.load_graphml(gzip_filename)

        inserted = 0
        updated = 0
        unchanged = 0

        for node_id, data in graph.nodes(data=True):

            node_data = {
                "node_id": node_id,
                "network_mode": travel_type,
                "city_code": city_code,
                "location": {
                    "type": "Point",
                    "coordinates": [
                        float(data["x"]),
                        float(data["y"])
                    ]
                }
            }

            try:

                result = collection.update_one(
                    {  "node_id": node_id,
                       "network_mode": travel_type,
                       "city_code": city_code,
                    },
                    {
                        "$set": {
                            "location": node_data["location"]
                        }
                    },
                    upsert=True
                )

                if result.upserted_id is not None:
                    inserted += 1
                elif result.modified_count > 0:
                    updated += 1
                else:
                    unchanged += 1

            except Exception as e:
                print(
                    f"Errore nel nodo {node_id} "
                    f"del comune {city_code}: {e}"
                )

        print(
            f"Inseriti: {inserted}, "
            f"Aggiornati: {updated}, "
            f"Invariati: {unchanged}"
        )


client.close()

