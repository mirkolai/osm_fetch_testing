from typing import Dict, Tuple, Union, List
from backend.db import db



def get_detailed_pois_by_node_id(node_id: int, min: int, vel: int, categories: List[str]) -> Tuple[int, str, Union[List[Dict], None], int]:
    """
    Recupera i POI raggiungibili dal nodo specificato entro il tempo massimo indicato.

    La funzione usa prima la collezione con le distanze precomputate per filtrare i POI
    raggiungibili, poi arricchisce il risultato con i dettagli anagrafici letti dalla
    collezione `pois`, infine restituisce l'elenco ordinato per distanza crescente.
    """
    try:
        distance_collection = db["distances_to_pois_walk"]
        pois_collection = db["pois"]

        # Calcola la distanza massima raggiungibile in metri
        max_distance = (vel * 1000 / 60) * min

        # La pipeline apre il vettore dei POI precalcolati e mantiene solo quelli entro soglia.
        pipeline = [
            {"$match": {"node_id": node_id}},
            {"$unwind": "$PoIs"},
            {"$match": {"PoIs.1": {"$lt": max_distance}}},
            {
                "$project": {
                    "_id": 0,
                    "poi_id": {"$arrayElemAt": ["$PoIs", 0]},
                    "distance": {"$arrayElemAt": ["$PoIs", 1]}
                }
            }
        ]

        documents = list(distance_collection.aggregate(pipeline))
        if len(documents)==0:
            return 200,"not found",[],0

        pois_ids = [d["poi_id"] for d in documents]
        pois_distances = {d["poi_id"]: d["distance"] for d in documents}

        # Se non ci sono POI per questo nodo, ritorna una lista vuota
        if not pois_ids:
            return 200,"not found",[],0

        # Recupera in un'unica query i dettagli dei POI e li indicizza per id.
        pois_details = {poi["pois_id"]: poi for poi in pois_collection.find({"pois_id": {"$in": pois_ids}})}
        total_count = len(pois_details)

        # Ricostruisce l'ordine originale per distanza filtrando le sole categorie richieste dal flow.
        detailed_pois_list = []
        for poi_id in pois_ids:
            if poi_id in pois_details:
                poi = pois_details[poi_id]
                primary_category = poi["categories"].get("primary", "")
                alternate_categories = poi["categories"].get("alternate", []) or []

                # Al momento lo user study usa la categoria primaria come criterio di inclusione.
                if primary_category in categories: #or any(cat in categories for cat in alternate_categories):
                    detailed_pois_list.append({
                        "poi_id": poi_id,
                        "distance": pois_distances[poi_id],
                        "location": poi["location"],
                        "names": poi["names"],
                        "categories": poi["categories"]
                    })

        # Ordina la lista per distanza in ordine crescente
        detailed_pois_list.sort(key=lambda x: x["distance"])

        return 200, "OK", detailed_pois_list, total_count

    except Exception as e:
        return 200, e, [], 0
