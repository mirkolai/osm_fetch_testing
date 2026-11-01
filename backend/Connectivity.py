from typing import Tuple, Union

from backend.mongo_db import db
from backend.RequestModels import NetworkMode
from backend.postgres_db import get_postgres_connection


def get_closeness_by_node_id(node_id: int, travel_mode: NetworkMode) -> Tuple[int, str, Union[float, None]]:
    """Return closeness from connectivity collections for the given node and travel mode."""
    try:
        if travel_mode not in {"walk", "bike"}:
            return 400, "unsupported network_mode: use walk or bike", None

        collection_name = f"connectivity_{travel_mode}"
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


def get_nodes_in_city(N: int, PRO_COM_T: str, network_mode: NetworkMode):
    """
    Restituisce al massimo N nodi distinti precomputati per città e modalità,
    selezionandoli in ordine casuale.
    """
    query = """
        SELECT node_id
        FROM (
            SELECT DISTINCT node_id
            FROM precomputed_metrics_rows
            WHERE city_code = %s
            AND network_mode = %s
        ) AS city_nodes
        ORDER BY MD5(node_id::text)
        LIMIT %s
    """

    conn = get_postgres_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT setseed(%s)", (0.12345,))
            cursor.execute(query, (PRO_COM_T, network_mode, N))
            return [{"node_id": int(row[0])} for row in cursor.fetchall()]
    finally:
        conn.close()
