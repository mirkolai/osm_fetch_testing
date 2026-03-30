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


def get_id_node_by_coordinates(coordinates: Coordinates) -> Tuple[int, str, Union[int, None]]:
    """Restituisce il node_id stradale più vicino a una coppia di coordinate."""
    try:
        logging.info("get_id_node_by_coordinates 0")
        logging.info(coordinates)
        nodes_collection = db['nodes']

        # La query geospaziale usa coordinate GeoJSON [lon, lat].
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

        if node:
            return 200, "OK", node['node_id']
        else:
            logging.info(f"Nodo non trovato!")

            return 404, "Nodo non trovato", None
    except Exception as e:
        print(e)
        return 500, f"Errore del server: {str(e)}", None
