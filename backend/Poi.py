from typing import Dict, Tuple, Union, List
import json
import os

from psycopg2.extras import RealDictCursor

from backend.mongo_db import db
from backend.postgres_db import get_postgres_connection


_CATEGORIES_BY_GROUP = None


def _load_categories_by_group() -> Dict[str, List[str]]:
    global _CATEGORIES_BY_GROUP
    if _CATEGORIES_BY_GROUP is not None:
        return _CATEGORIES_BY_GROUP

    categories_path = os.path.join(os.path.dirname(__file__), "categories.json")
    try:
        with open(categories_path, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
            _CATEGORIES_BY_GROUP = data if isinstance(data, dict) else {}
    except Exception:
        _CATEGORIES_BY_GROUP = {}
    return _CATEGORIES_BY_GROUP


def expand_requested_categories(categories: List[str]) -> List[str]:
    """Espande macro-categorie in categorie atomiche usate nei POI."""
    categories_by_group = _load_categories_by_group()
    expanded = []
    for category in categories or []:
        if category in categories_by_group:
            expanded.extend(categories_by_group.get(category, []))
        else:
            expanded.append(category)
    # Preserve order, remove duplicates.
    return list(dict.fromkeys(expanded))


def _normalize_poi_location(location: Dict) -> Dict:
    """Normalizza Point GeoJSON eventualmente salvati come [lat, lon]."""
    if not isinstance(location, dict):
        return location
    if location.get("type") != "Point":
        return location

    coords = location.get("coordinates", [])
    if not isinstance(coords, list) or len(coords) != 2:
        return location

    a = float(coords[0])
    b = float(coords[1])

    # Heuristica robusta per Italia: [lat, lon] -> [lon, lat].
    if 35.0 <= a <= 48.5 and 6.0 <= b <= 19.0:
        return {"type": "Point", "coordinates": [b, a]}

    return location



def _resolve_network_mode(travel_mode: str) -> str:
    normalized_mode = (travel_mode or "walking").strip().lower()
    if normalized_mode in {"walking", "walking_cane", "walk", "pedestrian"}:
        return "walk"
    if normalized_mode in {"bike", "bicycle", "cycling"}:
        return "bike"
    return "walk"


def _fetch_reachable_pois_by_mode(node_id: int, max_distance: float, network_mode: str) -> List[Dict]:
    """
    Calcola i POI raggiungibili con pgr_drivingDistance su rete reale per mode.

    Il risultato usa la distanza di rete del nodo raggiungibile più vicino al POI
    sommata alla distanza residua nodo->POI salvata in node_poi.distance_m.
    """
    query = f"""
        WITH reachable AS (
            SELECT node, agg_cost
            FROM pgr_drivingDistance(
                'SELECT id, source, target, cost, cost AS reverse_cost FROM edges WHERE network_mode = ''{network_mode}''',
                %s,
                %s,
                directed := false
            )
        )
        SELECT
            np.poi_id,
            MIN(reachable.agg_cost + COALESCE(np.distance_m, 0)) AS distance
        FROM reachable
        JOIN node_poi np ON np.node_id = reachable.node AND np.network_mode = %s
        GROUP BY np.poi_id
        HAVING MIN(reachable.agg_cost + COALESCE(np.distance_m, 0)) < %s
        ORDER BY distance ASC
    """

    conn = get_postgres_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (node_id, max_distance, network_mode, max_distance))
            rows = cursor.fetchall()
            return list(rows)
    finally:
        conn.close()


def get_detailed_pois_by_node_id(
    node_id: int,
    min: int,
    vel: int,
    categories: List[str],
    travel_mode: str = "walking",
) -> Tuple[int, str, Union[List[Dict], None], int]:
    """
    Recupera i POI raggiungibili dal nodo specificato entro il tempo massimo indicato.

    La funzione calcola on-the-fly i POI raggiungibili con distanza di rete reale,
    poi arricchisce il risultato con i dettagli anagrafici letti dalla collezione
    `pois`, infine restituisce l'elenco ordinato per distanza crescente.
    """
    try:
        network_mode = _resolve_network_mode(travel_mode)
        allowed_categories = set(expand_requested_categories(categories))

        pois_collection = db["pois"]

        # Calcola la distanza massima raggiungibile in metri
        max_distance = (vel * 1000 / 60) * min

        documents = _fetch_reachable_pois_by_mode(
            node_id=node_id,
            max_distance=max_distance,
            network_mode=network_mode,
        )
        if len(documents) == 0:
            return 200, "not found", [], 0

        pois_ids = [d["poi_id"] for d in documents]
        pois_distances = {d["poi_id"]: d["distance"] for d in documents}

        # Se non ci sono POI per questo nodo, ritorna una lista vuota
        if not pois_ids:
            return 200, "not found", [], 0

        # Recupera in un'unica query i dettagli dei POI e li indicizza per id.
        pois_details = {poi["pois_id"]: poi for poi in pois_collection.find({"pois_id": {"$in": pois_ids}})}
        # Ricostruisce l'ordine originale per distanza filtrando le sole categorie richieste dal flow.
        detailed_pois_list = []
        for poi_id in pois_ids:
            if poi_id in pois_details:
                poi = pois_details[poi_id]
                primary_category = poi["categories"].get("primary", "")
                alternate_categories = poi["categories"].get("alternate", []) or []

                # Il frontend invia macro-categorie: qui lavoriamo su categorie atomiche espanse.
                include_poi = (
                    not allowed_categories
                    or primary_category in allowed_categories
                    or any(alt in allowed_categories for alt in alternate_categories)
                )

                if include_poi:
                    detailed_pois_list.append({
                        "poi_id": poi_id,
                        "distance": float(pois_distances[poi_id]),
                        "location": _normalize_poi_location(poi["location"]),
                        "names": poi["names"],
                        "categories": poi["categories"]
                    })

        # Ordina la lista per distanza in ordine crescente
        detailed_pois_list.sort(key=lambda x: x["distance"])

        return 200, "OK", detailed_pois_list, len(detailed_pois_list)

    except Exception as e:
        return 500, str(e), [], 0
