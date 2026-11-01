"""
Calcola le metriche dei POI raggiungibili e le salva in PostgreSQL.
Versione ULTRA-FAST: Rete in RAM (NetworkX/SciPy) + POI in RAM.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np
from psycopg2.extras import execute_batch
from scipy.spatial import ConvexHull

from backend.mongo_db import db as mongo_db
from backend.postgres_db import get_postgres_connection

TABLE_NAME = "precomputed_metrics_rows"
TRAVEL_TIMES_MIN = (5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60)
SPEEDS_KMH = {
    "walk": (2, 5),
    "bike": (15,),
}
BATCH_SIZE = 1000


def _load_categories() -> Tuple[List[str], List[str]]:
    path = Path(__file__).resolve().parents[2] / "backend" / "categories.json"
    with path.open("r", encoding="utf-8") as file_obj:
        groups = json.load(file_obj)
    primary_categories = sorted(groups.keys())
    secondary_categories = sorted({cat for values in groups.values() for cat in values})
    return primary_categories, secondary_categories


def _preload_poi_categories() -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    """Carica i POI da MongoDB in RAM."""
    print("Pre-caricamento POI da MongoDB in RAM...")
    poi_map = {}
    projection = {"_id": 0, "pois_id": 1, "taxonomy.hierarchy": 1}

    for poi in mongo_db["pois"].find({}, projection):
        poi_id = str(poi.get("pois_id"))
        hierarchy = (poi.get("taxonomy") or {}).get("hierarchy") or []

        prim = hierarchy[0] if len(hierarchy) >= 1 else None
        sec = hierarchy[1] if len(hierarchy) >= 2 else None
        poi_map[poi_id] = (prim, sec)

    print(f"Caricati {len(poi_map)} POI in RAM.")
    return poi_map


def _get_cities_to_process() -> List[str]:
    from db_ingest import utils

    cities = []
    for city in mongo_db["neighbourhood_polygon"].find({}, {"_id": 0, "PRO_COM_T": 1}):
        city_code = str(city.get("PRO_COM_T"))
        if utils.should_process_city(city_code):
            cities.append(city_code)
    return cities


def _get_city_network_node_ids(city_code: str, network_mode: str) -> set[int]:
    projection = {"_id": 0, "node_id": 1}
    query = {"city_code": city_code, "network_mode": network_mode}
    return {
        int(node["node_id"])
        for node in mongo_db["nodes"].find(query, projection)
        if node.get("node_id") is not None
    }


def _get_completed_node_ids(
    conn, city_code: str, network_mode: str, speeds: Tuple[int, ...]
) -> set[int]:
    query = f"""
        SELECT node_id
        FROM {TABLE_NAME}
        WHERE city_code = %s
          AND network_mode = %s
          AND travel_time = ANY(%s)
          AND velocity_kmh = ANY(%s)
        GROUP BY node_id
        HAVING COUNT(DISTINCT (travel_time, velocity_kmh)) = %s
    """
    expected_rows_per_node = len(TRAVEL_TIMES_MIN) * len(speeds)

    with conn.cursor() as cursor:
        cursor.execute(
            query,
            (
                city_code,
                network_mode,
                list(TRAVEL_TIMES_MIN),
                list(speeds),
                expected_rows_per_node,
            ),
        )
        return {int(row[0]) for row in cursor.fetchall()}


def _get_neighbourhood_node_pairs(city_code: str,mode: str) -> Dict[int, Optional[str]]:
    from db_ingest import utils

    projection = {
        "_id": 0,
        "PRO_COM_T": 1,
        "neighbourhoods.id": 1,
        "neighbourhoods.nodes": 1,
    }
    node_to_neighbourhood: Dict[int, Optional[str]] = {}

    for city in mongo_db["neighbourhood_polygon"].find({"PRO_COM_T": city_code,"mode": mode}, projection):
        if not utils.should_process_city(str(city.get("PRO_COM_T"))):
            continue

        for neighbourhood in city.get("neighbourhoods") or []:
            neighbourhood_id = neighbourhood.get("id")
            for value in neighbourhood.get("nodes") or []:
                try:
                    node_id = int(value)
                    node_to_neighbourhood[node_id] = (
                        str(neighbourhood_id) if neighbourhood_id is not None else None
                    )
                except (TypeError, ValueError):
                    continue

    return node_to_neighbourhood


def _load_city_graph_and_pois(
    conn, city_code: str, network_mode: str
) -> Tuple[nx.Graph, Dict[int, List[Tuple[str, float]]], Dict[int, Tuple[float, float]]]:
    """Carica l'intero grafo della città, le coordinate dei nodi e le associazioni nodi-POI in RAM."""
    G = nx.Graph()
    node_coords: Dict[int, Tuple[float, float]] = {}

    with conn.cursor() as cursor:
        # 1. Carica gli archi della città
        cursor.execute(
            """
            SELECT source, target, cost 
            FROM edges 
            WHERE city_code = %s AND network_mode = %s
            """,
            (city_code, network_mode),
        )
        for src, tgt, cost in cursor.fetchall():
            G.add_edge(int(src), int(tgt), weight=float(cost))

        # 2. Carica le coordinate WGS84 dei nodi per il calcolo dell'Hull
        cursor.execute(
            """
            SELECT n.id, ST_X(n.geom), ST_Y(n.geom) 
            FROM nodes n
            """
        )
        for n_id, lon, lat in cursor.fetchall():
            if n_id in G:
                node_coords[int(n_id)] = (float(lon), float(lat))

        # 3. Carica la mappa nodo -> POI
        cursor.execute(
            """
            SELECT node_id, poi_id, COALESCE(distance_m, 0)
            FROM node_poi
            WHERE network_mode = %s
            """,
            (network_mode,),
        )
        node_to_pois: Dict[int, List[Tuple[str, float]]] = {}
        for n_id, poi_id, dist in cursor.fetchall():
            n_id = int(n_id)
            if n_id in G:
                node_to_pois.setdefault(n_id, []).append((str(poi_id), float(dist)))

    return G, node_to_pois, node_coords


