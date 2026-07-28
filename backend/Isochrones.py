from typing import Union, List, Tuple, Dict, Optional

from backend.mongo_db import db
from backend.postgres_db import get_postgres_connection
from shapely.geometry import MultiPoint, mapping
import logging
logging.basicConfig(
    #level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def _resolve_network_mode(travel_mode: str) -> str:
    normalized_mode = (travel_mode or "walking").strip().lower()
    if normalized_mode in {"bike", "bicycle", "cycling"}:
        return "bike"
    return "walk"


def _fetch_reachable_nodes(
    node_id: int,
    minute: int,
    velocity: int,
    network_mode: str,
    conn=None,
    graph_sql: Optional[str] = None,
) -> List[Tuple[float, float]]:
    max_distance = (velocity * 1000 / 60) * minute
    graph_sql_text = graph_sql or (
        "SELECT id, source, target, cost, cost AS reverse_cost "
        f"FROM edges WHERE network_mode = ''{network_mode}''"
    )
    query = f"""
        WITH reachable AS (
            SELECT node, agg_cost
            FROM pgr_drivingDistance(
                '{graph_sql_text}',
                %s,
                %s,
                directed := false
            )
        )
        SELECT n.x, n.y
        FROM reachable r
        JOIN nodes n ON n.id = r.node AND n.network_mode = %s
        ORDER BY r.agg_cost ASC
    """

    own_connection = conn is None
    if own_connection:
        conn = get_postgres_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (node_id, max_distance, network_mode))
            return [(float(x), float(y)) for x, y in cursor.fetchall()]
    finally:
        if own_connection:
            conn.close()


def _build_isochrone_result(
    node_id: int,
    minute: int,
    velocity: int,
    travel_mode: str,
    conn=None,
    graph_sql: Optional[str] = None,
):
    network_mode = _resolve_network_mode(travel_mode)
    reachable_coords = _fetch_reachable_nodes(
        node_id,
        minute,
        velocity,
        network_mode,
        conn=conn,
        graph_sql=graph_sql,
    )

    if not reachable_coords:
        return 404, "Dati dell'isocrona non trovati per i parametri specificati", None

    hull = MultiPoint(reachable_coords).convex_hull
    hull_geojson = mapping(hull)
    bbox = list(hull.bounds)

    result = {
        "node_id": node_id,
        "convex_hull": {
            "coordinates": hull_geojson.get("coordinates", []),
            "bbox": bbox,
        },
    }
    return 200, "OK", result


def get_isochrone_bbox_by_node_id(
    node_id: int,
    minute: int,
    velocity: int,
    conn=None,
    graph_sql: Optional[str] = None,
) -> (
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
        status, message, result = _build_isochrone_result(
            node_id,
            minute,
            velocity,
            "walking",
            conn=conn,
            graph_sql=graph_sql,
        )
        if status != 200:
            return status, message, None
        bbox = result["convex_hull"]["bbox"]
        return 200, "OK", bbox
    except Exception as e:
        return 500, f"Errore del server: {str(e)}", None


def get_isocronewalk_by_node_id(
    node_id: int,
    minute: int,
    velocity: int,
    travel_mode: str = "walking",
    conn=None,
    graph_sql: Optional[str] = None,
) -> (
        Tuple)[int, str, Union[Dict[str, Union[int, Dict[str, Union[List[List[float]], List[float]]]]], None]]:
    """Recupera la geometria semplificata dell'isocrona per nodo, minuti e velocità."""
    logging.info(f"get_isocronewalk_by_node_id ")
    try:
        return _build_isochrone_result(
            node_id,
            minute,
            velocity,
            travel_mode,
            conn=conn,
            graph_sql=graph_sql,
        )
    except Exception as e:
        return 500, f"Errore del server: {str(e)}", None
