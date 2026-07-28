import glob
import os

import osmnx as ox
import psycopg2
from psycopg2.extras import execute_batch

import sys
from pathlib import Path
# Add parent directory to path so utils can be imported
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
print(sys.path)
from backend.postgres_db import get_postgres_connection
from db_ingest import utils as utils


def ensure_routing_schema(conn):
    """Crea schema minimo routing se non presente (setup DB da zero)."""
    with conn.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pgrouting")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id BIGINT NOT NULL,
                network_mode TEXT NOT NULL DEFAULT 'walk',
                x DOUBLE PRECISION,
                y DOUBLE PRECISION,
                geom geometry(POINT, 4326),
                PRIMARY KEY (network_mode, id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS edges (
                id BIGSERIAL PRIMARY KEY,
                network_mode TEXT NOT NULL DEFAULT 'walk',
                source BIGINT NOT NULL,
                target BIGINT NOT NULL,
                cost DOUBLE PRECISION NOT NULL,
                geom geometry(LINESTRING, 4326)
            )
            """
        )

        # node_poi viene usata dallo step successivo (x9); la creiamo gia qui.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS node_poi (
                id BIGSERIAL PRIMARY KEY,
                network_mode TEXT NOT NULL DEFAULT 'walk',
                node_id BIGINT NOT NULL,
                poi_id TEXT NOT NULL,
                distance_m DOUBLE PRECISION,
                UNIQUE (network_mode, node_id, poi_id)
            )
            """
        )

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_mode_id ON nodes(network_mode, id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_geom ON nodes USING GIST(geom)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_mode_source ON edges(network_mode, source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_mode_target ON edges(network_mode, target)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_node_poi_mode_node ON node_poi(network_mode, node_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_node_poi_poi ON node_poi(poi_id)")

    conn.commit()

def resolve_mode(path: str):
    file_name = os.path.basename(path).lower()
    if "bike" in file_name:
        return "bike"
    if "walk" in file_name:
        return "walk"
    return None


def resolve_city_code(path: str) -> str:
    """Estrae il codice ISTAT dal nome del file (es. '001272 walk.graphml.gz' -> '001272')."""
    name = Path(path).name
    import re
    match = re.search(r"(\d{6})", name)
    if match:
        return match.group(1)
    return name.split(" ")[0]


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
        execute_batch(cursor, insert_query, edge_rows, page_size=5000)
    conn.commit()


def reset_mode_network_data(conn, mode: str):
    """Reset dati rete per mode una sola volta prima dell'ingest completo."""
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM edges WHERE network_mode = %s", (mode,))
        cursor.execute("DELETE FROM nodes WHERE network_mode = %s", (mode,))
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
    graphml_dir = os.getenv("GRAPHML_DIR", "db_ingest/graphml")

    paths = sorted(glob.glob(os.path.join(graphml_dir, "*.graphml*")))
    if not paths:
        print(f"Nessun file trovato in {graphml_dir}")
        return

    modes_in_files = {resolve_mode(path) for path in paths}
    modes_in_files.discard(None)

    conn = get_postgres_connection()
    try:
        ensure_routing_schema(conn)

        for mode in sorted(modes_in_files):
            print(f"Reset rete esistente per mode={mode}")
            reset_mode_network_data(conn, mode)

        for path in paths:
            city_code = resolve_city_code(path)
            if not utils.should_process_city(city_code):
                print(f"Skip {path}: {city_code} non in CITY_CODE_FILTER")
                continue
            ingest_graphml(path, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
