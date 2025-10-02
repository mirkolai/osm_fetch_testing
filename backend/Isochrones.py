from typing import Union, List, Tuple, Dict

from backend.db import db
import logging
logging.basicConfig(
    #level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def get_isochrone_bbox_by_node_id(node_id: int, minute: int, velocity: int) -> (
        Tuple)[int, str, Union[List[float], None]]:
    """
    Recupera la bounding box dell'isocrona di un nodo dalla collezione 'isochrone_walk',
    filtrando per node_id, minuti e velocità, e accedendo correttamente ai dati sotto 'convex_hull'.

    :param node_id: ID del nodo
    :param minute: Minuti dell'isocrona
    :param velocity: Velocità dell'isocrona
    :return: Tuple con codice di stato, messaggio e la bounding box [lon_min, lat_min, lon_max, lat_max]
    """
    try:
        collection = db["isochrone_walk"]

        # Query per trovare il documento con il node_id, minuto e velocità specificati
        query = {"node_id": node_id}
        document = collection.find_one(query)

        if not document:
            return 404, "Nessuna isocrona trovata per il node_id fornito", None

        # Naviga nella struttura annidata per estrarre la bounding box dal convex_hull
        isochrone_data = document.get("isochrone", {}).get(str(minute), {}).get(str(velocity), {})
        convex_hull = isochrone_data.get("convex_hull", {})

        # Estrazione della bounding box
        bbox = convex_hull.get("bbox", None)

        if bbox:
            return 200, "OK", bbox
        else:
            return 404, "Bounding box non trovata per i parametri specificati", None

    except Exception as e:
        return 500, f"Errore del server: {str(e)}", None


def get_isocronewalk_by_node_id(node_id: int, minute: int, velocity: int) -> (
        Tuple)[int, str, Union[Dict[str, Union[int, Dict[str, Union[List[List[float]], List[float]]]]], None]]:
    logging.info(f"get_isocronewalk_by_node_id ")
    #print(f"get_isocronewalk_by_node_id {node_id}")

    collection = db["isochrone_walk"]
    # Query per trovare il documento con il node_id specificato
    query = {"node_id": node_id}
    document = collection.find_one(query)
    #print(document)
    # Verifica se il documento esiste
    if not document:
        print(f"No data found for the given node_id {node_id}")
        logging.debug(f"No data found for the given node_id {node_id}")

        return 404, "No data found for the given node_id", None

    # Verifica se il campo isochrone esiste per il minuto e la velocità
    isochrone_data = document.get("isochrone", {}).get(str(minute), {}).get(str(velocity), {})

    # Log di debug per vedere cosa viene trovato
    # print(f"Document trovato: {document}")
    # print(f"isochrone_data per {minute} minuti e velocità {velocity}: {isochrone_data}")

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
        logging.debug(f"Dati dell'isocrona non trovati per i parametri specificati")

        return 404, "Dati dell'isocrona non trovati per i parametri specificati", None
