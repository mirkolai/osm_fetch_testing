import json
import math
import os
from pathlib import Path
from time import perf_counter
from typing import Dict, Iterable, List, Optional, Tuple

from psycopg2.extras import execute_batch

from backend.Isochrones import get_isocronewalk_by_node_id
from backend.Parameters import compute_area_km2_from_iso
from backend.mongo_db import db as mongo_db
from backend.postgres_db import get_postgres_connection


# Velocita canonical per mode: una sola velocita per mantenere la matrice N x T x C.
MODE_VELOCITY_KMH: Dict[str, int] = {
    "walk": 5,
    "slow_walk": 2,
    "bike": 15,
}

# Tempi canonical condivisi con lo user study.
TRAVEL_TIMES_MIN: List[int] = [5, 10, 15, 20]

TABLE_NAME = "precomputed_metrics_rows"
PHASE_ORDER = ("reachable", "counts", "area", "proximity", "upsert")
SETUP_PHASE_ORDER = ("city_setup", "load_processed_keys", "mode_prep")
MODE_HEARTBEAT_SECONDS = 10.0


def _load_atomic_categories() -> List[str]:
    categories_path = Path(__file__).resolve().parents[2] / "backend" / "categories.json"
    with categories_path.open("r", encoding="utf-8") as file_obj:
        categories_by_group = json.load(file_obj)

    ordered: List[str] = []
    seen = set()
    for _, values in categories_by_group.items():
        for category in values:
            if category not in seen:
                seen.add(category)
                ordered.append(category)
    return ordered


def _render_progress_bar(current: int, total: int, width: int = 28) -> str:
    if total <= 0:
        return "[" + ("-" * width) + "]"
    filled = int((current / total) * width)
    if filled > width:
        filled = width
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def _format_phase_averages(phase_totals: Dict[str, float], phase_counts: Dict[str, int]) -> str:
    parts: List[str] = []
    for phase in PHASE_ORDER:
        count = phase_counts.get(phase, 0)
        if count <= 0:
            continue
        avg_ms = (phase_totals.get(phase, 0.0) / float(count)) * 1000.0
        parts.append(f"{phase}:{avg_ms:.1f}ms")
    return " | ".join(parts) if parts else "n/a"


def _merge_phase_stats(
    target_totals: Dict[str, float],
    target_counts: Dict[str, int],
    source_totals: Dict[str, float],
    source_counts: Dict[str, int],
) -> None:
    for phase in PHASE_ORDER:
        target_totals[phase] = target_totals.get(phase, 0.0) + source_totals.get(phase, 0.0)
        target_counts[phase] = target_counts.get(phase, 0) + source_counts.get(phase, 0)


def _format_setup_averages(setup_totals: Dict[str, float], setup_counts: Dict[str, int]) -> str:
    parts: List[str] = []
    for phase in SETUP_PHASE_ORDER:
        count = setup_counts.get(phase, 0)
        if count <= 0:
            continue
        avg_ms = (setup_totals.get(phase, 0.0) / float(count)) * 1000.0
        parts.append(f"{phase}:{avg_ms:.1f}ms")
    return " | ".join(parts) if parts else "n/a"


def _merge_setup_stats(
    target_totals: Dict[str, float],
    target_counts: Dict[str, int],
    source_totals: Dict[str, float],
    source_counts: Dict[str, int],
) -> None:
    for phase in SETUP_PHASE_ORDER:
        target_totals[phase] = target_totals.get(phase, 0.0) + source_totals.get(phase, 0.0)
        target_counts[phase] = target_counts.get(phase, 0) + source_counts.get(phase, 0)


def _mode_to_travel_mode(mode: str) -> str:
    if mode == "bike":
        return "bike"
    return "walking"


def _mode_to_network_mode(mode: str) -> str:
    if mode == "bike":
        return "bike"
    return "walk"


