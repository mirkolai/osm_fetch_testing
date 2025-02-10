from typing import Dict, Tuple, Union, List
from backend.db import db

def get_detailed_pois_by_node_id(node_id: int, min: int, vel: int) -> Tuple[int, str, Union[Dict[str, Dict], None]]:
    """
    Recupera i POI associati a un dato node_id dalla collezione distance_to_pois_walk,
    arricchisce i dati con le informazioni dettagliate dalla collezione pois,
    e li restituisce ordinati per distanza in ordine crescente.
    Filtra i POI in base alla distanza massima raggiungibile con la velocità e il tempo forniti.

    :param node_id: Identificatore univoco del nodo
    :param min: Tempo in minuti
    :param vel: Velocità in km/h
    :return: Tuple contenente il codice di stato, il messaggio e i dati ordinati (se presenti)
    """
    try:
        distance_collection = db["distances_to_pois_walk"]
        pois_collection = db["pois"]

        # Calcola la distanza massima raggiungibile in metri
        max_distance = (vel * 1000 / 60) * min

        # Trova il documento con il node_id specificato
        query = {"node_id": node_id}
        document = distance_collection.find_one(query)

        if not document:
            return 404, "Nessun dato trovato per il node_id fornito", None

        pois_data = document.get("PoIs", {})

        # Se non ci sono POI per questo nodo, ritorna un dizionario vuoto
        if not pois_data:
            return 200, "Nessun POI disponibile per questo nodo", {}

        # Recupera i dettagli dei POI dalla collezione 'pois'
        poi_ids = list(pois_data.keys())
        pois_details = {poi["pois_id"]: poi for poi in pois_collection.find({"pois_id": {"$in": poi_ids}})}

        # Creazione della lista dei POI con dettagli filtrati per distanza
        detailed_pois_list = []
        for poi_id, poi_info in pois_data.items():
            if poi_id in pois_details and poi_info["distance"] <= max_distance:
                detailed_pois_list.append({
                    "poi_id": poi_id,
                    "distance": poi_info["distance"],
                    "location": pois_details[poi_id]["location"],
                    "names": pois_details[poi_id]["names"],
                    "categories": pois_details[poi_id]["categories"]
                })

        # Ordina la lista per distanza in ordine crescente
        detailed_pois_list.sort(key=lambda x: x["distance"])

        return 200, "OK", detailed_pois_list

    except Exception as e:
        return 500, f"Errore del server: {str(e)}", None
