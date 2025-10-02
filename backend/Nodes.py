from typing import Union, Tuple

from pydantic import BaseModel

from backend.db import db
import logging
logging.basicConfig(
    #level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class Coordinates(BaseModel):
    lat: float
    lon: float


# Funzione per ottenere l'ID del nodo in base alle coordinate
def get_id_node_by_coordinates(coordinates: Coordinates) -> Tuple[int, str, Union[int, None]]:
    #print("get_id_node_by_coordinates 0.1")
    #print(coordinates)
    try:
        logging.info("get_id_node_by_coordinates 0")
        logging.info(coordinates)
        nodes_collection = db['nodes']

        # Query per trovare il nodo con le coordinate specificate
        node = nodes_collection.count_documents({})
        logging.info(node)

        node = nodes_collection.find_one({
            "location": {
                "$near": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [coordinates.lon, coordinates.lat]
                    },
                }
            }
        })
        #print("nodes_collection.find_one")
        #print(node)
        logging.info(node)

        # Controlla se il nodo è stato trovato
        if node:
            return 200, "OK", node['node_id']
        else:
            logging.info(f"Nodo non trovato!")

            return 404, "Nodo non trovato", None
    except Exception as e:
        print(e)
        # Gestione degli errori generali
        return 500, f"Errore del server: {str(e)}", None