def _ensure_table(conn) -> None:
    create_sql = f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            city_code TEXT NOT NULL,
            neighbourhood_id TEXT,
            network_mode TEXT NOT NULL,
            node_id BIGINT NOT NULL,
            travel_time INTEGER NOT NULL,
            category_primary_counts INTEGER[] NOT NULL DEFAULT '{{}}',
            category_secondary_counts INTEGER[] NOT NULL DEFAULT '{{}}',
            isochrone_area_km2 DOUBLE PRECISION NOT NULL DEFAULT 0,
            total_pois INTEGER NOT NULL DEFAULT 0,
            density_15m_all_services DOUBLE PRECISION,
            entropy_15m_all_services DOUBLE PRECISION,
            proximity_value DOUBLE PRECISION,
            PRIMARY KEY (network_mode, node_id, travel_time)
        );

        ALTER TABLE {TABLE_NAME}
        ADD COLUMN IF NOT EXISTS density_15m_all_services DOUBLE PRECISION;

        ALTER TABLE {TABLE_NAME}
        ADD COLUMN IF NOT EXISTS entropy_15m_all_services DOUBLE PRECISION;

        CREATE INDEX IF NOT EXISTS idx_precomputed_metrics_city
        ON {TABLE_NAME}(city_code);

        CREATE INDEX IF NOT EXISTS idx_precomputed_metrics_neighbourhood
        ON {TABLE_NAME}(neighbourhood_id);

        CREATE INDEX IF NOT EXISTS idx_precomputed_metrics_city_mode_time
        ON {TABLE_NAME}(city_code, network_mode, travel_time);

        CREATE INDEX IF NOT EXISTS idx_precomputed_metrics_node
        ON {TABLE_NAME}(node_id);
    """
    with conn.cursor() as cursor:
        cursor.execute(create_sql)
    conn.commit()


def _ensure_routing_indexes(conn) -> None:
    create_sql = """
        CREATE INDEX IF NOT EXISTS idx_edges_mode_source
        ON edges(network_mode, source);

        CREATE INDEX IF NOT EXISTS idx_edges_mode_target
        ON edges(network_mode, target);
    """
    with conn.cursor() as cursor:
        cursor.execute(create_sql)
    conn.commit()


def _fetch_reachable_pois(
    conn,
    node_id: int,
    max_distance_m: float,
    network_mode: str,
    graph_sql: Optional[str] = None,
) -> List[Tuple[str, float]]:
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
        SELECT
            np.poi_id,
            MIN(reachable.agg_cost + COALESCE(np.distance_m, 0)) AS distance
        FROM reachable
        JOIN node_poi np ON np.node_id = reachable.node AND np.network_mode = %s
        GROUP BY np.poi_id
        HAVING MIN(reachable.agg_cost + COALESCE(np.distance_m, 0)) < %s
        ORDER BY distance ASC
    """

    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (node_id, max_distance_m, network_mode, max_distance_m))
            rows = cursor.fetchall()
    except Exception:
        return []

    result: List[Tuple[str, float]] = []
    for poi_id, distance in rows:
        result.append((str(poi_id), float(distance)))
    return result


def _compute_area(
    conn,
    node_id: int,
    minute: int,
    velocity: int,
    mode: str,
    graph_sql: Optional[str] = None,
) -> float:
    status, _, isochrone_data = get_isocronewalk_by_node_id(
        node_id=node_id,
        minute=minute,
        velocity=velocity,
        travel_mode=_mode_to_travel_mode(mode),
        conn=conn,
        graph_sql=graph_sql,
    )
    if status != 200 or not isochrone_data:
        return 0.0
    return float(compute_area_km2_from_iso(isochrone_data))


