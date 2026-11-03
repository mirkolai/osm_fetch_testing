from typing import Union, List, Tuple, Dict, Optional

from backend.mongo_db import db
from backend.postgres_db import get_postgres_connection
from backend.RequestModels import NetworkMode
from shapely.geometry import MultiPoint, mapping
import logging
logging.basicConfig(
    #level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def fetch_reachable_node_costs(
    node_id: int,
    max_distance: float,
    network_mode: str,
    conn=None,
) -> List[Tuple[int, float, Optional[float], Optional[float]]]:
    """
    Esegue una sola pgr_drivingDistance e restituisce (node, agg_cost, x, y)
    ordinati per agg_cost; x/y sono None se il nodo non esiste in nodes.
    Il risultato è riusabile sia per l'isocrona sia per i POI.
    """
    query = f"""
        SELECT r.node, r.agg_cost, n.x, n.y
        FROM pgr_drivingDistance(
            'SELECT id, source, target, cost, cost AS reverse_cost FROM edges WHERE network_mode = ''{network_mode}''',
            %s,
            %s,
            directed := false
        ) r
        LEFT JOIN nodes n ON n.id = r.node AND n.network_mode = %s
        ORDER BY r.agg_cost ASC
    """
    own_connection = conn is None
    if own_connection:
        conn = get_postgres_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (node_id, max_distance, network_mode))
            return cursor.fetchall()
    finally:
        if own_connection:
            conn.close()


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
    reachable=None,
):
    if travel_mode not in {"walk", "bike"}:
        return 400, "unsupported network_mode: use walk or bike", None

    if reachable is not None:
        reachable_coords = [
            (float(x), float(y)) for _, _, x, y in reachable if x is not None and y is not None
        ]
    else:
        reachable_coords = _fetch_reachable_nodes(
            node_id,
            minute,
            velocity,
            travel_mode,
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


def get_isocronewalk_by_node_id(
    node_id: int,
    minute: int,
    velocity: int,
    travel_mode: str,
    conn=None,
    graph_sql: Optional[str] = None,
    reachable=None,
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
            reachable=reachable,
        )
    except Exception as e:
        return 500, f"Errore del server: {str(e)}", None
