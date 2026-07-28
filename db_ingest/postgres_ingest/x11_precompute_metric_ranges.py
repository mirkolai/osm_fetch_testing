"""
Precalcola i range delle metriche per le citta gia processate da x10.

Per ogni coppia (city_code, network_mode) salva:
- density_raw_min / max: densita grezza POI / km^2 calcolata dai precompute di x10
- entropy_score_min / max: entropy normalizzata calcolata dalle counts di x10
- closeness_raw_min / max: closeness grezza dalla collection connectivity
- proximity_min / max: range canonico 0..60 minuti

Il risultato viene scritto nella tabella precomputed_metric_ranges.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

from psycopg2.extras import execute_batch

from backend.Connectivity import _compute_closeness_min_max, _resolve_connectivity_collection
from backend.postgres_db import get_postgres_connection


SOURCE_TABLE = "precomputed_metrics_rows"
TARGET_TABLE = "precomputed_metric_ranges"
PROXIMITY_MIN = 0.0
PROXIMITY_MAX = 60.0


def _normalize_city_code(city_code: Any) -> Optional[str]:
    if city_code is None:
        return None

    value = str(city_code).strip()
    if not value:
        return None

    if value.isdigit():
        return value.zfill(6)
    return value


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


def _ensure_table(conn) -> None:
    create_sql = f"""
        CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (
            city_code TEXT NOT NULL,
            network_mode TEXT NOT NULL,
            density_raw_min DOUBLE PRECISION NOT NULL DEFAULT 0,
            density_raw_q1 DOUBLE PRECISION NOT NULL DEFAULT 0,
            density_raw_q3 DOUBLE PRECISION NOT NULL DEFAULT 0,
            density_raw_max DOUBLE PRECISION NOT NULL DEFAULT 0,
            entropy_score_min DOUBLE PRECISION NOT NULL DEFAULT 0,
            entropy_score_q1 DOUBLE PRECISION NOT NULL DEFAULT 0,
            entropy_score_q3 DOUBLE PRECISION NOT NULL DEFAULT 0,
            entropy_score_max DOUBLE PRECISION NOT NULL DEFAULT 0,
            closeness_raw_min DOUBLE PRECISION NOT NULL DEFAULT 0,
            closeness_raw_max DOUBLE PRECISION NOT NULL DEFAULT 0,
            proximity_min DOUBLE PRECISION NOT NULL DEFAULT 0,
            proximity_max DOUBLE PRECISION NOT NULL DEFAULT 60,
            source_rows INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            PRIMARY KEY (city_code, network_mode)
        );

        CREATE INDEX IF NOT EXISTS idx_metric_ranges_city_mode
        ON {TARGET_TABLE}(city_code, network_mode);
    """
    with conn.cursor() as cursor:
        cursor.execute(create_sql)
    conn.commit()


def _fetch_city_mode_groups(conn) -> List[Tuple[str, str]]:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from db_ingest import utils as _utils

    query = f"""
        SELECT DISTINCT city_code, network_mode
        FROM {SOURCE_TABLE}
        WHERE city_code IS NOT NULL
        ORDER BY city_code, network_mode
    """

    groups: List[Tuple[str, str]] = []
    with conn.cursor() as cursor:
        cursor.execute(query)
        for city_code, network_mode in cursor.fetchall():
            normalized_city_code = _normalize_city_code(city_code)
            normalized_network_mode = str(network_mode or "").strip().lower()
            if normalized_city_code and normalized_network_mode:
                if not _utils.should_process_city(normalized_city_code):
                    continue
                groups.append((normalized_city_code, normalized_network_mode))
    return groups


def _fetch_rows_for_city_mode(conn, city_code: str, network_mode: str) -> List[Dict[str, Any]]:
    query = f"""
        SELECT
            category_primary_counts,
            category_secondary_counts,
            isochrone_area_km2,
            total_pois
        FROM {SOURCE_TABLE}
        WHERE city_code = %s
          AND network_mode = %s
    """

    rows: List[Dict[str, Any]] = []
    with conn.cursor() as cursor:
        cursor.execute(query, (city_code, network_mode))
        for row in cursor.fetchall():
            rows.append(
                {
                    "category_primary_counts": list(row[0] or []),
                    "category_secondary_counts": list(row[1] or []),
                    "isochrone_area_km2": float(row[2] or 0.0),
                    "total_pois": int(row[3] or 0),
                }
            )
    return rows


def _compute_density_raw(row: Dict[str, Any]) -> float:
    area_km2 = float(row.get("isochrone_area_km2") or 0.0)
    total_pois = int(row.get("total_pois") or 0)
    if area_km2 <= 0 or total_pois <= 0:
        return 0.0
    return float(total_pois) / float(area_km2)


def _compute_quartiles(values: List[float]) -> Tuple[float, float, float]:
    """Calcola min, Q1 (25° percentile), e Q3 (75° percentile)."""
    if not values:
        return 0.0, 0.0, 0.0
    
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    
    min_val = float(sorted_vals[0])
    max_val = float(sorted_vals[-1])
    
    # Calcola Q1 (25° percentile)
    q1_idx = (n - 1) * 0.25
    q1_lower = int(q1_idx)
    q1_fraction = q1_idx - q1_lower
    if q1_lower + 1 < n:
        q1_val = sorted_vals[q1_lower] * (1 - q1_fraction) + sorted_vals[q1_lower + 1] * q1_fraction
    else:
        q1_val = sorted_vals[q1_lower]
    
    # Calcola Q3 (75° percentile)
    q3_idx = (n - 1) * 0.75
    q3_lower = int(q3_idx)
    q3_fraction = q3_idx - q3_lower
    if q3_lower + 1 < n:
        q3_val = sorted_vals[q3_lower] * (1 - q3_fraction) + sorted_vals[q3_lower + 1] * q3_fraction
    else:
        q3_val = sorted_vals[q3_lower]
    
    return float(q1_val), float(q3_val)


def _compute_entropy_score(row: Dict[str, Any], atomic_categories_count: int) -> float:
    if atomic_categories_count <= 0:
        return 0.0

    primary_counts = row.get("category_primary_counts") or []
    total_pois = int(row.get("total_pois") or 0)
    if total_pois <= 0:
        return 0.0

    counts = [primary_counts[idx] if idx < len(primary_counts) else 0 for idx in range(atomic_categories_count)]
    total = float(sum(counts))
    if total <= 0:
        return 0.0

    entropy = 0.0
    for value in counts:
        if value > 0:
            p = value / total
            entropy -= p * math.log2(p)

    max_entropy = math.log2(atomic_categories_count) if atomic_categories_count > 1 else 1.0
    if max_entropy <= 0:
        return 0.0
    return float(entropy / max_entropy)


def _compute_city_mode_ranges(
    conn,
    city_code: str,
    network_mode: str,
    atomic_categories_count: int,
) -> Dict[str, Any]:
    rows = _fetch_rows_for_city_mode(conn, city_code=city_code, network_mode=network_mode)
    if not rows:
        return {}

    density_values = [_compute_density_raw(row) for row in rows]
    entropy_values = [_compute_entropy_score(row, atomic_categories_count) for row in rows]

    # Calcola quartili per density e entropy
    density_q1, density_q3 = _compute_quartiles(density_values)
    entropy_q1, entropy_q3 = _compute_quartiles(entropy_values)

    closeness_collection = _resolve_connectivity_collection(network_mode)
    closeness_min, closeness_max = _compute_closeness_min_max(closeness_collection, city_code)

    return {
        "city_code": city_code,
        "network_mode": network_mode,
        "density_raw_min": float(min(density_values)) if density_values else 0.0,
        "density_raw_q1": density_q1,
        "density_raw_q3": density_q3,
        "density_raw_max": float(max(density_values)) if density_values else 0.0,
        "entropy_score_min": float(min(entropy_values)) if entropy_values else 0.0,
        "entropy_score_q1": entropy_q1,
        "entropy_score_q3": entropy_q3,
        "entropy_score_max": float(max(entropy_values)) if entropy_values else 0.0,
        "closeness_raw_min": float(closeness_min),
        "closeness_raw_max": float(closeness_max),
        "proximity_min": PROXIMITY_MIN,
        "proximity_max": PROXIMITY_MAX,
        "source_rows": len(rows),
    }


def _upsert_ranges(conn, ranges: List[Dict[str, Any]]) -> None:
    if not ranges:
        return

    upsert_sql = f"""
        INSERT INTO {TARGET_TABLE} (
            city_code,
            network_mode,
            density_raw_min,
            density_raw_q1,
            density_raw_q3,
            density_raw_max,
            entropy_score_min,
            entropy_score_q1,
            entropy_score_q3,
            entropy_score_max,
            closeness_raw_min,
            closeness_raw_max,
            proximity_min,
            proximity_max,
            source_rows,
            updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (city_code, network_mode)
        DO UPDATE SET
            density_raw_min = EXCLUDED.density_raw_min,
            density_raw_q1 = EXCLUDED.density_raw_q1,
            density_raw_q3 = EXCLUDED.density_raw_q3,
            density_raw_max = EXCLUDED.density_raw_max,
            entropy_score_min = EXCLUDED.entropy_score_min,
            entropy_score_q1 = EXCLUDED.entropy_score_q1,
            entropy_score_q3 = EXCLUDED.entropy_score_q3,
            entropy_score_max = EXCLUDED.entropy_score_max,
            closeness_raw_min = EXCLUDED.closeness_raw_min,
            closeness_raw_max = EXCLUDED.closeness_raw_max,
            proximity_min = EXCLUDED.proximity_min,
            proximity_max = EXCLUDED.proximity_max,
            source_rows = EXCLUDED.source_rows,
            updated_at = NOW()
    """

    rows = [
        (
            item["city_code"],
            item["network_mode"],
            item["density_raw_min"],
            item["density_raw_q1"],
            item["density_raw_q3"],
            item["density_raw_max"],
            item["entropy_score_min"],
            item["entropy_score_q1"],
            item["entropy_score_q3"],
            item["entropy_score_max"],
            item["closeness_raw_min"],
            item["closeness_raw_max"],
            item["proximity_min"],
            item["proximity_max"],
            item["source_rows"],
        )
        for item in ranges
    ]

    with conn.cursor() as cursor:
        execute_batch(cursor, upsert_sql, rows, page_size=500)
    conn.commit()


def main() -> None:
    atomic_categories = _load_atomic_categories()
    atomic_categories_count = len(atomic_categories)

    conn = get_postgres_connection()
    try:
        _ensure_table(conn)
        city_mode_groups = _fetch_city_mode_groups(conn)

        print(f"Found {len(city_mode_groups)} city/mode groups from {SOURCE_TABLE}")
        computed_ranges: List[Dict[str, Any]] = []

        started_at = perf_counter()
        for index, (city_code, network_mode) in enumerate(city_mode_groups, start=1):
            group_started = perf_counter()
            ranges = _compute_city_mode_ranges(
                conn=conn,
                city_code=city_code,
                network_mode=network_mode,
                atomic_categories_count=atomic_categories_count,
            )
            if ranges:
                computed_ranges.append(ranges)

            elapsed = perf_counter() - group_started
            print(
                f"[{index}/{len(city_mode_groups)}] city={city_code} mode={network_mode} "
                f"rows={ranges.get('source_rows', 0) if ranges else 0} elapsed={elapsed:.1f}s",
                flush=True,
            )

        _upsert_ranges(conn, computed_ranges)
        total_elapsed = perf_counter() - started_at
        print(f"Completed. Upserted {len(computed_ranges)} range rows in {total_elapsed:.1f}s")
    finally:
        conn.close()


if __name__ == "__main__":
    main()