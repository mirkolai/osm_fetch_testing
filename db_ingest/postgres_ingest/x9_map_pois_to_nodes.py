import os
from pathlib import Path

from psycopg2.extras import execute_batch
from pymongo import MongoClient

import sys
from backend.postgres_db import get_postgres_connection


def _load_env_file():
    env_path = Path(__file__).resolve().parents[2] / ".env"

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(
        encoding="utf-8"
    ).splitlines():

        line = raw_line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, value = line.split("=", 1)

        os.environ.setdefault(
            key.strip(),
            value.strip().strip('"').strip("'")
        )


_load_env_file()



def load_pois_from_mongo(city_code: str):

    mongo_url = (
        os.getenv("MONGO_URL_LOCAL")
        or os.getenv("MONGO_URL")
        or os.getenv("MONGO_URL_DOCKER")
    )

    mongo_db_name = os.getenv(
        "MONGO_DB",
        "15minute"
    )

    if not mongo_url:
        raise RuntimeError(
            "Mongo URL non configurata: "
            "imposta MONGO_URL_LOCAL o MONGO_URL in .env"
        )

    client = MongoClient(mongo_url)

    try:

        db = client[mongo_db_name]

        docs = list(
            db["pois"].find(
                {   "city_code": city_code,
                    "location.coordinates": {
                        "$exists": True
                    }
                },
                {
                    "_id": 0,
                    "pois_id": 1,
                    "location": 1
                }
            )
        )

        return docs

    finally:

        client.close()




def get_existing_poi_ids(conn, mode: str,city_code: str):
    """
    Recupera gli ID dei POI già mappati per una modalità.

    Questi POI non verranno ricalcolati.
    """

    query = """
        SELECT DISTINCT poi_id
        FROM node_poi
        WHERE network_mode = %s AND city_code = %s
    """

    with conn.cursor() as cursor:

        cursor.execute(
            query,
            (mode,city_code)
        )

        return {
            str(row[0])
            for row in cursor.fetchall()
        }


def map_mode(
    conn,
    mode: str,
    city_code: str,
    pois_docs
):

    print(
        f"Mapping POI -> nodo "
        f"per mode={mode}"
    )

    # ---------------------------------------------------------
    # POI GIÀ CALCOLATI
    # ---------------------------------------------------------

    existing_poi_ids = get_existing_poi_ids(
        conn,
        mode,
        city_code
    )

    print(
        f"Mode {mode}: "
        f"{len(existing_poi_ids)} POI già presenti nel DB"
    )

    # ---------------------------------------------------------
    # QUERY DI MAPPING
    # ---------------------------------------------------------

    nearest_query = """
        WITH poi AS (
            SELECT ST_SetSRID(
                ST_MakePoint(%s, %s),
                4326
            ) AS geom
        )

        SELECT
            n.id,
            ST_Distance(
                n.geom::geography,
                poi.geom::geography
            ) AS dist_m

        FROM nodes n, poi

        WHERE n.network_mode = %s and n.city_code = %s

        ORDER BY n.geom <-> poi.geom

        LIMIT 1
    """

    insert_query = """
        INSERT INTO node_poi (
            network_mode,
            city_code,
            node_id,
            poi_id,
            distance_m
        )

        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s
        )

        ON CONFLICT (
            network_mode,
            city_code,
            node_id,
            poi_id
        )

        DO UPDATE SET
            distance_m = EXCLUDED.distance_m
    """

    rows = []

    skipped_existing = 0
    calculated = 0
    skipped_invalid = 0
    not_found = 0

    with conn.cursor() as cursor:

        for poi in pois_docs:
            poi_id = poi.get("pois_id")

            if not poi_id:
                skipped_invalid += 1
                continue

            poi_id = str(poi_id)

            # -------------------------------------------------
            # IMPORTANTE:
            # se il POI è già nel DB, NON facciamo il calcolo
            # spaziale.
            # -------------------------------------------------

            if poi_id in existing_poi_ids:

                skipped_existing += 1
                continue

            coords = (
                poi.get("location") or {}
            ).get(
                "coordinates",
                []
            )

            lat = float(coords[1])
            lon = float(coords[0])

            if lon is None:

                skipped_invalid += 1
                continue

            # -------------------------------------------------
            # CALCOLO DEL NODO PIÙ VICINO
            # -------------------------------------------------

            cursor.execute(
                nearest_query,
                (
                    lon,
                    lat,
                    mode,
                    city_code
                )
            )

            result = cursor.fetchone()

            if not result:

                not_found += 1
                continue

            node_id, dist_m = result

            rows.append(
                (
                    mode,
                    city_code,
                    int(node_id),
                    poi_id,
                    float(dist_m)
                )
            )

            calculated += 1

    # ---------------------------------------------------------
    # SALVATAGGIO
    # ---------------------------------------------------------

    if rows:

        with conn.cursor() as cursor:

            execute_batch(
                cursor,
                insert_query,
                rows,
                page_size=5000
            )

        conn.commit()

    print(
        f"Mode {mode}: "
        f"nuovi calcoli={calculated}, "
        f"già presenti={skipped_existing}, "
        f"non validi={skipped_invalid}, "
        f"senza nodo={not_found}"
    )


def get_distinct_city_codes(conn):
    query = """
        SELECT DISTINCT city_code
        FROM nodes
        WHERE city_code IS NOT NULL
        ORDER BY city_code
    """

    with conn.cursor() as cursor:
        cursor.execute(query)
        return [row[0] for row in cursor.fetchall()]


def main():

    conn = get_postgres_connection()

    try:

        

        for mode in ("walk", "bike"):
            for city_code in get_distinct_city_codes(conn):
                pois_docs = load_pois_from_mongo(city_code=city_code)


                print("Mode:", mode, "City_code:", city_code)

                if not pois_docs:

                    print(
                        "Nessun POI trovato in MongoDB per la modalità ", mode
                    )

                    return

                print(
                    f"POI totali letti da MongoDB per la modalità {mode}: "
                    f"{len(pois_docs)}"
                    )

                map_mode(
                    conn,
                    mode,
                    city_code,  # Sostituisci con il codice della città appropriato
                    pois_docs
                )

    finally:

        conn.close()


if __name__ == "__main__":
    main()
