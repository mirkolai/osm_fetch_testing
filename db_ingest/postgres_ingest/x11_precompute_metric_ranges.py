"""
Precalcola i range delle metriche per le citta gia processate da x10.

Per ogni gruppo (city_code, network_mode, travel_time) salva:
- min, Q1, mediana (Q2), Q3, avg, e max per densita, entropia, closeness e proximity
- source_rows: numero di righe sorgente usate per i range

IMPORTANTE:
- I dati gia presenti in precomputed_metric_ranges NON vengono ricalcolati.
- Vengono calcolate solamente le coppie (city_code, network_mode, travel_time)
  che non sono ancora presenti nel database.
- Nessuna tabella viene cancellata.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple

from psycopg2.extras import execute_batch

from backend.Connectivity import (
    _resolve_connectivity_collection,
)
from backend.mongo_db import db as mongo_db
from backend.postgres_db import get_postgres_connection


SOURCE_TABLE = "precomputed_metrics_rows"
TARGET_TABLE = "precomputed_metric_ranges"

# ============================================================
# Utility
# ============================================================

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
    categories_path = (
        Path(__file__).resolve().parents[2]
        / "backend"
        / "categories.json"
    )

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


# ============================================================
# Database setup
# ============================================================

def _ensure_table(conn) -> None:
    """
    Crea la tabella se non esiste.

    NON cancella mai dati esistenti.
    """

    create_sql = f"""
        CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (
            city_code TEXT NOT NULL,
            network_mode TEXT NOT NULL,
            travel_time INTEGER NOT NULL,

            density_raw_min DOUBLE PRECISION NOT NULL DEFAULT 0,
            density_raw_q1 DOUBLE PRECISION NOT NULL DEFAULT 0,
            density_raw_q2 DOUBLE PRECISION,
            density_raw_q3 DOUBLE PRECISION NOT NULL DEFAULT 0,
            density_raw_max DOUBLE PRECISION NOT NULL DEFAULT 0,

            entropy_score_min DOUBLE PRECISION NOT NULL DEFAULT 0,
            entropy_score_q1 DOUBLE PRECISION NOT NULL DEFAULT 0,
            entropy_score_q2 DOUBLE PRECISION,
            entropy_score_q3 DOUBLE PRECISION NOT NULL DEFAULT 0,
            entropy_score_max DOUBLE PRECISION NOT NULL DEFAULT 0,

            closeness_raw_min DOUBLE PRECISION NOT NULL DEFAULT 0,
            closeness_raw_q1 DOUBLE PRECISION,
            closeness_raw_q2 DOUBLE PRECISION,
            closeness_raw_q3 DOUBLE PRECISION,
            closeness_raw_max DOUBLE PRECISION NOT NULL DEFAULT 0,

            proximity_min DOUBLE PRECISION NOT NULL DEFAULT 0,
            proximity_q1 DOUBLE PRECISION,
            proximity_q2 DOUBLE PRECISION,
            proximity_q3 DOUBLE PRECISION,
            proximity_max DOUBLE PRECISION NOT NULL DEFAULT 60,

            density_avg DOUBLE PRECISION,
            entropy_avg DOUBLE PRECISION,
            proximity_avg DOUBLE PRECISION,
            closeness_avg DOUBLE PRECISION,

            source_rows INTEGER NOT NULL DEFAULT 0,

            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

            PRIMARY KEY (city_code, network_mode, travel_time)
        );

        CREATE INDEX IF NOT EXISTS idx_metric_ranges_city_mode
        ON {TARGET_TABLE}(city_code, network_mode);
    """

    with conn.cursor() as cursor:
        cursor.execute(create_sql)

    conn.commit()


# ============================================================
# Lettura gruppi da processare
# ============================================================

def _fetch_city_mode_groups(conn) -> List[Tuple[str, str]]:
    """
    Recupera tutti i gruppi città/modalità/tempo presenti nella tabella sorgente.

    Esempio:

        001001 / walk / 5
        001001 / walk / 10
        001001 / bike / 5
        ...

    Le coppie gia presenti in TARGET_TABLE vengono escluse
    direttamente dalla query.
    """

    import sys

    sys.path.insert(
        0,
        str(Path(__file__).resolve().parents[2])
    )

    from db_ingest import utils as _utils

    query = f"""
        SELECT DISTINCT
            source.city_code,
            source.network_mode,
            source.travel_time
        FROM {SOURCE_TABLE} source
        LEFT JOIN {TARGET_TABLE} target
            ON target.city_code = source.city_code
            AND target.network_mode = source.network_mode
            AND target.travel_time = source.travel_time
        WHERE source.city_code IS NOT NULL
          AND (
                target.city_code IS NULL
                OR target.density_raw_q2 IS NULL
                OR target.entropy_score_q2 IS NULL
                OR target.closeness_raw_q1 IS NULL
                OR target.closeness_raw_q2 IS NULL
                OR target.closeness_raw_q3 IS NULL
                OR target.proximity_q1 IS NULL
                OR target.proximity_q2 IS NULL
                OR target.proximity_q3 IS NULL
                OR target.density_avg IS NULL
                OR target.entropy_avg IS NULL
                OR target.proximity_avg IS NULL
                OR target.closeness_avg IS NULL
          )
        ORDER BY source.city_code, source.network_mode
    """

    groups: List[Tuple[str, str, int]] = []

    with conn.cursor() as cursor:
        cursor.execute(query)

        for city_code, network_mode, travel_time in cursor.fetchall():
            normalized_city_code = _normalize_city_code(city_code)
            normalized_network_mode = str(network_mode or "").strip().lower()

            if not normalized_city_code or not normalized_network_mode:
                continue

            if not _utils.should_process_city(normalized_city_code):
                continue

            groups.append((normalized_city_code, normalized_network_mode, int(travel_time)))

    return groups


# ============================================================
# Lettura dati sorgente
# ============================================================

def _fetch_rows_for_city_mode(
    conn,
    city_code: str,
    network_mode: str,
    travel_time: int,
) -> List[Dict[str, Any]]:

    query = f"""
        SELECT
            travel_time,
            category_primary_counts,
            isochrone_area_km2,
            total_pois,
            proximity_value
        FROM {SOURCE_TABLE}
        WHERE city_code = %s
          AND network_mode = %s
                    AND travel_time = %s
    """

    rows: List[Dict[str, Any]] = []

    with conn.cursor() as cursor:
        cursor.execute(query, (city_code, network_mode, travel_time))

        for row in cursor.fetchall():
            rows.append(
                {
                    "travel_time": int(row[0]),
                    "category_primary_counts": list(row[1] or []),
                    "isochrone_area_km2": float(row[2] or 0.0),
                    "total_pois": int(row[3] or 0),
                    "proximity_value": float(row[4]) if row[4] is not None else None,
                }
            )

    return rows


# ============================================================
# Metriche
# ============================================================

def _compute_density_raw(
    row: Dict[str, Any],
) -> float:

    area_km2 = float(
        row.get("isochrone_area_km2") or 0.0
    )

    total_pois = int(
        row.get("total_pois") or 0
    )

    if area_km2 <= 0 or total_pois <= 0:
        return 0.0

    return float(total_pois) / float(area_km2)


def _compute_quartiles(
    values: List[float],
) -> Tuple[float, float, float]:
    """Calcola Q1, mediana (Q2) e Q3 usando interpolazione lineare."""
    if not values:
        return 0.0, 0.0, 0.0

    sorted_values = sorted(values)
    last_index = len(sorted_values) - 1

    def percentile(fraction: float) -> float:
        index = last_index * fraction
        lower = int(index)
        upper = min(lower + 1, last_index)
        weight = index - lower
        return float(sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight)

    return percentile(0.25), percentile(0.5), percentile(0.75)


def _fetch_closeness_values(collection_name: str, city_code: str) -> List[float]:
    connectivity_collection = mongo_db[collection_name]
    normalized_city_code = _normalize_city_code(city_code)
    city_code_query: Any = normalized_city_code
    if normalized_city_code and normalized_city_code.isdigit():
        city_code_query = {"$in": [normalized_city_code, int(normalized_city_code)]}

    city_doc = mongo_db["city_polygon"].find_one(
        {"PRO_COM_T": city_code_query},
        {"_id": 0, "geometry": 1},
    ) if city_code_query else None

    city_pipeline: List[Dict[str, Any]] = [
        {"$match": {"connectivity.closeness": {"$type": "number"}}},
        {
            "$lookup": {
                "from": "nodes",
                "localField": "node_id",
                "foreignField": "node_id",
                "as": "node_doc",
            }
        },
        {"$unwind": "$node_doc"},
        {
            "$match": {
                "node_doc.location": {
                    "$geoWithin": {"$geometry": (city_doc or {}).get("geometry", {})}
                }
            }
        },
        {"$project": {"_id": 0, "value": "$connectivity.closeness"}},
    ]

    values: List[float] = []
    if city_doc and city_doc.get("geometry"):
        values = [
            float(document["value"])
            for document in connectivity_collection.aggregate(city_pipeline)
        ]

    if not values:
        global_pipeline = [
            {"$match": {"connectivity.closeness": {"$type": "number"}}},
            {"$project": {"_id": 0, "value": "$connectivity.closeness"}},
        ]
        values = [
            float(document["value"])
            for document in connectivity_collection.aggregate(global_pipeline)
        ]

    return values


def _compute_entropy_score(
    row: Dict[str, Any],
    atomic_categories_count: int,
) -> float:
    if atomic_categories_count <= 0:
        return 0.0

    primary_counts = row.get("category_primary_counts") or []
    total_pois = int(row.get("total_pois") or 0)
    if total_pois <= 0:
        return 0.0

    counts = [
        primary_counts[index] if index < len(primary_counts) else 0
        for index in range(atomic_categories_count)
    ]
    total = float(sum(counts))
    if total <= 0:
        return 0.0

    entropy = 0.0
    for value in counts:
        if value > 0:
            probability = value / total
            entropy -= probability * math.log2(probability)

    max_entropy = math.log2(atomic_categories_count) if atomic_categories_count > 1 else 1.0
    if max_entropy <= 0:
        return 0.0
    return float(entropy / max_entropy)


def _normalize_metric_value(
    value: float,
    minimum: float,
    maximum: float,
    fallback: float,
) -> float:
    if maximum <= minimum:
        return fallback
    if value <= minimum:
        return 0.0
    if value >= maximum:
        return 1.0
    return (value - minimum) / (maximum - minimum)


# ============================================================
# Calcolo range per una città/modalità
# ============================================================

def _compute_city_mode_ranges(
    conn,
    city_code: str,
    network_mode: str,
    travel_time: int,
    atomic_categories_count: int,
) -> Dict[str, Any]:

    print(
        f"  Loading source rows "
        f"city={city_code} "
        f"mode={network_mode}",
        flush=True,
    )

    rows = _fetch_rows_for_city_mode(
        conn,
        city_code=city_code,
        network_mode=network_mode,
        travel_time=travel_time,
    )

    if not rows:
        return {}

    print(
        f"  Computing density/entropy "
        f"for {len(rows)} rows",
        flush=True,
    )

    # --------------------------------------------------------
    # Density
    # --------------------------------------------------------

    density_values = [
        _compute_density_raw(row)
        for row in rows
    ]

    # --------------------------------------------------------
    # Entropy
    # --------------------------------------------------------

    entropy_values = [
        _compute_entropy_score(
            row,
            atomic_categories_count,
        )
        for row in rows
    ]
    proximity_values = [
        float(row["proximity_value"])
        for row in rows
        if row["proximity_value"] is not None
    ]

    density_min = float(min(density_values)) if density_values else 0.0
    density_max = float(max(density_values)) if density_values else 0.0
    entropy_min = float(min(entropy_values)) if entropy_values else 0.0
    entropy_max = float(max(entropy_values)) if entropy_values else 0.0

    # --------------------------------------------------------
    # Quartili
    # --------------------------------------------------------

    density_q1, density_q2, density_q3 = _compute_quartiles(density_values)
    entropy_q1, entropy_q2, entropy_q3 = _compute_quartiles(entropy_values)
    proximity_q1, proximity_q2, proximity_q3 = _compute_quartiles(proximity_values)
    proximity_min = min(proximity_values) if proximity_values else 0.0
    proximity_max = max(proximity_values) if proximity_values else 0.0

    # --------------------------------------------------------
    # Closeness
    # --------------------------------------------------------

    print(
        f"  Loading closeness "
        f"city={city_code} "
        f"mode={network_mode}",
        flush=True,
    )

    closeness_collection = (
        _resolve_connectivity_collection(
            network_mode
        )
    )

    closeness_values = _fetch_closeness_values(closeness_collection, city_code)
    closeness_q1, closeness_q2, closeness_q3 = _compute_quartiles(closeness_values)
    closeness_min = min(closeness_values) if closeness_values else 0.0
    closeness_max = max(closeness_values) if closeness_values else 1.0
    density_avg = sum(density_values) / len(density_values) if density_values else 0.0
    entropy_avg = sum(entropy_values) / len(entropy_values) if entropy_values else 0.0
    proximity_avg = sum(proximity_values) / len(proximity_values) if proximity_values else 0.0
    closeness_avg = sum(closeness_values) / len(closeness_values) if closeness_values else 0.0

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    return {
        "city_code": city_code,
        "network_mode": network_mode,
        "travel_time": travel_time,

        "density_raw_min": (
            density_min
        ),

        "density_raw_q1": density_q1,

        "density_raw_q2": density_q2,

        "density_raw_q3": density_q3,

        "density_raw_max": (
            density_max
        ),

        "entropy_score_min": (
            entropy_min
        ),

        "entropy_score_q1": entropy_q1,

        "entropy_score_q2": entropy_q2,

        "entropy_score_q3": entropy_q3,

        "entropy_score_max": (
            entropy_max
        ),

        "closeness_raw_min": float(
            closeness_min
        ),

        "closeness_raw_q1": closeness_q1,

        "closeness_raw_q2": closeness_q2,

        "closeness_raw_q3": closeness_q3,

        "closeness_raw_max": float(
            closeness_max
        ),

        "proximity_min": proximity_min,

        "proximity_q1": proximity_q1,

        "proximity_q2": proximity_q2,

        "proximity_q3": proximity_q3,

        "proximity_max": proximity_max,

        "density_avg": density_avg,
        "entropy_avg": entropy_avg,
        "proximity_avg": proximity_avg,
        "closeness_avg": closeness_avg,

        "source_rows": len(rows),
    }


# ============================================================
# Salvataggio
# ============================================================

def _upsert_ranges(
    conn,
    ranges: List[Dict[str, Any]],
) -> None:

    if not ranges:
        return

    upsert_sql = f"""
        INSERT INTO {TARGET_TABLE} (
            city_code,
            network_mode,
            travel_time,

            density_raw_min,
            density_raw_q1,
            density_raw_q2,
            density_raw_q3,
            density_raw_max,

            entropy_score_min,
            entropy_score_q1,
            entropy_score_q2,
            entropy_score_q3,
            entropy_score_max,

            closeness_raw_min,
            closeness_raw_q1,
            closeness_raw_q2,
            closeness_raw_q3,
            closeness_raw_max,

            proximity_min,
            proximity_q1,
            proximity_q2,
            proximity_q3,
            proximity_max,

            density_avg,
            entropy_avg,
            proximity_avg,
            closeness_avg,

            source_rows,
            updated_at
        )
        VALUES (
            %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s,
            NOW()
        )

        ON CONFLICT (city_code, network_mode, travel_time)
        DO UPDATE SET

            density_raw_min =
                EXCLUDED.density_raw_min,

            density_raw_q1 =
                EXCLUDED.density_raw_q1,

            density_raw_q2 =
                EXCLUDED.density_raw_q2,

            density_raw_q3 =
                EXCLUDED.density_raw_q3,

            density_raw_max =
                EXCLUDED.density_raw_max,

            entropy_score_min =
                EXCLUDED.entropy_score_min,

            entropy_score_q1 =
                EXCLUDED.entropy_score_q1,

            entropy_score_q2 =
                EXCLUDED.entropy_score_q2,

            entropy_score_q3 =
                EXCLUDED.entropy_score_q3,

            entropy_score_max =
                EXCLUDED.entropy_score_max,

            closeness_raw_min =
                EXCLUDED.closeness_raw_min,

            closeness_raw_q1 =
                EXCLUDED.closeness_raw_q1,

            closeness_raw_q2 =
                EXCLUDED.closeness_raw_q2,

            closeness_raw_q3 =
                EXCLUDED.closeness_raw_q3,

            closeness_raw_max =
                EXCLUDED.closeness_raw_max,

            proximity_min =
                EXCLUDED.proximity_min,

            proximity_q1 =
                EXCLUDED.proximity_q1,

            proximity_q2 =
                EXCLUDED.proximity_q2,

            proximity_q3 =
                EXCLUDED.proximity_q3,

            proximity_max =
                EXCLUDED.proximity_max,

            density_avg =
                EXCLUDED.density_avg,

            entropy_avg =
                EXCLUDED.entropy_avg,

            proximity_avg =
                EXCLUDED.proximity_avg,

            closeness_avg =
                EXCLUDED.closeness_avg,

            source_rows =
                EXCLUDED.source_rows,

            updated_at =
                NOW()
    """

    rows = [
        (
            item["city_code"],
            item["network_mode"],
            item["travel_time"],

            item["density_raw_min"],
            item["density_raw_q1"],
            item["density_raw_q2"],
            item["density_raw_q3"],
            item["density_raw_max"],

            item["entropy_score_min"],
            item["entropy_score_q1"],
            item["entropy_score_q2"],
            item["entropy_score_q3"],
            item["entropy_score_max"],

            item["closeness_raw_min"],
            item["closeness_raw_q1"],
            item["closeness_raw_q2"],
            item["closeness_raw_q3"],
            item["closeness_raw_max"],

            item["proximity_min"],
            item["proximity_q1"],
            item["proximity_q2"],
            item["proximity_q3"],
            item["proximity_max"],

            item["density_avg"],
            item["entropy_avg"],
            item["proximity_avg"],
            item["closeness_avg"],

            item["source_rows"],
        )
        for item in ranges
    ]

    with conn.cursor() as cursor:

        execute_batch(
            cursor,
            upsert_sql,
            rows,
            page_size=500,
        )

    conn.commit()


# ============================================================
# Main
# ============================================================

def main() -> None:

    atomic_categories = (
        _load_atomic_categories()
    )

    atomic_categories_count = len(
        atomic_categories
    )

    conn = get_postgres_connection()

    try:

        # ----------------------------------------------------
        # Crea la tabella se necessario.
        # NON cancella dati.
        # ----------------------------------------------------

        _ensure_table(conn)

        # ----------------------------------------------------
        # Recupera solo i gruppi città/modalità/tempo incompleti o assenti.
        # ----------------------------------------------------

        city_mode_groups = (
            _fetch_city_mode_groups(conn)
        )

        print(
            f"Found {len(city_mode_groups)} "
            f"city/mode/travel_time groups to process "
            f"from {SOURCE_TABLE}",
            flush=True,
        )

        if not city_mode_groups:

            print(
                "Nothing to calculate: "
                "all available city/mode ranges "
                "are already present in "
                f"{TARGET_TABLE}.",
                flush=True,
            )

            return

        computed_ranges: List[
            Dict[str, Any]
        ] = []

        started_at = perf_counter()

        # ----------------------------------------------------
        # Calcola solamente i gruppi nuovi.
        # ----------------------------------------------------

        for index, (
            city_code,
            network_mode,
            travel_time,
        ) in enumerate(
            city_mode_groups,
            start=1,
        ):

            group_started = (
                perf_counter()
            )

            print(
                "",
                flush=True,
            )

            print(
                f"[{index}/{len(city_mode_groups)}] "
                f"START city={city_code} "
                f"mode={network_mode}",
                flush=True,
            )

            ranges = (
                _compute_city_mode_ranges(
                    conn=conn,
                    city_code=city_code,
                    network_mode=network_mode,
                    travel_time=travel_time,
                    atomic_categories_count=(
                        atomic_categories_count
                    ),
                )
            )

            if ranges:

                computed_ranges.append(
                    ranges
                )

            elapsed = (
                perf_counter()
                - group_started
            )

            print(
                f"[{index}/{len(city_mode_groups)}] "
                f"DONE city={city_code} "
                f"mode={network_mode} "
                f"rows="
                f"{ranges.get('source_rows', 0) if ranges else 0} "
                f"elapsed={elapsed:.1f}s",
                flush=True,
            )

            # ------------------------------------------------
            # Salva subito il gruppo.
            #
            # Questo e' utile perche', se lo script viene
            # interrotto dopo 20 citta, al riavvio quelle 20
            # non verranno ricalcolate.
            # ------------------------------------------------

            if ranges:

                _upsert_ranges(
                    conn,
                    [ranges],
                )

                print(
                    f"  Saved city={city_code} "
                    f"mode={network_mode}",
                    flush=True,
                )

        total_elapsed = (
            perf_counter()
            - started_at
        )

        print(
            "",
            flush=True,
        )

        print(
            f"Completed. "
            f"New range rows calculated: "
            f"{len(computed_ranges)} "
            f"in {total_elapsed:.1f}s",
            flush=True,
        )

    finally:

        conn.close()


if __name__ == "__main__":
    main()

