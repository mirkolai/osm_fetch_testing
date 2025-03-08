from typing import Union, Tuple

from pydantic import BaseModel

from backend.db import db


class Coordinates(BaseModel):
    lat: float
    lon: float


# Funzione per ottenere l'ID del nodo in base alle coordinate
def get_id_node_by_coordinates(coordinates: Coordinates) -> Tuple[int, str, Union[int, None]]:
    try:
        nodes_collection = db['nodes']

        # Query per trovare il nodo con le coordinate specificate
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

        # Controlla se il nodo è stato trovato
        if node:
            return 200, "OK", node['node_id']
        else:
            return 404, "Nodo non trovato", None
    except Exception as e:
        # Gestione degli errori generali
        return 500, f"Errore del server: {str(e)}", None
