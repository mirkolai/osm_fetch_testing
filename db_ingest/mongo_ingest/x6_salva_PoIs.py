import glob
import numpy as np
import geopandas as gpd
from pymongo import MongoClient, version
from db_ingest import utils


# Connessione a MongoDB
client = MongoClient(utils.CONNECTION_STRING)
db = client[utils.MONGO_DB_NAME]
collection = db["pois"]


# Creazione indici
collection.create_index([("pois_id", 1), ("city_code", 1)], unique=True)
collection.create_index([("location", "2dsphere")])


for gzip_filename in glob.glob("db_ingest/graphml/* PoI.feather.zstd"):

    city_code = (
        gzip_filename
        .split("/")[-1]
        .replace(" PoI.feather.zstd", "")
        .strip()
    )

    if not utils.should_process_city(city_code):
        print(f"Skip {city_code} (non in CITY_CODE_FILTER)")
        continue

    poi_data = gpd.read_feather(gzip_filename)

    print(f"\n{city_code}")
    print(f"Numero di PoI da elaborare: {len(poi_data)}")

    inserted = 0
    updated = 0
    unchanged = 0
    errors = 0

    for _, row in poi_data.iterrows():

        
        try:
            # ---------------------------------------------------------
            # Coordinate
            # ---------------------------------------------------------

            geom = row["geometry"]
            lon, lat = geom.x, geom.y


            # ---------------------------------------------------------
            # Categorie
            # ---------------------------------------------------------


            taxonomy = (
                row.get("taxonomy")
                if "taxonomy" in poi_data.columns
                else None
            )

            if isinstance(taxonomy, dict):
                taxonomy = taxonomy.copy()

                for key, value in taxonomy.items():
                    if isinstance(value, np.ndarray):
                        taxonomy[key] = value.tolist()
                            

            basic_cat = (
                row.get("basic_category")
                if "basic_category" in poi_data.columns
                else None
            )

            if isinstance(taxonomy, dict):

                primary = taxonomy.get("primary")

                alternate = taxonomy.get("alternate", [])

                if isinstance(alternate, np.ndarray):
                    alternate = alternate.tolist()

            else:

                primary = None
                alternate = []


            # ---------------------------------------------------------
            # Nomi
            # ---------------------------------------------------------

            names = row.get("names")

            if (
                isinstance(names, dict)
                and isinstance(names.get("rules"), np.ndarray)
            ):
                names["rules"] = names["rules"].tolist()


            # ---------------------------------------------------------
            # Documento
            # ---------------------------------------------------------

            poi_id = row["id"]

            poi_document = {
                "pois_id": poi_id,
                "city_code": city_code,
                 
                "location": {
                    "type": "Point",
                    "coordinates": [
                        float(lon),
                        float(lat)
                    ]
                },

                "names": names,
                "basic_category": basic_cat,
                "taxonomy": taxonomy,
                "categories": {
                    "primary": primary,
                    "alternate": alternate
                },
                "version": row.get("version")


                
            }


            # ---------------------------------------------------------
            # INSERT oppure UPDATE
            # ---------------------------------------------------------

            result = collection.update_one(
                {"pois_id": poi_id, "city_code": city_code},


                {
                    "$set": {
                        "location": poi_document["location"],
                        "names": poi_document["names"],
                        "basic_category": poi_document["basic_category"],
                        "taxonomy": poi_document["taxonomy"],
                        "categories": poi_document["categories"],
                        "version": poi_document["version"]
                    }
                },

                upsert=True
            )


            # ---------------------------------------------------------
            # Statistiche
            # ---------------------------------------------------------

            if result.upserted_id is not None:
                inserted += 1

            elif result.modified_count > 0:
                updated += 1

            else:
                unchanged += 1


        except Exception as e:

            errors += 1

            print(
                f"Errore durante l'elaborazione del PoI "
                f"{row.get('id')}: {e}"
            )


    print(
        f"Risultato {city_code}: "
        f"inseriti={inserted}, "
        f"aggiornati={updated}, "
        f"inalterati={unchanged}, "
        f"errori={errors}"
    )


client.close()

