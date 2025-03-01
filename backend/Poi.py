from typing import Dict, Tuple, Union, List
from backend.db import db

def get_detailed_pois_by_node_id(node_id: int, min: int, vel: int, categories: List[str]) -> Tuple[int, str, Union[List[Dict], None]]:
    """
    Recupera i POI associati a un dato node_id dalla collezione distance_to_pois_walk,
    arricchisce i dati con le informazioni dettagliate dalla collezione pois,
    e li restituisce ordinati per distanza in ordine crescente.
    Filtra i POI in base alla distanza massima raggiungibile con la velocità e il tempo forniti.
    Inoltre, filtra i POI sulla base delle categorie specificate, considerando sia primary che alternate.

    :param node_id: Identificatore univoco del nodo
    :param min: Tempo in minuti
    :param vel: Velocità in km/h
    :param categories: Lista di categorie da filtrare
    :return: Lista dei POI filtrati
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
            return []

        pois_data = document.get("PoIs", {})

        # Se non ci sono POI per questo nodo, ritorna una lista vuota
        if not pois_data:
            return []

        # Recupera i dettagli dei POI dalla collezione 'pois'
        poi_ids = [poi_id for poi_id, poi_info in pois_data.items() if
                   isinstance(poi_info, dict) and poi_info.get("distance") is not None and poi_info[
                       "distance"] <= max_distance]
        pois_details = {poi["pois_id"]: poi for poi in pois_collection.find({"pois_id": {"$in": poi_ids}})}

        # Creazione della lista dei POI con dettagli filtrati per distanza e categorie
        detailed_pois_list = []
        for poi_id in poi_ids:
            if poi_id in pois_details:
                poi = pois_details[poi_id]
                primary_category = poi["categories"].get("primary", "")
                alternate_categories = poi["categories"].get("alternate", []) or []

                # Verifica se il POI appartiene a una delle categorie richieste
                if primary_category in categories or any(cat in categories for cat in alternate_categories):
                    detailed_pois_list.append({
                        "poi_id": poi_id,
                        "distance": pois_data[poi_id]["distance"],
                        "location": poi["location"],
                        "names": poi["names"],
                        "categories": poi["categories"]
                    })

        # Ordina la lista per distanza in ordine crescente
        detailed_pois_list.sort(key=lambda x: x["distance"])

        return detailed_pois_list

    except Exception as e:
        return []