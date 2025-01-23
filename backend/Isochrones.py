from typing import Union, List, Tuple, Annotated, Dict
from backend.db import db

def get_isocronewalk_by_node_id(node_id: int, minute: int, velocity: int) -> Tuple[int, str, Union[Dict[str,
Union[int, Dict[str, Union[List[List[float]], List[float]]]]], None]]:

    collection = db["isochrone_walk"]
    # Query per trovare il documento con il node_id specificato
    query = {"node_id": node_id}
    document = collection.find_one(query)

    # Verifica se il documento esiste
    if not document:
        return 404, "No data found for the given node_id", None

    # Verifica se il campo isochrone esiste per il minuto e la velocità
    isochrone_data = document.get("isochrone", {}).get(str(minute), {}).get(str(velocity), {})

    # Log di debug per vedere cosa viene trovato
    print(f"Document trovato: {document}")
    print(f"isochrone_data per {minute} minuti e velocità {velocity}: {isochrone_data}")

    if isochrone_data:
        # Estrazione dei dati concave_hull
        result = {
            "node_id": document["node_id"],
            "concave_hull": {
                "coordinates": isochrone_data.get("concave_hull", {}).get("features", [])[0].get("geometry", {})
                .get("coordinates", []),
                "bbox": isochrone_data.get("concave_hull", {}).get("bbox", [])
            }
        }
        return 200, "OK", result
    else:
        return 404, "Dati dell'isocrona non trovati per i parametri specificati", None
"""
def get_isocronewalk_by_node_id(node_id: int, minute: int, velocity: int) -> Tuple[int, str, Union[Dict[str,
Union[int, Dict[str, Union[List[List[float]], List[float]]]]], None]]:

    collection = db["isochrone_walk"]
    # Query per trovare il documento con il node_id specificato
    query = {"node_id": node_id}
    document = collection.find_one(query)

    # Verifica se il documento esiste
    if not document:
        return 404, "No data found for the given node_id", None

    # Verifica se il campo isochrone esiste per il minuto e la velocità
    isochrone_data = document.get("isochrone", {}).get(str(minute), {}).get(str(velocity), {})

    # Log di debug per vedere cosa viene trovato
    print(f"Document trovato: {document}")
    print(f"isochrone_data per {minute} minuti e velocità {velocity}: {isochrone_data}")

    if isochrone_data:
        # Estrazione dei dati concave_hull
        result = {
            "node_id": document["node_id"],
            "convex_hull": {
                "coordinates": isochrone_data.get("convex_hull", {}).get("features", [])[0].get("geometry", {})
                .get("coordinates", []),
                "bbox": isochrone_data.get("convex_hull", {}).get("bbox", [])
            }
        }
        return 200, "OK", result
    else:
        return 404, "Dati dell'isocrona non trovati per i parametri specificati", None """
