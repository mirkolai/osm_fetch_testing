from typing import Dict, Tuple, Union, List
from backend.db import db



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
        #print("get_detailed_pois_by_node_id")
        distance_collection = db["distances_to_pois_walk"]
        pois_collection = db["pois"]
        #print(1)
        # Calcola la distanza massima raggiungibile in metri
        max_distance = (vel * 1000 / 60) * min

        # Trova il documento con il node_id specificato
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
        #print("documents")
        #print(documents)
        if len(documents)==0:
            #print(2)
            return 200,"not found",[],0

        pois_ids = [d["poi_id"] for d in documents]
        pois_distances = {d["poi_id"]: d["distance"] for d in documents}

        # Se non ci sono POI per questo nodo, ritorna una lista vuota
        if not pois_ids:
            #print(3)
            return 200,"not found",[],0
        #print(4)
        # Recupera i dettagli dei POI dalla collezione 'pois'

        pois_details = {poi["pois_id"]: poi for poi in pois_collection.find({"pois_id": {"$in": pois_ids}})}
        total_count = len(pois_details)
        #print("TOT POIS in Poi: ", len(pois_details))

        # Creazione della lista dei POI con dettagli filtrati per distanza e categorie
        detailed_pois_list = []
        for poi_id in pois_ids:
            if poi_id in pois_details:
                poi = pois_details[poi_id]
                primary_category = poi["categories"].get("primary", "")
                alternate_categories = poi["categories"].get("alternate", []) or []

                # Verifica se il POI appartiene a una delle categorie richieste
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
