from typing import Dict, Iterable, Tuple, Union

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


def get_closeness_by_node_ids(node_ids: Iterable[int], travel_mode: NetworkMode) -> Dict[int, float]:
    """
    Come get_closeness_by_node_id, ma per più nodi con una sola query.

    Restituisce {node_id: closeness}; i nodi senza closeness sono assenti
    (il chiamante usa 0.0, come nel caso del lookup singolo).
    """
    if travel_mode not in {"walk", "bike"}:
        return {}

    ids = [int(node_id) for node_id in node_ids]
    if not ids:
        return {}

    cursor = db[f"connectivity_{travel_mode}"].find(
        {"node_id": {"$in": ids}},
        {"_id": 0, "node_id": 1, "connectivity.closeness": 1},
    )
    closeness_by_node: Dict[int, float] = {}
    for document in cursor:
        closeness = (document.get("connectivity") or {}).get("closeness")
        if closeness is not None:
            # Come find_one: vale il primo documento trovato per il nodo.
            closeness_by_node.setdefault(int(document["node_id"]), float(closeness))
    return closeness_by_node


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
