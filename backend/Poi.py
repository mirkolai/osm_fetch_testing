from typing import Dict, Tuple, Union, List
from backend.db import db

def get_detailed_pois_by_node_id(
    node_id: int,
    min: int,
    vel: int,
    categories: List[str]
) -> Tuple[int, str, Union[List[Dict], None], int]:
    """
    Recupera i POI associati a un dato node_id dalla collezione distances_to_pois_walk,
    arricchisce i dati con le informazioni dettagliate dalla collezione pois,
    e li restituisce ordinati per distanza in ordine crescente.
    Filtra i POI in base alla distanza massima raggiungibile con la velocità e il tempo forniti.
    Inoltre, filtra i POI sulla base delle categorie specificate (primary e alternate).

    Ritorna:
        status_code, message, detailed_pois_list, total_count
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
            # Non c'è alcun documento per questo node_id
            return 404, "Nessun documento trovato per il node_id indicato", [], 0

        pois_data = document.get("PoIs", {})

        # Se non ci sono POI per questo nodo, ritorna comunque una tupla con lista vuota
        if not pois_data:
            return 200, "Nessun POI trovato", [], 0

        # Recupera i POI dalla collezione 'pois' il cui distance <= max_distance
        poi_ids = [
            poi_id
            for poi_id, poi_info in pois_data.items()
            if isinstance(poi_info, dict)
            and poi_info.get("distance") is not None
            and poi_info["distance"] <= max_distance
        ]

        # Leggi i dettagli da 'pois'
        pois_details = {
            poi["pois_id"]: poi
            for poi in pois_collection.find({"pois_id": {"$in": poi_ids}})
        }

        # Filtro finale sui POI in base alle categorie
        detailed_pois_list = []
        for poi_id in poi_ids:
            if poi_id in pois_details:
                poi = pois_details[poi_id]
                primary_category = poi["categories"].get("primary", "")
                alternate_categories = poi["categories"].get("alternate", []) or []

                # Verifica se appartiene a una delle categorie fornite
                if (primary_category in categories
                   or any(cat in categories for cat in alternate_categories)):

                    detailed_pois_list.append({
                        "poi_id": poi_id,
                        "distance": pois_data[poi_id]["distance"],
                        "location": poi["location"],
                        "names": poi["names"],
                        "categories": poi["categories"]
                    })

        # Ordina per distanza crescente
        detailed_pois_list.sort(key=lambda x: x["distance"])

        # Ritorna anche la lunghezza complessiva dei POI filtrati
        total_count = len(detailed_pois_list)
        return 200, "OK", detailed_pois_list, total_count

    except Exception as e:
        # In caso di errore imprevisto
        return 500, f"Errore del server: {str(e)}", [], 0


def get_detailed_pois_by_node_id(node_id: int, min: int, vel: int, categories: List[str]) -> Tuple[int, str, Union[List[Dict], None], int]:
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
        total_count = len(pois_details)
        print("TOT POIS in Poi: ", len(pois_details))

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

        return 200, "OK", detailed_pois_list, total_count

    except Exception as e:
        return []