def _compute_counts(
    reachable: List[Tuple[str, float]],
    category_to_idx: Dict[str, int],
) -> Tuple[List[int], List[int], int]:
    primary_counts = [0] * len(category_to_idx)
    secondary_counts = [0] * len(category_to_idx)

    if not reachable:
        return primary_counts, secondary_counts, 0

    poi_ids = [poi_id for poi_id, _ in reachable]
    pois_docs = list(
        mongo_db["pois"].find(
            {"pois_id": {"$in": poi_ids}},
            {"_id": 0, "pois_id": 1, "categories": 1},
        )
    )
    by_id = {str(doc["pois_id"]): doc for doc in pois_docs}

    for poi_id in poi_ids:
        doc = by_id.get(poi_id)
        if not doc:
            continue

        categories = doc.get("categories") or {}
        primary = categories.get("primary")
        if primary in category_to_idx:
            primary_counts[category_to_idx[primary]] += 1

        alternate = categories.get("alternate") or []
        for alt in dict.fromkeys(alternate):
            if alt in category_to_idx:
                secondary_counts[category_to_idx[alt]] += 1

    return primary_counts, secondary_counts, len(poi_ids)


def _compute_proximity_minutes(reachable: List[Tuple[str, float]], velocity_kmh: int) -> Optional[float]:
    if not reachable:
        return None

    speed_m_per_min = (velocity_kmh * 1000.0) / 60.0
    if speed_m_per_min <= 0:
        return None

    times = [distance / speed_m_per_min for _, distance in reachable]
    return float(max(times)) if times else None


def _compute_density_all_services(total_pois: int, area_km2: float) -> float:
    if total_pois <= 0 or area_km2 <= 0:
        return 0.0
    return float(total_pois) / float(area_km2)


def _compute_entropy_all_services(primary_counts: List[int], categories_count: int) -> float:
    if categories_count <= 1:
        return 0.0

    total = float(sum(primary_counts or []))
    if total <= 0:
        return 0.0

    entropy = 0.0
    for value in (primary_counts or []):
        if value > 0:
            p = float(value) / total
            entropy -= p * math.log2(p)

    max_entropy = math.log2(float(categories_count))
    if max_entropy <= 0:
        return 0.0
    return float(entropy / max_entropy)


def _iter_city_nodes() -> Iterable[Tuple[str, Dict[int, Optional[str]]]]:
    from db_ingest import utils as _utils
    collection = mongo_db["neighbourhood_polygon"]

    for city_doc in collection.find({}, {"_id": 0, "PRO_COM_T": 1, "neighbourhoods.id": 1, "neighbourhoods.nodes": 1}):
        city_code = str(city_doc.get("PRO_COM_T"))
        if not _utils.should_process_city(city_code):
            continue
        node_to_neighbourhood: Dict[int, Optional[str]] = {}

        for neighbourhood in city_doc.get("neighbourhoods") or []:
            neighbourhood_id = str(neighbourhood.get("id"))
            for node in neighbourhood.get("nodes") or []:
                try:
                    node_id = int(node)
                except Exception:
                    continue
                # Se un nodo appare in piu quartieri, mantiene il primo mapping trovato.
                node_to_neighbourhood.setdefault(node_id, neighbourhood_id)

        if node_to_neighbourhood:
            yield city_code, node_to_neighbourhood


def _upsert_rows(conn, rows: List[Tuple]) -> None:
    if not rows:
        return

    upsert_sql = f"""
        INSERT INTO {TABLE_NAME} (
            city_code,
            neighbourhood_id,
            network_mode,
            node_id,
            travel_time,
            category_primary_counts,
            category_secondary_counts,
            isochrone_area_km2,
            total_pois,
            density_15m_all_services,
            entropy_15m_all_services,
            proximity_value
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (network_mode, node_id, travel_time)
        DO UPDATE SET
            city_code = EXCLUDED.city_code,
            neighbourhood_id = EXCLUDED.neighbourhood_id,
            category_primary_counts = EXCLUDED.category_primary_counts,
            category_secondary_counts = EXCLUDED.category_secondary_counts,
            isochrone_area_km2 = EXCLUDED.isochrone_area_km2,
            total_pois = EXCLUDED.total_pois,
            density_15m_all_services = EXCLUDED.density_15m_all_services,
            entropy_15m_all_services = EXCLUDED.entropy_15m_all_services,
            proximity_value = EXCLUDED.proximity_value
    """

    with conn.cursor() as cursor:
        execute_batch(cursor, upsert_sql, rows, page_size=500)
    conn.commit()


