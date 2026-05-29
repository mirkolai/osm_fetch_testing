from typing import Dict, Tuple, Union

from backend.mongo_db import db


_closeness_min_max_cache: Dict[Tuple[str, str], Tuple[float, float]] = {}
_node_city_cache: Dict[int, Union[str, None]] = {}
_city_geometry_cache: Dict[str, dict] = {}


def _resolve_connectivity_collection(travel_mode: str) -> str:
    mode = (travel_mode or "walking").strip().lower()
    if mode in {"bike", "bicycle", "cycling"}:
        return "connectivity_bike"
    return "connectivity_walk"


def get_closeness_by_node_id(node_id: int, travel_mode: str) -> Tuple[int, str, Union[float, None]]:
    """Return closeness from connectivity collections for the given node and travel mode."""
    try:
        collection_name = _resolve_connectivity_collection(travel_mode)
        collection = db[collection_name]
        document = collection.find_one({"node_id": node_id}, {"_id": 0, "connectivity.closeness": 1})
        if not document:
            return 404, "connectivity not found", None

        closeness = (document.get("connectivity") or {}).get("closeness")
        if closeness is None:
            return 404, "closeness not found", None

        return 200, "OK", float(closeness)
    except Exception as exc:
        return 500, str(exc), None


def _get_city_code_by_node_id(node_id: int) -> Union[str, None]:
    if node_id in _node_city_cache:
        return _node_city_cache[node_id]

    nodes_collection = db["nodes"]
    city_polygon_collection = db["city_polygon"]

    node_doc = nodes_collection.find_one({"node_id": node_id}, {"_id": 0, "location": 1})
    if not node_doc or "location" not in node_doc:
        _node_city_cache[node_id] = None
        return None

    city_doc = city_polygon_collection.find_one(
        {
            "geometry": {
                "$geoIntersects": {
                    "$geometry": node_doc["location"]
                }
            }
        },
        {"_id": 0, "PRO_COM_T": 1},
    )
    if not city_doc:
        _node_city_cache[node_id] = None
        return None

    city_code = city_doc.get("PRO_COM_T")
    _node_city_cache[node_id] = city_code
    return city_code


def _compute_closeness_min_max(collection_name: str, city_code: Union[str, None]) -> Tuple[float, float]:
    cache_key = (collection_name, city_code or "__ALL__")
    cached = _closeness_min_max_cache.get(cache_key)
    if cached:
        return cached

    connectivity_collection = db[collection_name]

    # Fallback globale sul mode quando non e possibile derivare la citta.
    if not city_code:
        result = list(connectivity_collection.aggregate([
            {
                "$group": {
                    "_id": None,
                    "min_closeness": {"$min": "$connectivity.closeness"},
                    "max_closeness": {"$max": "$connectivity.closeness"},
                }
            }
        ]))
        if not result:
            return 0.0, 1.0
        min_c = float(result[0].get("min_closeness", 0.0) or 0.0)
        max_c = float(result[0].get("max_closeness", 1.0) or 1.0)
        _closeness_min_max_cache[cache_key] = (min_c, max_c)
        return min_c, max_c

    city_geometry = _city_geometry_cache.get(city_code)
    if city_geometry is None:
        city_polygon_collection = db["city_polygon"]
        city_doc = city_polygon_collection.find_one({"PRO_COM_T": city_code}, {"_id": 0, "geometry": 1})
        if not city_doc or "geometry" not in city_doc:
            return _compute_closeness_min_max(collection_name, None)
        city_geometry = city_doc["geometry"]
        _city_geometry_cache[city_code] = city_geometry

    if not city_geometry:
        return _compute_closeness_min_max(collection_name, None)

    pipeline = [
        {
            "$lookup": {
                "from": "nodes",
                "localField": "node_id",
                "foreignField": "node_id",
                "as": "node_doc",
            }
        },
        {"$unwind": "$node_doc"},
        {
            "$match": {
                "node_doc.location": {
                    "$geoWithin": {
                        "$geometry": city_geometry
                    }
                }
            }
        },
        {
            "$group": {
                "_id": None,
                "min_closeness": {"$min": "$connectivity.closeness"},
                "max_closeness": {"$max": "$connectivity.closeness"},
            }
        }
    ]

    result = list(connectivity_collection.aggregate(pipeline))
    if not result:
        return _compute_closeness_min_max(collection_name, None)

    min_c = float(result[0].get("min_closeness", 0.0) or 0.0)
    max_c = float(result[0].get("max_closeness", 1.0) or 1.0)
    _closeness_min_max_cache[cache_key] = (min_c, max_c)
    return min_c, max_c


def get_normalized_closeness_by_node_id(node_id: int, travel_mode: str) -> Tuple[int, str, Union[float, None]]:
    """Return closeness normalized to [0, 1] using city-level min/max (fallback mode-wide)."""
    status, message, closeness = get_closeness_by_node_id(node_id=node_id, travel_mode=travel_mode)
    if status != 200 or closeness is None:
        return status, message, None

    try:
        collection_name = _resolve_connectivity_collection(travel_mode)
        city_code = _get_city_code_by_node_id(node_id)
        min_c, max_c = _compute_closeness_min_max(collection_name, city_code)

        if max_c <= min_c:
            return 200, "OK", 0.0

        normalized = (float(closeness) - min_c) / (max_c - min_c)
        if normalized < 0.0:
            normalized = 0.0
        elif normalized > 1.0:
            normalized = 1.0
        return 200, "OK", float(normalized)
    except Exception as exc:
        return 500, str(exc), None
