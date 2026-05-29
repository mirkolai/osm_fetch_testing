import os
import time

from pymongo import MongoClient

from backend.postgres_db import get_postgres_connection
from backend.postgres_ingest.ingest_network import main as ingest_network_main
from backend.postgres_ingest.map_pois_to_nodes import main as map_pois_main


def _wait_for_postgres(timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        try:
            conn = get_postgres_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                return
            finally:
                conn.close()
        except Exception as exc:
            print(f"[bootstrap] PostgreSQL non ancora pronto: {exc}")
            time.sleep(2)

    raise TimeoutError("Timeout attesa PostgreSQL")


def _wait_for_mongo(timeout_seconds: int, mongo_url: str, mongo_db: str) -> None:
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        try:
            client = MongoClient(mongo_url)
            try:
                db = client[mongo_db]
                # Aspetta che il restore abbia reso disponibile almeno la collection pois.
                if "pois" in db.list_collection_names() and db["pois"].estimated_document_count() > 0:
                    return
            finally:
                client.close()
        except Exception as exc:
            print(f"[bootstrap] MongoDB non ancora pronto: {exc}")

        print("[bootstrap] Attendo restore Mongo (collection pois)...")
        time.sleep(2)

    raise TimeoutError("Timeout attesa MongoDB/restore")


def _current_counts() -> tuple[int, int, int]:
    conn = get_postgres_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    (SELECT count(*) FROM nodes) AS nodes_count,
                    (SELECT count(*) FROM edges) AS edges_count,
                    (SELECT count(*) FROM node_poi) AS node_poi_count
                """
            )
            row = cursor.fetchone()
            return int(row[0]), int(row[1]), int(row[2])
    finally:
        conn.close()


def _already_initialized() -> bool:
    nodes_count, edges_count, node_poi_count = _current_counts()
    print(
        f"[bootstrap] Stato attuale Postgres: nodes={nodes_count}, "
        f"edges={edges_count}, node_poi={node_poi_count}"
    )
    return nodes_count > 0 and edges_count > 0 and node_poi_count > 0


def main() -> None:
    timeout_seconds = int(os.getenv("BOOTSTRAP_TIMEOUT_SECONDS", "600"))
    mongo_url = os.getenv("MONGO_URL", "mongodb://user:pass@mongodb:27017")
    mongo_db = os.getenv("MONGO_DB", "15minute")

    print("[bootstrap] Avvio bootstrap automatico Postgres...")
    _wait_for_postgres(timeout_seconds)
    _wait_for_mongo(timeout_seconds, mongo_url, mongo_db)

    if _already_initialized():
        print("[bootstrap] Dataset gia presente, skip ingest.")
        return

    print("[bootstrap] Eseguo ingest rete da GraphML...")
    ingest_network_main()

    print("[bootstrap] Eseguo mapping POI -> nodo...")
    map_pois_main()

    nodes_count, edges_count, node_poi_count = _current_counts()
    print(
        f"[bootstrap] Completato: nodes={nodes_count}, "
        f"edges={edges_count}, node_poi={node_poi_count}"
    )

    if nodes_count == 0 or edges_count == 0 or node_poi_count == 0:
        raise RuntimeError("Bootstrap incompleto: tabelle Postgres ancora vuote")


if __name__ == "__main__":
    main()