def _calculate_hull_area_km2(points: List[Tuple[float, float]]) -> float:
    """Calcola l'area dell'Hull sui punti WGS84 approssimando i gradi in km."""
    if len(points) < 3:
        return 0.0
    try:
        pts = np.array(points)
        # Converti approssimativamente gradi -> km (1 deg lat ~ 111km, lon regolata da cos(lat))
        mean_lat = np.radians(np.mean(pts[:, 1]))
        pts_km = np.column_stack(
            (pts[:, 0] * 111.0 * np.cos(mean_lat), pts[:, 1] * 111.0)
        )
        hull = ConvexHull(pts_km)
        return float(hull.volume)  # In 2D, hull.volume restituisce l'Area
    except Exception:
        return 0.0


def _ensure_table(conn) -> None:
    create_table = f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            city_code TEXT NOT NULL,
            neighbourhood_id TEXT,
            network_mode TEXT NOT NULL,
            travel_time INTEGER NOT NULL,
            velocity_kmh INTEGER NOT NULL,
            node_id BIGINT NOT NULL,
            category_primary_counts INTEGER[] NOT NULL,
            category_secondary_counts INTEGER[] NOT NULL,
            isochrone_area_km2 DOUBLE PRECISION NOT NULL,
            total_pois INTEGER NOT NULL,
            PRIMARY KEY (
                city_code,
                network_mode,
                velocity_kmh,
                node_id,
                travel_time
            )
        );
    """

    indexes = [
        f"""
        CREATE INDEX IF NOT EXISTS idx_metrics_city_network_node
        ON {TABLE_NAME} (
            city_code,
            network_mode,
            node_id
        );
        """,
        f"""
        CREATE INDEX IF NOT EXISTS idx_metrics_network_velocity_node_time
        ON {TABLE_NAME} (
            network_mode,
            velocity_kmh,
            node_id,
            travel_time
        );
        """,
        f"""
        CREATE INDEX IF NOT EXISTS idx_metrics_city_network_velocity_time
        ON {TABLE_NAME} (
            city_code,
            network_mode,
            velocity_kmh,
            travel_time
        );
        """
    ]

    with conn.cursor() as cursor:
        cursor.execute(create_table)

        for index_sql in indexes:
            cursor.execute(index_sql)

    conn.commit()



def _save_rows(conn, rows: List[Tuple]) -> None:
    if not rows:
        return

    query = f"""
        INSERT INTO {TABLE_NAME} (
            city_code, neighbourhood_id, network_mode, travel_time,
            velocity_kmh, node_id, category_primary_counts,
            category_secondary_counts, isochrone_area_km2,
            total_pois
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (city_code, network_mode, velocity_kmh, node_id, travel_time)
        DO UPDATE SET
            neighbourhood_id = EXCLUDED.neighbourhood_id,
            category_primary_counts = EXCLUDED.category_primary_counts,
            category_secondary_counts = EXCLUDED.category_secondary_counts,
            isochrone_area_km2 = EXCLUDED.isochrone_area_km2,
            total_pois = EXCLUDED.total_pois
    """
    with conn.cursor() as cursor:
        execute_batch(cursor, query, rows, page_size=BATCH_SIZE)
    conn.commit()


def main() -> None:
    primary_categories, secondary_categories = _load_categories()
    primary_idx = {cat: i for i, cat in enumerate(primary_categories)}
    secondary_idx = {cat: i for i, cat in enumerate(secondary_categories)}

    poi_map = _preload_poi_categories()
    conn = get_postgres_connection()

    try:
        _ensure_table(conn)

        for city_code in _get_cities_to_process():

            for network_mode in ("walk", "bike"):
                node_to_neighbourhood = _get_neighbourhood_node_pairs(city_code,network_mode)
                print(f"\nCaricamento grafo in RAM per {city_code} ({network_mode})...")
                G, node_to_pois, node_coords = _load_city_graph_and_pois(
                    conn, city_code, network_mode
                )

                if G.number_of_nodes() == 0:
                    continue

                mongo_node_ids = _get_city_network_node_ids(city_code, network_mode)
                speeds = SPEEDS_KMH[network_mode]
                completed_node_ids = _get_completed_node_ids(
                    conn, city_code, network_mode, speeds
                )
                candidate_nodes = [
                    node_id for node_id in G.nodes() if node_id in mongo_node_ids
                ]
                completed_node_ids.intersection_update(candidate_nodes)
                nodes = [
                    node_id for node_id in candidate_nodes
                    if node_id not in completed_node_ids
                ]
                total_nodes = len(nodes)
                if total_nodes == 0:
                    print(
                        f"Nessun nodo da elaborare per {city_code} "
                        f"({network_mode}); nodi già completati: "
                        f"{len(completed_node_ids)}."
                    )
                    continue

                max_possible_distance = max(speeds) * 1000 / 60 * max(TRAVEL_TIMES_MIN)

                rows = []
                print(
                    f"Elaborazione in corso su {total_nodes} nodi "
                    f"(saltati {len(completed_node_ids)} già completati)..."
                )

                for completed, node_id in enumerate(nodes, start=1):
                    # Dijkstra in RAM fino alla distanza massima
                    node_distances = nx.single_source_dijkstra_path_length(
                        G, node_id, cutoff=max_possible_distance
                    )

                    for travel_time in TRAVEL_TIMES_MIN:
                        for velocity in speeds:
                            cutoff = velocity * 1000 / 60 * travel_time

                            # 1. Trova nodi e punti entro il cutoff
                            reachable_nodes = [
                                n for n, d in node_distances.items() if d <= cutoff
                            ]
                            points = [
                                node_coords[n]
                                for n in reachable_nodes
                                if n in node_coords
                            ]

                            # 2. Calcolo dell'area Hull sui punti in RAM (SciPy)
                            area_km2 = _calculate_hull_area_km2(points)

                            # 3. Raccogli e conta POI
                            primary_counts = [0] * len(primary_idx)
                            secondary_counts = [0] * len(secondary_idx)
                            poi_distances: Dict[str, float] = {}

                            for r_node in reachable_nodes:
                                r_dist = node_distances[r_node]
                                for poi_id, poi_offset in node_to_pois.get(
                                    r_node, []
                                ):
                                    tot_dist = r_dist + poi_offset
                                    if tot_dist <= cutoff:
                                        if (
                                            poi_id not in poi_distances
                                            or tot_dist < poi_distances[poi_id]
                                        ):
                                            poi_distances[poi_id] = tot_dist

                            for poi_id in poi_distances:
                                cat_info = poi_map.get(poi_id)
                                if cat_info:
                                    prim, sec = cat_info
                                    if prim in primary_idx:
                                        primary_counts[primary_idx[prim]] += 1
                                    if sec in secondary_idx:
                                        secondary_counts[secondary_idx[sec]] += 1

                            rows.append(
                                (
                                    city_code,
                                    node_to_neighbourhood.get(node_id),
                                    network_mode,
                                    travel_time,
                                    velocity,
                                    node_id,
                                    primary_counts,
                                    secondary_counts,
                                    area_km2,
                                    len(poi_distances),
                                )
                            )

                            if len(rows) >= BATCH_SIZE:
                                _save_rows(conn, rows)
                                rows.clear()

                    if completed % 100 == 0 or completed == total_nodes:
                        print(
                            f"\rProgresso {city_code} ({network_mode}): {completed*100/total_nodes:.1f}%",
                            end="",
                            flush=True,
                        )

                _save_rows(conn, rows)
                print()

    finally:
        conn.close()


if __name__ == "__main__":
    main()