def _load_routable_nodes_by_network_mode(conn) -> Dict[str, set[int]]:
    """Carica i nodi instradabili per mode (presenti almeno in un edge come source/target)."""
    query = """
        SELECT network_mode, node_id
        FROM (
            SELECT network_mode, source AS node_id FROM edges
            UNION
            SELECT network_mode, target AS node_id FROM edges
        ) t
    """

    by_mode: Dict[str, set[int]] = {}
    with conn.cursor() as cursor:
        cursor.execute(query)
        for network_mode, node_id in cursor.fetchall():
            try:
                by_mode.setdefault(str(network_mode), set()).add(int(node_id))
            except Exception:
                continue
    return by_mode


def _load_existing_processed_keys_for_nodes(conn, node_ids: set[int]) -> set[Tuple[str, int, int]]:
    """Carica solo le chiavi gia presenti per i nodi della citta corrente."""
    if not node_ids:
        return set()

    query = f"""
        SELECT network_mode, node_id, travel_time
        FROM {TABLE_NAME}
        WHERE node_id = ANY(%s)
          AND density_15m_all_services IS NOT NULL
          AND entropy_15m_all_services IS NOT NULL
    """

    processed: set[Tuple[str, int, int]] = set()
    with conn.cursor() as cursor:
        cursor.execute(query, (list(node_ids),))
        for network_mode, node_id, travel_time in cursor.fetchall():
            try:
                processed.add((str(network_mode), int(node_id), int(travel_time)))
            except Exception:
                continue
    return processed


def _prepare_city_nodes_temp_table(conn, node_ids: set[int]) -> None:
    """Prepara tabella temporanea con i nodi della citta per filtrare il grafo pgRouting."""
    with conn.cursor() as cursor:
        cursor.execute("CREATE TEMP TABLE IF NOT EXISTS tmp_city_nodes (node_id BIGINT PRIMARY KEY)")
        cursor.execute("TRUNCATE tmp_city_nodes")

    rows = [(int(node_id),) for node_id in node_ids]
    if rows:
        with conn.cursor() as cursor:
            execute_batch(
                cursor,
                "INSERT INTO tmp_city_nodes (node_id) VALUES (%s) ON CONFLICT (node_id) DO NOTHING",
                rows,
                page_size=5000,
            )
    conn.commit()


def _build_city_graph_sql(network_mode: str) -> str:
    return (
        "SELECT e.id, e.source, e.target, e.cost, e.cost AS reverse_cost "
        "FROM edges e "
        "JOIN tmp_city_nodes src ON src.node_id = e.source "
        "JOIN tmp_city_nodes tgt ON tgt.node_id = e.target "
        f"WHERE e.network_mode = ''{network_mode}''"
    )


