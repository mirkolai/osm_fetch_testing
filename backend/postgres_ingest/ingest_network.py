import glob
import os

import osmnx as ox
import psycopg2
from psycopg2.extras import execute_batch

from backend.postgres_db import get_postgres_connection


def resolve_mode(path: str):
    file_name = os.path.basename(path).lower()
    if "bike" in file_name:
        return "bike"
    if "walk" in file_name:
        return "walk"
    return None


def upsert_nodes(conn, mode: str, nodes_rows):
    query = """
        INSERT INTO nodes (id, network_mode, x, y, geom)
        VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
        ON CONFLICT (network_mode, id)
        DO UPDATE SET x = EXCLUDED.x, y = EXCLUDED.y, geom = EXCLUDED.geom
    """
    with conn.cursor() as cursor:
        execute_batch(cursor, query, nodes_rows, page_size=5000)
    conn.commit()


def insert_edges(conn, mode: str, edge_rows):
    delete_query = "DELETE FROM edges WHERE network_mode = %s"
    insert_query = """
        INSERT INTO edges (network_mode, source, target, cost, geom)
        VALUES (
            %s,
            %s,
            %s,
            %s,
            ST_SetSRID(ST_MakeLine(ST_MakePoint(%s, %s), ST_MakePoint(%s, %s)), 4326)
        )
    """

    with conn.cursor() as cursor:
        cursor.execute(delete_query, (mode,))
        execute_batch(cursor, insert_query, edge_rows, page_size=5000)
    conn.commit()


def ingest_graphml(path: str, conn):
    mode = resolve_mode(path)
    if mode is None:
        print(f"Skip {path}: mode non riconosciuta")
        return

    print(f"Ingest {path} ({mode})")
    graph = ox.load_graphml(path)

    nodes_rows = []
    for node_id, data in graph.nodes(data=True):
        x = float(data["x"])
        y = float(data["y"])
        nodes_rows.append((int(node_id), mode, x, y, x, y))
    upsert_nodes(conn, mode, nodes_rows)

    edge_rows = []
    for u, v, data in graph.edges(data=True):
        ux = float(graph.nodes[u]["x"])
        uy = float(graph.nodes[u]["y"])
        vx = float(graph.nodes[v]["x"])
        vy = float(graph.nodes[v]["y"])
        cost = float(data.get("length", 1.0))
        edge_rows.append((mode, int(u), int(v), cost, ux, uy, vx, vy))
    insert_edges(conn, mode, edge_rows)

    print(f"Done {path}: {len(nodes_rows)} nodi, {len(edge_rows)} archi")


def main():
    graphml_dir = os.getenv("GRAPHML_DIR", "postgres_init/graphml")
    paths = sorted(glob.glob(os.path.join(graphml_dir, "*.graphml*")))
    if not paths:
        print(f"Nessun file trovato in {graphml_dir}")
        return

    conn = get_postgres_connection()
    try:
        for path in paths:
            ingest_graphml(path, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
