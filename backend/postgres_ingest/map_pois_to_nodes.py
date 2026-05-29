import os

from psycopg2.extras import execute_batch
from pymongo import MongoClient

from backend.postgres_db import get_postgres_connection


def get_bike_spatial_scope(conn):
    """
    Restituisce bbox e convex hull della rete bike da usare come filtro POI.

    La richiesta utente e limitare il mapping ai POI coperti dalla bike extended,
    che e la rete piu ampia disponibile.
    """
    query = """
        SELECT
            ST_XMin(ST_Extent(geom)::box2d) AS min_lon,
            ST_YMin(ST_Extent(geom)::box2d) AS min_lat,
            ST_XMax(ST_Extent(geom)::box2d) AS max_lon,
            ST_YMax(ST_Extent(geom)::box2d) AS max_lat,
            ST_AsText(ST_ConvexHull(ST_Collect(geom))) AS hull_wkt
        FROM nodes
        WHERE network_mode = 'bike'
    """
    with conn.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()

    if not row or row[0] is None:
        return None, None

    bbox = (float(row[0]), float(row[1]), float(row[2]), float(row[3]))
    hull_wkt = row[4]
    return bbox, hull_wkt


def load_pois_from_mongo():
    mongo_url = os.getenv("MONGO_URL", "mongodb://user:pass@localhost:27017")
    mongo_db_name = os.getenv("MONGO_DB", "15minute")

    client = MongoClient(mongo_url)
    try:
        db = client[mongo_db_name]
        docs = list(db["pois"].find(
            {"location.coordinates": {"$exists": True}},
            {"_id": 0, "pois_id": 1, "location": 1},
        ))
        return docs
    finally:
        client.close()


def normalize_lon_lat(coords, bbox):
    """Normalizza coordinate Mongo in formato (lon, lat).

    Alcuni dataset sono salvati erroneamente come [lat, lon].
    Usiamo la bbox bike per riconoscere e correggere il verso.
    """
    if len(coords) != 2:
        return None, None

    a = float(coords[0])
    b = float(coords[1])
    min_lon, min_lat, max_lon, max_lat = bbox

    # Caso standard GeoJSON: [lon, lat]
    if min_lon <= a <= max_lon and min_lat <= b <= max_lat:
        return a, b

    # Caso invertito: [lat, lon]
    if min_lon <= b <= max_lon and min_lat <= a <= max_lat:
        return b, a

    return None, None


def map_mode(conn, mode: str, pois_docs, bike_bbox, bike_hull_wkt: str):
    print(f"Mapping POI -> nodo per mode={mode}")

    delete_query = "DELETE FROM node_poi WHERE network_mode = %s"
    nearest_query = """
        WITH poi AS (
            SELECT ST_SetSRID(ST_MakePoint(%s, %s), 4326) AS geom
        )
        SELECT n.id, ST_Distance(
            n.geom::geography,
            poi.geom::geography
        ) AS dist_m
        FROM nodes n, poi
        WHERE n.network_mode = %s
          AND ST_Contains(ST_GeomFromText(%s, 4326), poi.geom)
        ORDER BY n.geom <-> poi.geom
        LIMIT 1
    """
    insert_query = """
        INSERT INTO node_poi (network_mode, node_id, poi_id, distance_m)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (network_mode, node_id, poi_id)
        DO UPDATE SET distance_m = EXCLUDED.distance_m
    """

    rows = []
    with conn.cursor() as cursor:
        cursor.execute(delete_query, (mode,))

        for poi in pois_docs:
            poi_id = poi.get("pois_id")
            coords = (poi.get("location") or {}).get("coordinates", [])
            if not poi_id:
                continue

            lon, lat = normalize_lon_lat(coords, bike_bbox)
            if lon is None:
                continue

            cursor.execute(nearest_query, (lon, lat, mode, bike_hull_wkt))
            result = cursor.fetchone()
            if not result:
                continue

            node_id, dist_m = result
            rows.append((mode, int(node_id), str(poi_id), float(dist_m)))

    with conn.cursor() as cursor:
        execute_batch(cursor, insert_query, rows, page_size=5000)
    conn.commit()
    print(f"Mode {mode}: {len(rows)} mapping salvati")


def main():
    conn = get_postgres_connection()
    try:
        bike_bbox, bike_hull_wkt = get_bike_spatial_scope(conn)
        if bike_bbox is None or not bike_hull_wkt:
            print("Scope bike non disponibile: controlla ingest rete in Postgres")
            return

        pois_docs = load_pois_from_mongo()
        if not pois_docs:
            print("Nessun POI trovato in Mongo")
            return

        print(f"POI totali letti da Mongo: {len(pois_docs)}")

        for mode in ("walk", "bike"):
            map_mode(conn, mode, pois_docs, bike_bbox, bike_hull_wkt)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