def main() -> None:
    categories = _load_atomic_categories()
    category_to_idx = {category: idx for idx, category in enumerate(categories)}

    conn = get_postgres_connection()
    try:
        _ensure_table(conn)
        _ensure_routing_indexes(conn)
        routable_nodes_by_mode = _load_routable_nodes_by_network_mode(conn)

        total_rows = 0
        total_skipped_unroutable = 0
        total_skipped_already_processed = 0
        global_phase_totals = {phase: 0.0 for phase in PHASE_ORDER}
        global_phase_counts = {phase: 0 for phase in PHASE_ORDER}
        global_setup_totals = {phase: 0.0 for phase in SETUP_PHASE_ORDER}
        global_setup_counts = {phase: 0 for phase in SETUP_PHASE_ORDER}
        for city_code, node_to_neighbourhood in _iter_city_nodes():
            print(f"Processing city {city_code} with {len(node_to_neighbourhood)} nodes")
            batch: List[Tuple] = []
            city_skipped_unroutable = 0
            city_skipped_already_processed = 0

            city_node_ids = set(node_to_neighbourhood.keys())
            city_phase_totals = {phase: 0.0 for phase in PHASE_ORDER}
            city_phase_counts = {phase: 0 for phase in PHASE_ORDER}
            city_setup_totals = {phase: 0.0 for phase in SETUP_PHASE_ORDER}
            city_setup_counts = {phase: 0 for phase in SETUP_PHASE_ORDER}

            setup_t0 = perf_counter()
            _prepare_city_nodes_temp_table(conn, city_node_ids)
            city_setup_totals["city_setup"] += perf_counter() - setup_t0
            city_setup_counts["city_setup"] += 1

            setup_t0 = perf_counter()
            city_already_processed_keys = _load_existing_processed_keys_for_nodes(conn, city_node_ids)
            city_setup_totals["load_processed_keys"] += perf_counter() - setup_t0
            city_setup_counts["load_processed_keys"] += 1

            city_total_work_units = len(city_node_ids) * len(MODE_VELOCITY_KMH)
            city_completed_work_units = 0

            for mode, velocity in MODE_VELOCITY_KMH.items():
                mode_started_at = perf_counter()
                network_mode = _mode_to_network_mode(mode)
                graph_sql = _build_city_graph_sql(network_mode)
                routable_nodes = routable_nodes_by_mode.get(network_mode, set())

                city_routable_node_ids = city_node_ids.intersection(routable_nodes)
                city_unroutable_count = len(city_node_ids) - len(city_routable_node_ids)
                city_skipped_unroutable += city_unroutable_count * len(TRAVEL_TIMES_MIN)
                mode_total_units = len(city_routable_node_ids) * len(TRAVEL_TIMES_MIN)
                mode_completed_units = 0
                mode_last_heartbeat_at = perf_counter()

                for node_id in city_routable_node_ids:
                    neighbourhood_id = node_to_neighbourhood.get(node_id)
                    for minute in TRAVEL_TIMES_MIN:
                        mode_completed_units += 1
                        row_key = (mode, node_id, minute)
                        if row_key in city_already_processed_keys:
                            city_skipped_already_processed += 1
                            now = perf_counter()
                            if now - mode_last_heartbeat_at >= MODE_HEARTBEAT_SECONDS:
                                mode_bar = _render_progress_bar(mode_completed_units, mode_total_units)
                                elapsed_s = now - mode_started_at
                                avg_info = _format_phase_averages(city_phase_totals, city_phase_counts)
                                print(
                                    f"[city {city_code}] mode={mode} heartbeat combos(node*minute) {mode_completed_units}/{mode_total_units} {mode_bar} | elapsed {elapsed_s:.1f}s | avg {avg_info}",
                                    flush=True,
                                )
                                mode_last_heartbeat_at = now
                            continue

                        max_distance_m = (velocity * 1000.0 / 60.0) * minute

                        t0 = perf_counter()
                        reachable = _fetch_reachable_pois(
                            conn,
                            node_id,
                            max_distance_m,
                            network_mode,
                            graph_sql=graph_sql,
                        )
                        city_phase_totals["reachable"] += perf_counter() - t0
                        city_phase_counts["reachable"] += 1

                        t0 = perf_counter()
                        primary_counts, secondary_counts, total_pois = _compute_counts(
                            reachable=reachable,
                            category_to_idx=category_to_idx,
                        )
                        city_phase_totals["counts"] += perf_counter() - t0
                        city_phase_counts["counts"] += 1

                        t0 = perf_counter()
                        area_km2 = _compute_area(
                            conn=conn,
                            node_id=node_id,
                            minute=minute,
                            velocity=velocity,
                            mode=mode,
                            graph_sql=graph_sql,
                        )
                        city_phase_totals["area"] += perf_counter() - t0
                        city_phase_counts["area"] += 1

                        t0 = perf_counter()
                        proximity_value = _compute_proximity_minutes(reachable=reachable, velocity_kmh=velocity)
                        city_phase_totals["proximity"] += perf_counter() - t0
                        city_phase_counts["proximity"] += 1

                        # Manteniamo i nomi colonna legacy (*_15m_all_services) per compatibilita,
                        # ma ora i valori vengono calcolati per tutti i travel_time canonical.
                        density_15m_all_services = _compute_density_all_services(
                            total_pois=total_pois,
                            area_km2=area_km2,
                        )
                        entropy_15m_all_services = _compute_entropy_all_services(
                            primary_counts=primary_counts,
                            categories_count=len(category_to_idx),
                        )

                        batch.append(
                            (
                                city_code,
                                neighbourhood_id,
                                mode,
                                node_id,
                                minute,
                                primary_counts,
                                secondary_counts,
                                area_km2,
                                total_pois,
                                density_15m_all_services,
                                entropy_15m_all_services,
                                proximity_value,
                            )
                        )

                        if len(batch) >= 1000:
                            upsert_started = perf_counter()
                            _upsert_rows(conn, batch)
                            upsert_elapsed = perf_counter() - upsert_started
                            city_phase_totals["upsert"] += upsert_elapsed
                            city_phase_counts["upsert"] += len(batch)
                            for row in batch:
                                city_already_processed_keys.add((str(row[2]), int(row[3]), int(row[4])))
                            total_rows += len(batch)
                            print(f"Inserted/updated {total_rows} rows")
                            batch = []

                        now = perf_counter()
                        if now - mode_last_heartbeat_at >= MODE_HEARTBEAT_SECONDS:
                            mode_bar = _render_progress_bar(mode_completed_units, mode_total_units)
                            elapsed_s = now - mode_started_at
                            avg_info = _format_phase_averages(city_phase_totals, city_phase_counts)
                            print(
                                f"[city {city_code}] mode={mode} heartbeat combos(node*minute) {mode_completed_units}/{mode_total_units} {mode_bar} | elapsed {elapsed_s:.1f}s | avg {avg_info}",
                                flush=True,
                            )
                            mode_last_heartbeat_at = now

                city_completed_work_units += len(city_node_ids)
                city_setup_totals["mode_prep"] += perf_counter() - mode_started_at
                city_setup_counts["mode_prep"] += 1
                progress_bar = _render_progress_bar(city_completed_work_units, city_total_work_units)
                avg_info = _format_phase_averages(city_phase_totals, city_phase_counts)
                print(
                    f"[city {city_code}] mode={mode} city-mode-pass progress(nodes*mode) {city_completed_work_units}/{city_total_work_units} {progress_bar} | avg {avg_info}",
                    flush=True,
                )

            if batch:
                upsert_started = perf_counter()
                _upsert_rows(conn, batch)
                upsert_elapsed = perf_counter() - upsert_started
                city_phase_totals["upsert"] += upsert_elapsed
                city_phase_counts["upsert"] += len(batch)
                for row in batch:
                    city_already_processed_keys.add((str(row[2]), int(row[3]), int(row[4])))
                total_rows += len(batch)
                print(f"Inserted/updated {total_rows} rows")

            if city_skipped_unroutable:
                total_skipped_unroutable += city_skipped_unroutable
                print(f"Skipped {city_skipped_unroutable} unroutable rows in city {city_code}")

            if city_skipped_already_processed:
                total_skipped_already_processed += city_skipped_already_processed
                print(f"Skipped {city_skipped_already_processed} already-processed rows in city {city_code}")

            city_avg_info = _format_phase_averages(city_phase_totals, city_phase_counts)
            city_setup_avg_info = _format_setup_averages(city_setup_totals, city_setup_counts)
            print(f"[city {city_code}] average phase times: {city_avg_info}")
            print(f"[city {city_code}] setup/mode times: {city_setup_avg_info}")
            _merge_phase_stats(global_phase_totals, global_phase_counts, city_phase_totals, city_phase_counts)
            _merge_setup_stats(global_setup_totals, global_setup_counts, city_setup_totals, city_setup_counts)

        print(f"Completed. Total rows inserted/updated: {total_rows}")
        if total_skipped_unroutable:
            print(f"Total skipped unroutable rows: {total_skipped_unroutable}")
        if total_skipped_already_processed:
            print(f"Total skipped already-processed rows: {total_skipped_already_processed}")
        print(f"Global average phase times: {_format_phase_averages(global_phase_totals, global_phase_counts)}")
        print(f"Global setup/mode times: {_format_setup_averages(global_setup_totals, global_setup_counts)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
