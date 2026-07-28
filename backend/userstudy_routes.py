"""
Endpoint FastAPI per lo user study
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
import json
import os
import math
from backend.UserStudySession import (
    SubmitDemographicsRequest,
    SubmitPreexplorationRequest,
    SelectStreetRequest,
    SelectCategoriesRequest,
    SubmitPostexplorationRequest,
    GetSessionRequest,
    AnalyzeAreaRequest,
    AnalyzePersonalizedRequest,
    CityAverageMetricsRequest,
)
from backend.userstudy_db import (
    create_session as db_create_session,
    get_session as db_get_session,
    save_demographics,
    save_preexploration,
    save_selected_street,
    save_selected_categories,
    save_analysis_metrics,
    save_results_viewed,
    save_postexploration,
    mark_session_completed,
    get_all_sessions,
    get_session_count
)
# Importa le funzioni per le API
from backend.Isochrones import get_isocronewalk_by_node_id
from backend.Poi import get_detailed_pois_by_node_id, expand_requested_categories
from backend.Connectivity import get_closeness_by_node_id, get_city_average_normalized_closeness
from backend.Parameters import compute_isochrone_parameters
from backend.Nodes import get_id_node_by_coordinates
from backend.RequestModels import Coordinates
from backend.postgres_db import get_postgres_connection
from backend.mongo_db import db as mongo_db

router = APIRouter(prefix="/api/userstudy", tags=["userstudy"])

_ATOMIC_CATEGORIES_CACHE: List[str] = []
_PRECOMPUTED_TRAVEL_BUCKETS: List[int] = [5, 10, 15, 20]
_CITY_BOUNDARIES_CACHE: Optional[Dict[str, Any]] = None


def _normalize_metric_value(value: Optional[float], q1: Optional[float], q3: Optional[float], fallback: float = 0.0) -> float:
    """
    Normalizza un valore usando quartili robusti (Q1/Q3 al posto di min/max).
    - Valori < Q1 → 0.0
    - Valori > Q3 → 1.0
    - Valori tra Q1 e Q3 → interpolazione lineare tra 0 e 1
    """
    if value is None:
        return float(fallback)
    if q1 is None or q3 is None:
        return float(value)

    q1_float = float(q1)
    q3_float = float(q3)
    
    # Se Q1 e Q3 sono uguali, fallback
    if q3_float <= q1_float:
        return float(fallback)
    
    value_float = float(value)
    
    # Valori sotto Q1 → 0.0
    if value_float <= q1_float:
        return 0.0
    
    # Valori sopra Q3 → 1.0
    if value_float >= q3_float:
        return 1.0
    
    # Interpolazione lineare tra Q1 e Q3
    normalized = (value_float - q1_float) / (q3_float - q1_float)
    return float(max(0.0, min(1.0, normalized)))


def _resolve_precomputed_mode(travel_mode: str) -> str:
    mode = (travel_mode or "walking").strip().lower()
    if mode in {"bike", "bicycle", "cycling"}:
        return "bike"
    if mode in {"walking_cane", "cane", "slow_walk"}:
        return "slow_walk"
    return "walk"


def _normalize_city_code(city_code: Any) -> Optional[str]:
    if city_code is None:
        return None

    value = str(city_code).strip()
    if not value:
        return None

    if value.isdigit():
        return value.zfill(6)
    return value


def _build_city_code_query(city_code: Optional[str]) -> Optional[Dict[str, Any]]:
    normalized = _normalize_city_code(city_code)
    if not normalized:
        return None
    candidates: List[Any] = [normalized]
    if normalized.isdigit():
        candidates.append(int(normalized))
        candidates.append(str(int(normalized)))
    return {"$in": candidates}


def _load_city_boundaries_feature_collection() -> Dict[str, Any]:
    global _CITY_BOUNDARIES_CACHE
    if _CITY_BOUNDARIES_CACHE is not None:
        return _CITY_BOUNDARIES_CACHE

    query = "SELECT DISTINCT city_code FROM precomputed_metrics_rows WHERE city_code IS NOT NULL"

    conn = get_postgres_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query)
            city_codes = [_normalize_city_code(row[0]) for row in cursor.fetchall() if row and row[0] is not None]
    finally:
        conn.close()

    normalized_codes = sorted({code for code in city_codes if code})
    features: List[Dict[str, Any]] = []

    city_collection = mongo_db["city_polygon"]
    for code in normalized_codes:
        code_query = _build_city_code_query(code)
        if code_query is None:
            continue

        doc = city_collection.find_one({"PRO_COM_T": code_query}, {"_id": 0, "PRO_COM_T": 1, "COMUNE": 1, "geometry": 1})
        if not doc:
            continue

        geometry = doc.get("geometry")
        if not geometry:
            continue

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "city_code": _normalize_city_code(doc.get("PRO_COM_T")),
                    "city_name": doc.get("COMUNE") or "",
                },
                "geometry": geometry,
            }
        )

    feature_collection = {
        "type": "FeatureCollection",
        "features": features,
    }
    _CITY_BOUNDARIES_CACHE = feature_collection
    return feature_collection


def _load_atomic_categories() -> List[str]:
    global _ATOMIC_CATEGORIES_CACHE
    if _ATOMIC_CATEGORIES_CACHE:
        return _ATOMIC_CATEGORIES_CACHE

    categories_path = os.path.join(os.path.dirname(__file__), "categories.json")
    with open(categories_path, "r", encoding="utf-8") as file_obj:
        categories_by_group = json.load(file_obj)

    ordered: List[str] = []
    seen = set()
    for _, values in categories_by_group.items():
        for category in values:
            if category not in seen:
                seen.add(category)
                ordered.append(category)

    _ATOMIC_CATEGORIES_CACHE = ordered
    return ordered


def _fetch_precomputed_row(node_id: int, travel_time: int, network_mode: str) -> Dict[str, Any]:
    query = """
        SELECT
            category_primary_counts,
            category_secondary_counts,
            isochrone_area_km2,
            total_pois,
            proximity_value
        FROM precomputed_metrics_rows
        WHERE network_mode = %s
          AND node_id = %s
          AND travel_time = %s
        LIMIT 1
    """

    conn = get_postgres_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (network_mode, node_id, travel_time))
            row = cursor.fetchone()
            if not row:
                return {}
            return {
                "category_primary_counts": list(row[0] or []),
                "category_secondary_counts": list(row[1] or []),
                "isochrone_area_km2": float(row[2] or 0.0),
                "total_pois": int(row[3] or 0),
                "proximity_value": float(row[4]) if row[4] is not None else None,
            }
    finally:
        conn.close()


def _fetch_city_metric_ranges(city_code: str, network_mode: str) -> Dict[str, float]:
    normalized_city_code = _normalize_city_code(city_code)
    if not normalized_city_code:
        return {}

    query = """
        SELECT
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
            proximity_max
        FROM precomputed_metric_ranges
        WHERE city_code = %s
          AND network_mode = %s
        LIMIT 1
    """

    conn = get_postgres_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (normalized_city_code, network_mode))
            row = cursor.fetchone()
            if not row:
                return {}

            return {
                "density_raw_min": float(row[0]) if row[0] is not None else 0.0,
                "density_raw_q1": float(row[1]) if row[1] is not None else 0.0,
                "density_raw_q3": float(row[2]) if row[2] is not None else 0.0,
                "density_raw_max": float(row[3]) if row[3] is not None else 0.0,
                "entropy_score_min": float(row[4]) if row[4] is not None else 0.0,
                "entropy_score_q1": float(row[5]) if row[5] is not None else 0.0,
                "entropy_score_q3": float(row[6]) if row[6] is not None else 0.0,
                "entropy_score_max": float(row[7]) if row[7] is not None else 0.0,
                "closeness_raw_min": float(row[8]) if row[8] is not None else 0.0,
                "closeness_raw_max": float(row[9]) if row[9] is not None else 0.0,
                "proximity_min": float(row[10]) if row[10] is not None else 0.0,
                "proximity_max": float(row[11]) if row[11] is not None else 60.0,
            }
    finally:
        conn.close()


def _apply_city_metric_ranges(parameters: Dict[str, Any], city_ranges: Dict[str, float]) -> Dict[str, Any]:
    if not city_ranges:
        return parameters

    adjusted = dict(parameters)
    
    print(f"[DEBUG] _apply_city_metric_ranges - Input:")
    print(f"  parameters: {parameters}")
    print(f"  city_ranges: {city_ranges}")
    
    old_density = adjusted.get("density_score")
    adjusted["density_score"] = _normalize_metric_value(
        adjusted.get("density_raw"),
        city_ranges.get("density_raw_q1"),
        city_ranges.get("density_raw_q3"),
        fallback=float(adjusted.get("density_score", 0.0) or 0.0),
    )
    print(f"  density_raw: {adjusted.get('density_raw')} -> density_score: {old_density} -> {adjusted['density_score']}")
    print(f"    (city ranges Q1-Q3: {city_ranges.get('density_raw_q1')} to {city_ranges.get('density_raw_q3')})")
    
    old_entropy = adjusted.get("entropy_score")
    adjusted["entropy_score"] = _normalize_metric_value(
        adjusted.get("entropy_raw"),
        city_ranges.get("entropy_score_q1"),
        city_ranges.get("entropy_score_q3"),
        fallback=float(adjusted.get("entropy_score", 0.0) or 0.0),
    )
    print(f"  entropy_raw: {adjusted.get('entropy_raw')} -> entropy_score: {old_entropy} -> {adjusted['entropy_score']}")
    print(f"    (city ranges Q1-Q3: {city_ranges.get('entropy_score_q1')} to {city_ranges.get('entropy_score_q3')})")

    proximity_min = adjusted.get("proximity")
    try:
        proximity_min_value = float(proximity_min)
    except Exception:
        proximity_min_value = None

    if proximity_min_value is not None:
        adjusted["proximity_score"] = _normalize_metric_value(
            proximity_min_value,
            city_ranges.get("proximity_min", 0.0),
            city_ranges.get("proximity_max", 60.0),
            fallback=float(adjusted.get("proximity_score", 0.0) or 0.0),
        )

    adjusted["poi_accessibility"] = (
        float(adjusted.get("proximity_score", 0.0))
        + float(adjusted.get("density_score", 0.0))
        + float(adjusted.get("entropy_score", 0.0))
    ) / 3.0
    print(f"  Output: density={adjusted['density_score']:.4f}, entropy={adjusted['entropy_score']:.4f}, proximity={adjusted['proximity_score']:.4f}, poi_accessibility={adjusted['poi_accessibility']:.4f}")
    print()
    return adjusted


def _fetch_precomputed_rows_for_node(node_id: int, network_mode: str) -> Dict[int, Dict[str, Any]]:
    query = """
        SELECT
            travel_time,
            category_primary_counts,
            category_secondary_counts,
            isochrone_area_km2,
            total_pois,
            proximity_value
        FROM precomputed_metrics_rows
        WHERE network_mode = %s
          AND node_id = %s
          AND travel_time = ANY(%s)
    """

    conn = get_postgres_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (network_mode, node_id, _PRECOMPUTED_TRAVEL_BUCKETS))
            rows = cursor.fetchall()
            result: Dict[int, Dict[str, Any]] = {}
            for row in rows:
                minute = int(row[0])
                result[minute] = {
                    "category_primary_counts": list(row[1] or []),
                    "category_secondary_counts": list(row[2] or []),
                    "isochrone_area_km2": float(row[3] or 0.0),
                    "total_pois": int(row[4] or 0),
                    "proximity_value": float(row[5]) if row[5] is not None else None,
                }
            return result
    finally:
        conn.close()


def _compute_category_based_proximity_minutes(
    rows_by_minute: Dict[int, Dict[str, Any]],
    selected_categories: List[str],
) -> Optional[float]:
    if not rows_by_minute:
        return None

    atomic_categories = _load_atomic_categories()
    category_to_idx = {category: idx for idx, category in enumerate(atomic_categories)}
    expanded_categories = expand_requested_categories(selected_categories)
    selected_idxs = [category_to_idx[c] for c in expanded_categories if c in category_to_idx]

    if not selected_idxs:
        return None

    for minute in sorted(_PRECOMPUTED_TRAVEL_BUCKETS):
        row = rows_by_minute.get(minute)
        if not row:
            continue

        primary_counts = row.get("category_primary_counts") or []
        secondary_counts = row.get("category_secondary_counts") or []

        all_categories_present = True
        for idx in selected_idxs:
            primary = primary_counts[idx] if idx < len(primary_counts) else 0
            secondary = secondary_counts[idx] if idx < len(secondary_counts) else 0
            if (primary + secondary) < 1:
                all_categories_present = False
                break

        if all_categories_present:
            return float(minute)

    return None


def _resolve_city_code_for_node(node_id: int, travel_time: int, network_mode: str) -> Optional[str]:
    query = """
        SELECT city_code
        FROM precomputed_metrics_rows
        WHERE network_mode = %s
          AND node_id = %s
          AND travel_time = %s
        LIMIT 1
    """

    conn = get_postgres_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (network_mode, node_id, travel_time))
            row = cursor.fetchone()
            if not row:
                return _resolve_city_code_for_node_from_mongo(node_id)
            return _normalize_city_code(row[0])
    finally:
        conn.close()


def _resolve_city_code_for_node_from_mongo(node_id: int) -> Optional[str]:
    """Fallback city lookup from Mongo nodes + city_polygon when precomputed row is missing."""
    try:
        node_doc = mongo_db["nodes"].find_one({"node_id": node_id}, {"_id": 0, "location": 1})
        if not node_doc or "location" not in node_doc:
            return None

        city_doc = mongo_db["city_polygon"].find_one(
            {
                "geometry": {
                    "$geoIntersects": {
                        "$geometry": node_doc["location"]
                    }
                }
            },
            {"_id": 0, "PRO_COM_T": 1},
        )
        if not city_doc:
            return None

        city_code = city_doc.get("PRO_COM_T")
        return _normalize_city_code(city_code)
    except Exception:
        return None


def _fetch_precomputed_rows_for_city(city_code: str, travel_time: int, network_mode: str) -> List[Dict[str, Any]]:
    normalized_city_code = _normalize_city_code(city_code)
    if not normalized_city_code:
        return []

    query = """
        SELECT
            city_code,network_mode,
            density_raw_min,density_raw_q1,density_raw_q3,density_raw_max,entropy_score_min,entropy_score_q1,entropy_score_q3,entropy_score_max,closeness_raw_min,closeness_raw_max,proximity_min,proximity_max,source_rows,updated_at
        FROM precomputed_metrics_rows
        WHERE city_code = %s
          AND network_mode = %s
          AND travel_time = %s
    """
    conn = get_postgres_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (normalized_city_code, network_mode, travel_time))
            rows = cursor.fetchall()
            result: List[Dict[str, Any]] = []
            for row in rows:
                result.append(
                    {
                        "category_primary_counts": list(row[0] or []),
                        "category_secondary_counts": list(row[1] or []),
                        "isochrone_area_km2": float(row[2] or 0.0),
                        "total_pois": int(row[3] or 0),
                        "proximity_value": float(row[4]) if row[4] is not None else None,
                    }
                )
            return result
    finally:
        conn.close()


def _compute_city_average_parameters(
    city_code: str,
    travel_time: int,
    travel_mode: str,
    categories: List[str],
) -> Dict[str, float]:
    network_mode = _resolve_precomputed_mode(travel_mode)
    city_ranges = _fetch_city_metric_ranges(city_code=city_code, network_mode=network_mode)
    rows = _fetch_precomputed_rows_for_city(
        city_code=city_code,
        travel_time=travel_time,
        network_mode=network_mode,
    )
    if not rows:
        return {}

    # Category filtering is always enabled for city averages.
    selected_categories = categories
    closeness_status, _, closeness_avg = get_city_average_normalized_closeness(city_code=city_code, travel_mode=travel_mode)
    if closeness_status != 200 or closeness_avg is None:
        closeness_avg = 0.0

    sums = {
        "proximity_score": 0.0,
        "density_score": 0.0,
        "entropy_score": 0.0,
        "poi_accessibility": 0.0,
    }

    for row in rows:
        params = _build_parameters_from_precomputed(
            precomputed_row=row,
            selected_categories=selected_categories,
            closeness_value=float(closeness_avg),
            max_minutes=60,
            city_ranges=city_ranges,
        )
        sums["proximity_score"] += params.get("proximity_score", 0.0)
        sums["density_score"] += params.get("density_score", 0.0)
        sums["entropy_score"] += params.get("entropy_score", 0.0)
        sums["poi_accessibility"] += params.get("poi_accessibility", 0.0)

    total = float(len(rows))
    if total <= 0:
        return {}

    return {
        "proximity_score": sums["proximity_score"] / total,
        "density_score": sums["density_score"] / total,
        "entropy_score": sums["entropy_score"] / total,
        "poi_accessibility": sums["poi_accessibility"] / total,
        "closeness": float(closeness_avg),
    }


def _build_parameters_from_precomputed(
    precomputed_row: Dict[str, Any],
    selected_categories: List[str],
    closeness_value: float,
    max_minutes: int = 60,
    proximity_min_override: Optional[float] = None,
    force_proximity_override: bool = False,
    city_ranges: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    print(f"[DEBUG] _build_parameters_from_precomputed:"
          f" precomputed_row={precomputed_row}, selected_categories={selected_categories}"
          f" closeness_value={closeness_value}, max_minutes={max_minutes},"
            f" proximity_min_override={proximity_min_override}, force_proximity_override={force_proximity_override},"
            f" city_ranges={city_ranges}"
            )
    atomic_categories = _load_atomic_categories()
    category_to_idx = {category: idx for idx, category in enumerate(atomic_categories)}

    expanded_categories = expand_requested_categories(selected_categories)
    selected_idxs = [category_to_idx[c] for c in expanded_categories if c in category_to_idx]

    primary_counts = precomputed_row.get("category_primary_counts") or []
    secondary_counts = precomputed_row.get("category_secondary_counts") or []
    total_pois = int(precomputed_row.get("total_pois") or 0)
    area_km2 = float(precomputed_row.get("isochrone_area_km2") or 0.0)
    entropy_raw = 0.0
    if force_proximity_override:
        proximity_min = proximity_min_override
    else:
        proximity_min = proximity_min_override if proximity_min_override is not None else precomputed_row.get("proximity_value")

    if selected_idxs:
        matched_primary = sum(primary_counts[idx] for idx in selected_idxs if idx < len(primary_counts))
        matched_secondary = sum(secondary_counts[idx] for idx in selected_idxs if idx < len(secondary_counts))
        total_pois_effective = min(total_pois, matched_primary + matched_secondary)
    else:
        total_pois_effective = total_pois

    if proximity_min is None:
        # Per scheda 5 personalizzata: nessun bucket valido equivale al caso peggiore (60 min).
        proximity_score = 1.0
    else:
        proximity_score = min(float(proximity_min) / float(max_minutes), 1.0)

    if total_pois_effective == 0 or area_km2 <= 0:
        density_score = 0.0
    else:
        density_raw = total_pois_effective / area_km2
        density_score = 1.0 if density_raw > 100 else (density_raw / 100.0)

    if total_pois_effective == 0 or not selected_idxs:
        entropy_score = 0.0
    else:
        counts = [primary_counts[idx] if idx < len(primary_counts) else 0 for idx in selected_idxs]
        total_selected = float(sum(counts))
        if total_selected <= 0:
            entropy_score = 0.0
        else:
            entropy = 0.0
            for value in counts:
                if value > 0:
                    p = value / total_selected
                    entropy -= p * math.log2(p)
            max_entropy = math.log2(len(selected_idxs)) if len(selected_idxs) > 1 else 1.0
            entropy_raw = entropy / max_entropy if max_entropy > 0 else 0.0
            entropy_score = entropy_raw

    density_raw = (total_pois_effective / area_km2) if total_pois_effective > 0 and area_km2 > 0 else 0.0

    print(f"[DEBUG] _build_parameters_from_precomputed:")
    print(f"  area_km2: {area_km2}, total_pois_effective: {total_pois_effective}")
    print(f"  density_raw: {density_raw} (POI/km²)")
    print(f"  city_ranges available: {bool(city_ranges)}")
    if city_ranges:
        print(f"  density_raw_min: {city_ranges.get('density_raw_min')}, density_raw_max: {city_ranges.get('density_raw_max')}")

    if city_ranges:
        density_score = _normalize_metric_value(
            density_raw,
            city_ranges.get("density_raw_min"),
            city_ranges.get("density_raw_max"),
            fallback=density_score,
        )
        print(f"  density_score after normalization: {density_score}")
        entropy_score = _normalize_metric_value(
            entropy_raw,
            city_ranges.get("entropy_score_min"),
            city_ranges.get("entropy_score_max"),
            fallback=entropy_score,
        )
        print(f"  entropy_score after normalization: {entropy_score}")
    else:
        # Mantiene il comportamento precedente se i range per citta non sono disponibili.
        if total_pois_effective != 0 and area_km2 > 0:
            density_score = 1.0 if density_raw > 100 else (density_raw / 100.0)
        entropy_score = entropy_raw
        print(f"  Using fallback (no city_ranges): density_score={density_score}, entropy_score={entropy_score}")

    poi_accessibility = (proximity_score + density_score + entropy_score) / 3.0

    return {
        "density_raw": float(density_raw),
        "entropy_raw": float(entropy_raw),
        "proximity_score": float(proximity_score),
        "density_score": float(density_score),
        "entropy_score": float(entropy_score),
        "poi_accessibility": float(poi_accessibility),
        "closeness": float(closeness_value or 0.0),
    }


def resolve_velocity_kmh(travel_mode: str) -> int:
    mode = (travel_mode or "walking").strip().lower()
    if mode in {"bike", "bicycle", "cycling"}:
        return 15
    if mode in {"walking_cane", "cane"}:
        return 4
    return 5


@router.get("/categories")
async def get_categories() -> Dict[str, Any]:
    """
    Restituisce le categorie disponibili da categories.json
    """
    try:
        categories_path = os.path.join(os.path.dirname(__file__), 'categories.json')
        with open(categories_path, 'r', encoding='utf-8') as f:
            categories_dict = json.load(f)
        
        return {
            "status": "success",
            "categories": categories_dict
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load categories: {str(e)}")


@router.post("/session/create")
async def create_new_session() -> Dict[str, Any]:
    """
    Crea una nuova sessione di user study
    
    Returns:
        Dict con session_id e timestamp di creazione
    """
    try:
        session = db_create_session()
        return {
            "status": "success",
            "session_id": session.session_id,
            "created_at": session.created_at.isoformat(),
            "message": "Session created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/get")
async def get_session(request: GetSessionRequest) -> Dict[str, Any]:
    """
    Recupera i dati di una sessione
    """
    try:
        session_data = db_get_session(request.session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Rimuovi l'ID interno di MongoDB
        session_data.pop("_id", None)
        
        return {
            "status": "success",
            "session": session_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/demographics/submit")
async def submit_demographics(request: SubmitDemographicsRequest) -> Dict[str, Any]:
    """
    Sottometti i dati demografici
    """
    try:
        # Verifica che la sessione esista
        session = db_get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Salva i dati demografici
        success = save_demographics(
            request.session_id,
            request.demographics.dict()
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save demographics")
        
        return {
            "status": "success",
            "message": "Demographics saved successfully",
            "current_step": 2
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preexploration/submit")
async def submit_preexploration(request: SubmitPreexplorationRequest) -> Dict[str, Any]:
    """
    Sottometti i dati di pre-esplorazione
    """
    try:
        session = db_get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        success = save_preexploration(
            request.session_id,
            request.preexploration.dict()
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save preexploration")
        
        return {
            "status": "success",
            "message": "Pre-exploration data saved successfully",
            "current_step": 3
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-area")
async def analyze_area(request: AnalyzeAreaRequest) -> Dict[str, Any]:
    """
    Analizza un'area con parametri di default (15 minuti, walking, tutte le categorie)
    Restituisce dati per isochrone, POI, e parametri del radar chart
    """
    import time
    start_total = time.time()
    
    try:
        # Verifica che la sessione esista
        session = db_get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Parametri di default
        minutes = 15
        velocity = 5  # walking speed (km/h)
        
        # Leggi tutte le categorie da categories.json
        start = time.time()
        with open('backend/categories.json', 'r', encoding='utf-8') as f:
            categories_dict = json.load(f)
        all_categories = list(categories_dict.keys())
        expanded_categories = expand_requested_categories(all_categories)
        print(f"[TIMING] Load categories: {time.time() - start:.3f}s")
        
        coordinates = Coordinates(lat=request.latitude, lon=request.longitude)
        
        # Step 1: Trova il node_id più vicino
        start = time.time()
        status_code, message, node_id = get_id_node_by_coordinates(coordinates, travel_mode="walking")
        print(f"[TIMING] get_id_node_by_coordinates: {time.time() - start:.3f}s (node_id={node_id})")
        if status_code != 200:
            raise HTTPException(status_code=404, detail=f"Node not found: {message}")
        
        # Step 2: Recupera l'isochrone
        start = time.time()
        iso_status, iso_msg, isochrone_data = get_isocronewalk_by_node_id(
            node_id=node_id,
            minute=minutes,
            velocity=velocity,
            travel_mode="walking"
        )
        print(f"[TIMING] get_isocronewalk_by_node_id: {time.time() - start:.3f}s")
        if iso_status != 200:
            raise HTTPException(status_code=404, detail=f"Isochrone not found: {iso_msg}")
        
        # Step 3: Recupera i POI
        start = time.time()
        poi_status, poi_msg, pois_data, total_pois = get_detailed_pois_by_node_id(
            node_id=node_id,
            min=minutes,
            vel=velocity,
            categories=all_categories,
            travel_mode="walk"
        )
        print(f"[TIMING] get_detailed_pois_by_node_id: {time.time() - start:.3f}s (total_pois={total_pois})")
        if poi_status != 200:
            # Se non ci sono POI, continua comunque
            pois_data = []
            total_pois = 0
        
        # Step 4: Calcola i parametri per il radar chart
        start = time.time()
        closeness_status, _, closeness_value = get_closeness_by_node_id(
            node_id=node_id,
            travel_mode="walk",
        )
        print(f"[TIMING] get_closeness_by_node_id: {time.time() - start:.3f}s")
        if closeness_status != 200:
            closeness_value = 0.0

        start = time.time()
        city_code = _resolve_city_code_for_node(
            node_id=node_id,
            travel_time=minutes,
            network_mode="walk",
        )
        print(f"[TIMING] resolve city_code: {time.time() - start:.3f}s (city_code={city_code})")

        start = time.time()
        city_ranges = _fetch_city_metric_ranges(city_code=city_code, network_mode="walk") if city_code else {}
        print(f"[TIMING] fetch city_ranges: {time.time() - start:.3f}s (city_code={city_code})")

        start = time.time()
        precomputed_row = _fetch_precomputed_row(
            node_id=node_id,
            travel_time=minutes,
            network_mode="walk",
        )
        print(f"[TIMING] _fetch_precomputed_row: {time.time() - start:.3f}s")
        
        start = time.time()
        parameters = _build_parameters_from_precomputed(
            precomputed_row=precomputed_row,
            selected_categories=all_categories,
            closeness_value=float(closeness_value or 0.0),
            max_minutes=60,
            city_ranges=city_ranges,
        )
        
        print(f"[TIMING] build/compute parameters: {time.time() - start:.3f}s")

        start = time.time()
        parameters = _apply_city_metric_ranges(parameters, city_ranges)
        print(f"[TIMING] _apply_city_metric_ranges: {time.time() - start:.3f}s")
        
        start = time.time()
        start = time.time()
        city_average_parameters = (
            _compute_city_average_parameters(
                city_code=city_code,
                travel_time=minutes,
                travel_mode="walk",
                categories=all_categories,
            )
            if city_code
            else {}
        )
        print(f"[TIMING] _compute_city_average_parameters: {time.time() - start:.3f}s")

        # Salva in sessione le metriche baseline per export finale e analisi successive.
        metrics_payload = {
            "proximity_score": parameters.get("proximity_score", 0.2),
            "density_score": parameters.get("density_score", 0.2),
            "entropy_score": parameters.get("entropy_score", 0.2),
            "poi_accessibility": parameters.get("poi_accessibility", 0.2),
            "closeness": parameters.get("closeness", 0.2)
        }
        start = time.time()
        save_ok = save_analysis_metrics(request.session_id, "default", metrics_payload)
        print(f"[TIMING] save_analysis_metrics: {time.time() - start:.3f}s")
        if not save_ok:
            raise HTTPException(status_code=500, detail="Failed to save default analysis metrics")
        
        print(f"[TIMING] TOTAL analyze_area: {time.time() - start_total:.3f}s\n")
        
        return {
            "status": "success",
            "node_id": node_id,
            "isochrone": isochrone_data,
            "pois": pois_data,
            "total_pois": total_pois,
            "parameters": metrics_payload,
            "city_average_parameters": city_average_parameters,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-personalized")
async def analyze_personalized(request: AnalyzePersonalizedRequest) -> Dict[str, Any]:
    """
    Analizza un'area con parametri personalizzati (tempo, modalità, categorie)
    Restituisce dati per isochrone, POI, e parametri del radar chart
    """
    try:
        # Verifica che la sessione esista
        session = db_get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Parametri personalizzati
        minutes = request.travel_time
        velocity = resolve_velocity_kmh(request.travel_mode)
        categories = request.categories
        expanded_categories = expand_requested_categories(categories)
        
        coordinates = Coordinates(lat=request.latitude, lon=request.longitude)
        
        # Step 1: Trova il node_id più vicino
        status_code, message, node_id = get_id_node_by_coordinates(coordinates, travel_mode=request.travel_mode)
        if status_code != 200:
            raise HTTPException(status_code=404, detail=f"Node not found: {message}")
        
        # Step 2: Recupera l'isochrone
        iso_status, iso_msg, isochrone_data = get_isocronewalk_by_node_id(
            node_id=node_id,
            minute=minutes,
            velocity=velocity,
            travel_mode=request.travel_mode
        )
        if iso_status != 200:
            raise HTTPException(status_code=404, detail=f"Isochrone not found: {iso_msg}")
        
        # Step 3: Recupera i POI (con le categorie selezionate)
        poi_status, poi_msg, pois_data, total_pois = get_detailed_pois_by_node_id(
            node_id=node_id,
            min=minutes,
            vel=velocity,
            categories=categories,
            travel_mode=request.travel_mode
        )
        if poi_status != 200:
            # Se non ci sono POI, continua comunque
            pois_data = []
            total_pois = 0
        
        # Step 4: Calcola i parametri per il radar chart
        closeness_status, _, closeness_value = get_closeness_by_node_id(
            node_id=node_id,
            travel_mode=request.travel_mode,
        )
        if closeness_status != 200:
            closeness_value = 0.0

        network_mode = _resolve_precomputed_mode(request.travel_mode)
        city_code = _resolve_city_code_for_node(
            node_id=node_id,
            travel_time=minutes,
            network_mode=network_mode,
        )
        city_ranges = _fetch_city_metric_ranges(city_code=city_code, network_mode=network_mode) if city_code else {}

        
        precomputed_row = _fetch_precomputed_row(
            node_id=node_id,
            travel_time=minutes,
            network_mode=network_mode,
        )
        if precomputed_row:
            node_bucket_rows = _fetch_precomputed_rows_for_node(
                node_id=node_id,
                network_mode=network_mode,
            )
            category_based_proximity_min = _compute_category_based_proximity_minutes(
                rows_by_minute=node_bucket_rows,
                selected_categories=categories,
            )
            parameters = _build_parameters_from_precomputed(
                precomputed_row=precomputed_row,
                selected_categories=categories,
                closeness_value=float(closeness_value or 0.0),
                max_minutes=60,
                proximity_min_override=category_based_proximity_min,
                force_proximity_override=True,
                city_ranges=city_ranges,
            )
        else:
            parameters = compute_isochrone_parameters(
                pois_data=pois_data,
                isochrone_data=isochrone_data,
                vel=velocity,
                total_pois=total_pois,
                max_minutes=60,
                categories=expanded_categories,
                closeness_value=closeness_value,
            )

        parameters = _apply_city_metric_ranges(parameters, city_ranges)
        city_average_parameters = (
            _compute_city_average_parameters(
                city_code=city_code,
                travel_time=minutes,
                travel_mode=request.travel_mode,
                categories=categories,
            )
            if city_code
            else {}
        )

        # Salva in sessione le metriche personalizzate per export finale e confronto.
        metrics_payload = {
            "proximity_score": parameters.get("proximity_score", 0.2),
            "density_score": parameters.get("density_score", 0.2),
            "entropy_score": parameters.get("entropy_score", 0.2),
            "poi_accessibility": parameters.get("poi_accessibility", 0.2),
            "closeness": parameters.get("closeness", 0.2)
        }
        save_ok = save_analysis_metrics(request.session_id, "personalized", metrics_payload)
        if not save_ok:
            raise HTTPException(status_code=500, detail="Failed to save personalized analysis metrics")
        
        return {
            "status": "success",
            "node_id": node_id,
            "isochrone": isochrone_data,
            "pois": pois_data,
            "total_pois": total_pois,
            "parameters": metrics_payload,
            "city_average_parameters": city_average_parameters,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/city-average-metrics")
async def city_average_metrics(request: CityAverageMetricsRequest) -> Dict[str, Any]:
    """Restituisce la media città delle metriche per mode/tempo e filtro categorie opzionale."""
    try:
        session = db_get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        coordinates = Coordinates(lat=request.latitude, lon=request.longitude)
        status_code, message, node_id = get_id_node_by_coordinates(
            coordinates,
            travel_mode=request.travel_mode,
        )
        if status_code != 200:
            raise HTTPException(status_code=404, detail=f"Node not found: {message}")

        network_mode = _resolve_precomputed_mode(request.travel_mode)
        city_code = _resolve_city_code_for_node(
            node_id=node_id,
            travel_time=request.travel_time,
            network_mode=network_mode,
        )
        if not city_code:
            raise HTTPException(status_code=404, detail="City code not found for selected node")

        city_average_parameters = _compute_city_average_parameters(
            city_code=city_code,
            travel_time=request.travel_time,
            travel_mode=request.travel_mode,
            categories=request.categories,
        )
        if not city_average_parameters:
            raise HTTPException(status_code=404, detail="City average metrics not found")

        return {
            "status": "success",
            "city_code": city_code,
            "parameters": city_average_parameters,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/street/select")
async def select_street(request: SelectStreetRequest) -> Dict[str, Any]:
    """
    Salva la via selezionata
    """
    try:
        session = db_get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        success = save_selected_street(
            request.session_id,
            request.street_name,
            request.latitude,
            request.longitude
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save street selection")
        
        return {
            "status": "success",
            "message": "Street selected successfully",
            "selected_street": request.street_name,
            "current_step": 4
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/categories/select")
async def select_categories(request: SelectCategoriesRequest) -> Dict[str, Any]:
    """
    Salva le categorie selezionate
    """
    try:
        session = db_get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        success = save_selected_categories(
            request.session_id,
            request.categories,
            request.travel_time,
            request.travel_mode
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save categories")
        
        return {
            "status": "success",
            "message": "Categories saved successfully",
            "categories_count": len(request.categories),
            "current_step": 5
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/results/viewed")
async def mark_results_viewed(request: GetSessionRequest) -> Dict[str, Any]:
    """
    Registra che l'utente ha visto i risultati
    """
    try:
        session = db_get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        success = save_results_viewed(request.session_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update results view")
        
        return {
            "status": "success",
            "current_step": 6
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/postexploration/submit")
async def submit_postexploration(request: SubmitPostexplorationRequest) -> Dict[str, Any]:
    """
    Sottometti i dati di post-esplorazione
    """
    try:
        session = db_get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        success = save_postexploration(
            request.session_id,
            request.postexploration.dict()
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save postexploration")
        
        return {
            "status": "success",
            "message": "Post-exploration data saved successfully",
            "current_step": 7
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/complete")
async def complete_session(request: GetSessionRequest) -> Dict[str, Any]:
    """
    Marca una sessione come completata
    """
    try:
        session = db_get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        success = mark_session_completed(request.session_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to complete session")
        
        return {
            "status": "success",
            "message": "Session completed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/city-boundaries")
async def get_city_boundaries() -> Dict[str, Any]:
    """Restituisce i confini GeoJSON delle citta presenti nei precompute."""
    try:
        return {
            "status": "success",
            "data": _load_city_boundaries_feature_collection(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/all")
async def get_all_sessions_data() -> Dict[str, Any]:
    """
    Recupera tutte le sessioni (ADMIN ONLY - in produzione aggiungere autenticazione)
    """
    try:
        sessions = get_all_sessions()
        count = get_session_count()
        
        return {
            "status": "success",
            "total_sessions": len(sessions),
            "completed_sessions": count,
            "sessions": sessions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
