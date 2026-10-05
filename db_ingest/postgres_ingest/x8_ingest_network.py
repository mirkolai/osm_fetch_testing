import glob
import os
import re
import sys
from pathlib import Path

import osmnx as ox
from psycopg2.extras import execute_batch

# Add parent directory to path so utils can be imported
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.postgres_db import get_postgres_connection
from db_ingest import utils


# ============================================================
# DATABASE SCHEMA
# ============================================================

def ensure_routing_schema(conn):
    """
    Crea lo schema routing se non esiste.

    IMPORTANTE:
    - non cancella dati esistenti
    - non modifica dati esistenti
    - nodes usa UPSERT
    - edges usa INSERT solo se l'arco non esiste
    """

    with conn.cursor() as cursor:

        cursor.execute(
            "CREATE EXTENSION IF NOT EXISTS postgis"
        )

        cursor.execute(
            "CREATE EXTENSION IF NOT EXISTS pgrouting"
        )

        # ----------------------------------------------------
        # NODES
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # EDGES
        # ----------------------------------------------------
        #
        # NON imponiamo qui una UNIQUE constraint.
        #
        # Questo è importante perché la tabella potrebbe essere
        # già esistente e contenere duplicati.
        #
        # Non vogliamo cancellare dati preesistenti.
        #

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

        # ----------------------------------------------------
        # NODE POI
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS node_poi (
                id BIGSERIAL PRIMARY KEY,
                network_mode TEXT NOT NULL DEFAULT 'walk',
                node_id BIGINT NOT NULL,
                poi_id TEXT NOT NULL,
                distance_m DOUBLE PRECISION,

                UNIQUE (
                    network_mode,
                    node_id,
                    poi_id
                )
            )
            """
        )

        # ----------------------------------------------------
        # INDICI NODES
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_nodes_mode_id
            ON nodes(network_mode, id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_nodes_geom
            ON nodes USING GIST(geom)
            """
        )

        # ----------------------------------------------------
        # INDICI EDGES
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_edges_mode_source
            ON edges(network_mode, source)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_edges_mode_target
            ON edges(network_mode, target)
            """
        )

        # Indice utile per velocizzare il controllo
        # "questo arco esiste già?"
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_edges_mode_source_target
            ON edges(network_mode, source, target)
            """
        )

        # ----------------------------------------------------
        # INDICI NODE POI
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_node_poi_mode_node
            ON node_poi(network_mode, node_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_node_poi_poi
            ON node_poi(poi_id)
            """
        )

    conn.commit()


# ============================================================
# FILE / CITY / MODE
# ============================================================

def resolve_mode(path: str):
    """
    Determina la modalità dal nome del file.
    """

    file_name = os.path.basename(path).lower()

    if "bike" in file_name:
        return "bike"

    if "walk" in file_name:
        return "walk"

    return None


def resolve_city_code(path: str) -> str:
    """
    Estrae il codice ISTAT dal nome del file.

    Esempio:
        001272 walk.graphml.gz
        -> 001272
    """

    name = Path(path).name

    match = re.search(r"(\d{6})", name)

    if match:
        return match.group(1)

    return name.split(" ")[0]


# ============================================================
# NODES
# ============================================================

def upsert_nodes(conn, mode: str, nodes_rows):
    """
    Inserisce i nodi.

    Se il nodo esiste già:
    - non viene duplicato
    - vengono aggiornate le coordinate

    Questo non cancella nessun nodo.
    """

    if not nodes_rows:
        return

    query = """
        INSERT INTO nodes (
            id,
            network_mode,
            x,
            y,
            geom
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            ST_SetSRID(
                ST_MakePoint(%s, %s),
                4326
            )
        )

        ON CONFLICT (
            network_mode,
            id
        )

        DO UPDATE SET
            x = EXCLUDED.x,
            y = EXCLUDED.y,
            geom = EXCLUDED.geom
    """

    with conn.cursor() as cursor:

        execute_batch(
            cursor,
            query,
            nodes_rows,
            page_size=5000
        )

    conn.commit()


# ============================================================
# EDGES
# ============================================================

def insert_edges(conn, edge_rows):
    """
    Inserisce gli archi che non sono già presenti.

    IMPORTANTE:
    - non cancella nulla
    - non modifica archi esistenti
    - evita duplicati
    - funziona anche se la tabella edges contiene già
      duplicati provenienti da una precedente importazione
    """

    if not edge_rows:
        return

    query = """
        INSERT INTO edges (
            network_mode,
            source,
            target,
            cost,
            geom
        )
        SELECT
            data.network_mode,
            data.source,
            data.target,
            data.cost,
            ST_SetSRID(
                ST_MakeLine(
                    ST_MakePoint(
                        data.ux,
                        data.uy
                    ),
                    ST_MakePoint(
                        data.vx,
                        data.vy
                    )
                ),
                4326
            )
        FROM (
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
        ) AS data(
            network_mode,
            source,
            target,
            cost,
            ux,
            uy,
            vx,
            vy
        )
        WHERE NOT EXISTS (
            SELECT 1
            FROM edges e
            WHERE e.network_mode = data.network_mode
              AND e.source = data.source
              AND e.target = data.target
        )
    """

    inserted = 0

    with conn.cursor() as cursor:

        for row in edge_rows:

            cursor.execute(
                query,
                row
            )

            inserted += cursor.rowcount

    conn.commit()

    print(
        f"Archi nuovi inseriti: {inserted} / "
        f"archi controllati: {len(edge_rows)}"
    )


# ============================================================
# GRAPHML INGEST
# ============================================================

def ingest_graphml(path: str, conn):

    mode = resolve_mode(path)

    if mode is None:

        print(
            f"Skip {path}: "
            f"mode non riconosciuta"
        )

        return

    city_code = resolve_city_code(path)

    print()
    print("=" * 70)
    print(
        f"Ingest {path}"
    )
    print(
        f"city={city_code} "
        f"mode={mode}"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # LOAD GRAPH
    # --------------------------------------------------------

    graph = ox.load_graphml(path)

    print(
        f"Grafo caricato: "
        f"{graph.number_of_nodes()} nodi, "
        f"{graph.number_of_edges()} archi"
    )

    # --------------------------------------------------------
    # NODI
    # --------------------------------------------------------

    nodes_rows = []

    for node_id, data in graph.nodes(data=True):

        try:
            x = float(data["x"])
            y = float(data["y"])

            nodes_rows.append(
                (
                    int(node_id),
                    mode,
                    x,
                    y,
                    x,
                    y
                )
            )

        except (KeyError, TypeError, ValueError) as exc:

            print(
                f"Skip nodo {node_id}: "
                f"coordinate non valide ({exc})"
            )

    if nodes_rows:

        print(
            f"Controllo {len(nodes_rows)} nodi..."
        )

        upsert_nodes(
            conn,
            mode,
            nodes_rows
        )

        print(
            f"Nodi processati: "
            f"{len(nodes_rows)}"
        )

    # --------------------------------------------------------
    # ARCHI
    # --------------------------------------------------------

    edge_rows = []

    # Set locale per evitare di mandare al DB più volte
    # lo stesso source -> target proveniente dal GraphML.
    seen_edges = set()

    for u, v, data in graph.edges(data=True):

        try:

            source = int(u)
            target = int(v)

            edge_key = (
                mode,
                source,
                target
            )

            if edge_key in seen_edges:
                continue

            seen_edges.add(edge_key)

            ux = float(
                graph.nodes[u]["x"]
            )

            uy = float(
                graph.nodes[u]["y"]
            )

            vx = float(
                graph.nodes[v]["x"]
            )

            vy = float(
                graph.nodes[v]["y"]
            )

            cost = float(
                data.get("length", 1.0)
                or 1.0
            )

            edge_rows.append(
                (
                    mode,
                    source,
                    target,
                    cost,
                    ux,
                    uy,
                    vx,
                    vy
                )
            )

        except (KeyError, TypeError, ValueError) as exc:

            print(
                f"Skip edge {u}->{v}: "
                f"dati non validi ({exc})"
            )

    if edge_rows:

        print(
            f"Controllo {len(edge_rows)} archi..."
        )

        insert_edges(
            conn,
            edge_rows
        )

    print()
    print(
        f"Done {path}: "
        f"{len(nodes_rows)} nodi, "
        f"{len(edge_rows)} archi candidati"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    graphml_dir = os.getenv(
        "GRAPHML_DIR",
        "db_ingest/graphml"
    )

    paths = sorted(
        glob.glob(
            os.path.join(
                graphml_dir,
                "*.graphml*"
            )
        )
    )

    if not paths:

        print(
            f"Nessun file trovato in "
            f"{graphml_dir}"
        )

        return

    # --------------------------------------------------------
    # SELEZIONE FILE
    # --------------------------------------------------------

    selected_paths = []

    for path in paths:

        city_code = resolve_city_code(path)

        if not utils.should_process_city(
            city_code
        ):

            print(
                f"Skip {path}: "
                f"{city_code} non in "
                f"CITY_CODE_FILTER"
            )

            continue

        mode = resolve_mode(path)

        if mode is None:

            print(
                f"Skip {path}: "
                f"modalità non riconosciuta"
            )

            continue

        selected_paths.append(path)

    if not selected_paths:

        print(
            "Nessun GraphML compatibile "
            "con CITY_CODE_FILTER"
        )

        return

    print()
    print(
        f"File da processare: "
        f"{len(selected_paths)}"
    )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    conn = get_postgres_connection()

    try:

        ensure_routing_schema(conn)

        # ----------------------------------------------------
        # NESSUN RESET
        # ----------------------------------------------------
        #
        # NON facciamo:
        #
        # DELETE FROM nodes
        # DELETE FROM edges
        #
        # I dati esistenti rimangono.
        # ----------------------------------------------------

        for index, path in enumerate(
            selected_paths,
            start=1
        ):

            print()
            print(
                f"[{index}/{len(selected_paths)}] "
                f"Processing {path}"
            )

            try:

                ingest_graphml(
                    path,
                    conn
                )

            except Exception as exc:

                # Rollback della transazione corrente
                # senza perdere i dati già committati
                # dai file precedenti.
                conn.rollback()

                print(
                    f"ERRORE durante "
                    f"l'importazione di {path}:"
                )

                print(
                    f"{type(exc).__name__}: {exc}"
                )

                # Rilanciamo l'errore per permettere
                # al pipeline runner di sapere che
                # questa fase è fallita.
                raise

    finally:

        conn.close()


if __name__ == "__main__":
    main()

