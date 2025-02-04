from typing import Dict, Tuple, Union, List
from backend.db import db

def get_pois_by_node_id(node_id: int) -> Tuple[int, str, Union[Dict[str, Dict], None]]:
    """
    Recupera i POI associati a un dato node_id dalla collezione distance_to_pois_walk.

    :param node_id: Identificatore univoco del nodo
    :return: Tuple contenente il codice di stato, il messaggio e i dati trovati (se presenti)
    """
    try:
        collection = db["distances_to_pois_walk"]
        query = {"node_id": node_id}
        document = collection.find_one(query)

        if not document:
            return 404, "Nessun poi trovato per il node_id fornito", None

        pois_data = document.get("PoIs", {})

        return 200, "OK", pois_data

    except Exception as e:
        return 500, f"Errore del server: {str(e)}", None

def get_detailed_pois_by_node_id(node_id: int) -> Tuple[int, str, Union[Dict[str, Dict], None]]:
    """
    Recupera i POI associati a un dato node_id dalla collezione distance_to_pois_walk,
    arricchisce i dati con le informazioni dettagliate dalla collezione pois
    e li restituisce ordinati per distanza in ordine crescente.

    :param node_id: Identificatore univoco del nodo
    :return: Tuple contenente il codice di stato, il messaggio e i dati ordinati (se presenti)
    """
    try:
        distance_collection = db["distances_to_pois_walk"]
        pois_collection = db["pois"]

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

        # Creazione della lista dei POI con dettagli
        detailed_pois_list = []
        for poi_id, poi_info in pois_data.items():
            if poi_id in pois_details:
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


def get_pois_within_isochrone(node_id: int, isochrone_data: Dict) -> Tuple[int, str, Union[List[Dict], None]]:
    """
    Recupera i POI all'interno dell'isocrona, filtrandoli direttamente tramite il poligono invece della bounding box.

    :param node_id: Identificatore univoco del nodo
    :param isochrone_data: Dati dell'isocrona contenenti il poligono
    :return: Lista dei POI all'interno del poligono
    """
    try:
        pois_collection = db["pois"]
        distance_collection = db["distances_to_pois_walk"]

        # Trova il documento con il node_id specificato
        query = {"node_id": node_id}
        document = distance_collection.find_one(query)

        if not document:
            return 404, "Nessun documento trovato per il node_id fornito", None

        pois_data = document.get("PoIs", {})
        if not pois_data:
            return 200, "Nessun POI disponibile per questo nodo", []

        # Estrarre il poligono dal convex_hull dell'isocrona (è già nel formato [lon, lat])
        convex_hull_coordinates = isochrone_data["convex_hull"]["coordinates"]

        # Debug: Stampa il poligono usato per la query
        print(f"Poligono usato per il filtraggio: {convex_hull_coordinates}")

        # Query per trovare i POI dentro l'isocrona
        pois_details = {poi["pois_id"]: poi for poi in pois_collection.find({
            "pois_id": {"$in": list(pois_data.keys())},
            "location": {
                "$geoWithin": {
                    "$geometry": {
                        "type": "Polygon",
                        "coordinates": convex_hull_coordinates  # Ora i POI hanno coordinate coerenti
                    }
                }
            }
        })}

        # Debug: Numero di POI trovati dopo il filtro
        print(f"Numero di POI trovati dentro l'isocrona: {len(pois_details)}")

        # Creazione della lista dei POI con dettagli
        detailed_pois_list = []
        for poi_id, poi_info in pois_data.items():
            if poi_id in pois_details:
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




'''
def get_pois_within_bbox(node_id: int, bbox: List[float]) -> Tuple[int, str, Union[List[Dict], None]]:
    """
    Recupera i POI associati a un node_id dalla collezione distance_to_pois_walk,
    arricchisce i dati con le informazioni dettagliate dalla collezione pois,
    e filtra i risultati per essere all'interno della bounding box fornita.

    :param node_id: Identificatore univoco del nodo
    :param bbox: Bounding box [lon_min, lat_min, lon_max, lat_max] per filtrare i POI
    :return: Tuple contenente il codice di stato, il messaggio e i dati filtrati (se presenti)
    """
    try:
        distance_collection = db["distances_to_pois_walk"]  # Correzione del nome collezione
        pois_collection = db["pois"]

        # Trova il documento con il node_id specificato
        query = {"node_id": node_id}
        document = distance_collection.find_one(query)

        if not document:
            return 404, "Nessun poi documento trovato per il node_id fornito", None

        pois_data = document.get("PoIs", {})

        # Se non ci sono POI per questo nodo, ritorna una lista vuota
        if not pois_data:
            return 200, "Nessun POI disponibile per questo nodo", []

        # Recupera i dettagli dei POI dalla collezione 'pois', filtrando per bounding box
        poi_ids = list(pois_data.keys())

        # Debugging - stampa la bounding box
        print(f"Bounding Box Usata: {bbox}")

        # Stampa i POI disponibili prima del filtraggio
        all_pois = list(pois_collection.find({"pois_id": {"$in": poi_ids}}, {"pois_id": 1, "location": 1}))
        print(f"Numero totale di POI prima del filtro bbox: {len(all_pois)}")

        filtered_pois_manual = [
            poi for poi in all_pois
            if bbox[0] <= poi["location"]["coordinates"][1] <= bbox[2] and
               bbox[1] <= poi["location"]["coordinates"][0] <= bbox[3]
        ]

        print(f"Numero di POI che manualmente rientrano nella bbox: {len(filtered_pois_manual)}")

        pois_details = {poi["pois_id"]: poi for poi in pois_collection.find({
            "pois_id": {"$in": poi_ids},
            "location": {
                "$geoWithin": {
                    "$box": [
                        [bbox[0] - 0.001, bbox[1] - 0.001],  # lon_min, lat_min con margine di errore
                        [bbox[2] + 0.001, bbox[3] + 0.001]
                    ]

                }
            }
        })}
        

        pois_details = {poi["pois_id"]: poi for poi in pois_collection.find({
            "pois_id": {"$in": poi_ids},
            "location": {
                "$geoIntersects": {
                    "$geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [bbox[0], bbox[1]],  # lon_min, lat_min
                            [bbox[2], bbox[1]],  # lon_max, lat_min
                            [bbox[2], bbox[3]],  # lon_max, lat_max
                            [bbox[0], bbox[3]],  # lon_min, lat_max
                            [bbox[0], bbox[1]]  # chiusura del poligono
                        ]]
                    }
                }
            }
        })}

        # Debugging - Stampa il numero di POI trovati
        print(f"Numero di POI trovati: {len(pois_details)}")

        # Creazione della lista dei POI con dettagli
        detailed_pois_list = []
        for poi_id, poi_info in pois_data.items():
            if poi_id in pois_details:
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
'''


