"""
Endpoint FastAPI per lo user study
"""
from unicodedata import normalize
from urllib import request
from pathlib import Path
import numpy as np
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional, Tuple
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
    AnalyzePersonalizedRequest,
)
from backend.category_mapping import get_new_groups, get_new_secondary_categories
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
from backend.Poi import get_detailed_pois_by_node_id
from backend.Connectivity import get_nodes_in_city
from backend.Parameters import compute_isochrone_parameters
from backend.Nodes import get_id_node_by_coordinates
from backend.RequestModels import Coordinates, NetworkMode, UserStudyTravelMode
from backend.postgres_db import get_postgres_connection
from backend.mongo_db import db as mongo_db

router = APIRouter(prefix="/api/userstudy", tags=["userstudy"])


_CITY_BOUNDARIES_CACHE: Optional[Dict[str, Any]] = None


def _network_mode_for_travel_mode(travel_mode: UserStudyTravelMode) -> NetworkMode:
    return "walk" if travel_mode == "slow_walk" else travel_mode




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




def _get_city_sample_size() -> int:
    try:
        return max(1, int(os.getenv("USERSTUDY_CITY_SAMPLE_SIZE", "100")))
    except (TypeError, ValueError):
        return 100



def _resolve_city_code_for_node(node_id: int, travel_time: int, network_mode: NetworkMode) -> Optional[str]:
    """Trova il codice PRO_COM_T del comune in city_polygon che contiene il nodo."""
    conn = get_postgres_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT ST_X(geom), ST_Y(geom)
                FROM nodes
                WHERE id = %s AND network_mode = %s
                LIMIT 1
                """,
                (node_id, network_mode),
            )
            row = cursor.fetchone()
    finally:
        conn.close()

    if not row or row[0] is None or row[1] is None:
        return None

    try:
        city_doc = mongo_db["city_polygon"].find_one(
            {
                "geometry": {
                    "$geoIntersects": {
                        "$geometry": {"type": "Point", "coordinates": [float(row[0]), float(row[1])]}
                    }
                }
            },
            {"_id": 0, "PRO_COM_T": 1},
        )
    except Exception:
        return None

    if not city_doc:
        return None
    return _normalize_city_code(city_doc.get("PRO_COM_T"))





def _compute_city_sample_personalized_parameters(
            city_code,
            network_mode,
            velocity,
            travel_time,
            max_minutes,
            selected_categories) -> list[Dict[str, Any]]:


    sample_rows = get_nodes_in_city(
        _get_city_sample_size(),
        city_code,
        network_mode,
    )

    proximities=[]
    entropies=[]
    densities=[]
    closenesses=[]
    i=0
    for row in sample_rows:
        node_id = row["node_id"]
        #print("row", i )
        i+=1

        try:
        
            parameters = compute_isochrone_parameters(
                        node_id,
                        city_code,
                        velocity,
                        travel_time,
                        network_mode,
                        max_minutes,
                        selected_categories,)
            proximities.append(parameters["proximity"])
            entropies.append(parameters["entropy"])
            densities.append(parameters["density"])
            closenesses.append(parameters["closeness"])



            averages = {
                "proximity": sum(proximities) / len(proximities) if proximities else 0,
                "entropy": sum(entropies) / len(entropies) if entropies else 0,
                "density": sum(densities) / len(densities) if densities else 0,
                "closeness": sum(closenesses) / len(closenesses) if closenesses else 0,
            }


            minimum_values = {
                "proximity": np.percentile(proximities, 10) if proximities else 0,
                "entropy": np.percentile(entropies, 10) if entropies else 0,
                "density": np.percentile(densities, 10) if densities else 0,
                "closeness": np.percentile(closenesses, 10) if closenesses else 0,
            }

            maximum_values = {
                "proximity": np.percentile(proximities, 90) if proximities else 0,
                "entropy": np.percentile(entropies, 90) if entropies else 0,
                "density": np.percentile(densities, 90) if densities else 0,
                "closeness": np.percentile(closenesses, 90) if closenesses else 0,
            }
        except Exception as e:
            print(f"Error computing parameters for node_id {node_id}: {e}")
            

    return averages,minimum_values,maximum_values





def resolve_velocity_kmh(travel_mode: UserStudyTravelMode) -> int:
    if travel_mode == "bike":
        return 15
    if travel_mode == "slow_walk":
        return 2
    if travel_mode == "walk":
        return 5
    raise ValueError("unsupported travel mode: use walk, slow_walk or bike")


@router.get("/categories")
async def get_categories() -> Dict[str, Any]:
    """
    Restituisce le categorie personalizzate (NewPrimaryName -> NewSecondaryName) da personalised_categories.tsv
    """
    try:
        categories_dict = get_new_groups()
        
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


@router.post("/analyze-personalized")
async def analyze_personalized(request: AnalyzePersonalizedRequest) -> Dict[str, Any]:
    """
    Analizza un'area con parametri personalizzati o standard (15 minuti e tutte le categorie).
    Restituisce dati per isochrone, POI, e parametri del radar chart.
    """
    try:
        # Verifica che la sessione esista
        session = db_get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Risolve i parametri richiesti o i valori standard.
        #print("request",request)
        #request di esempio
        # request session_id='b04a5b90-a82e-4441-b677-aa03b6ccf62a'
        #  latitude=45.076953 
        # longitude=7.6761215 
        # travel_time=15 
        # travel_mode='walk' 
        # categories=[] 
        # analysis_type='default'       
        minutes = request.travel_time
        #5, 10, 12, 20
        velocity = resolve_velocity_kmh(request.travel_mode)
        # 2 o 5 se walk, 15 se bike
        network_mode = _network_mode_for_travel_mode(request.travel_mode)
        #walk o bike (se walk, velocity=5 km/h; se bike, velocity=15 km/h, se slow_walk, velocity=2 km/h)
        valid_new_categories = set(get_new_secondary_categories())
        selected_categories = [c for c in (request.categories or []) if c in valid_new_categories] \
            or get_new_secondary_categories()
        coordinates = Coordinates(lat=request.latitude, lon=request.longitude)
        
        # Step 1: Trova il node_id più vicino
        # usa ST_SetSRID sulla collezione mongo node
        status_code, message, node_id = get_id_node_by_coordinates(coordinates, travel_mode=network_mode)
        if status_code != 200:
            raise HTTPException(status_code=404, detail=f"Node not found: {message}")
        #print("node_id", node_id)
        #es node_id 438238719 4, Corso Alessandro Tassoni, Campidoglio, Circoscrizione 4, Torino, Piemonte, 10143, Italia
        
        # Step 2: Recupera l'isochrone
        # usa postgres con pgr_drivingDistance per torvare i nodi raggiungibili
        # MultiPoint(reachable_coords).convex_hull per generare l'isochrona
        iso_status, iso_msg, isochrone_data = get_isocronewalk_by_node_id(
            node_id=node_id,
            minute=minutes,
            velocity=velocity,
            travel_mode=network_mode
        )
        if iso_status != 200:
            raise HTTPException(status_code=404, detail=f"Isochrone not found: {iso_msg}")
        
        # Step 3: Recupera i POI (con le categorie selezionate)
        # indivia i nodi raggiungibili con pgr_drivingDistance
        # facendo la JOIN con node_poi individua i POI raggiungibili
        poi_status, poi_msg, pois_data, total_pois = get_detailed_pois_by_node_id(
            node_id=node_id,
            min=minutes,
            vel=velocity,
            categories=selected_categories,
            travel_mode=network_mode
        )
        #print("poi_status", poi_status,len(pois_data), "total_pois", total_pois)
        if poi_status != 200:
            # Se non ci sono POI, continua comunque
            pois_data = []
            total_pois = 0
        # Step 4: Calcola i parametri per il radar chart


        # Step 4.2 recupera il codice istat della città
        # trovando una riga precompute per il nodo e il tempo selezionato
        # nella tabella precomputed_metrics_rows in postgress
        city_code = _resolve_city_code_for_node(
            node_id=node_id,
            travel_time=minutes,
            network_mode=network_mode,
        )
        #print("city_code", city_code)
        if not city_code:
            raise HTTPException(status_code=404, detail="City code not found for selected node")
        
        parameters = compute_isochrone_parameters(
                node_id=node_id,
                city_code=city_code,
                network_mode=network_mode,
                velocity=velocity,
                travel_time=minutes,
                max_minutes=60,
                selected_categories=selected_categories,
        )
        #print("parameters",parameters)

        avg_sample, mininum_sample, maximum_sample = _compute_city_sample_personalized_parameters(
            city_code=city_code,
            network_mode=network_mode,
            velocity=velocity,
            travel_time=minutes,
            max_minutes=60,
            selected_categories=selected_categories)
        # Salva in sessione le metriche personalizzate per export finale e confronto.
        #print("parameters",parameters)
        #print("minimum sample",mininum_sample)
        #print("maximum sample",maximum_sample)
        metrics_payload = {
                "proximity_score": np.clip(
                    (parameters.get("proximity") - mininum_sample["proximity"]) /
                    (maximum_sample["proximity"] - mininum_sample["proximity"]),
                    0, 1
                ) if (maximum_sample["proximity"] - mininum_sample["proximity"]) > 0 else 0,

                "density_score": np.clip(
                    (parameters.get("density") - mininum_sample["density"]) /
                    (maximum_sample["density"] - mininum_sample["density"]),
                    0, 1
                ) if (maximum_sample["density"] - mininum_sample["density"]) > 0 else 0,

                "entropy_score": np.clip(
                    (parameters.get("entropy") - mininum_sample["entropy"]) /
                    (maximum_sample["entropy"] - mininum_sample["entropy"]),
                    0, 1
                ) if (maximum_sample["entropy"] - mininum_sample["entropy"]) > 0 else 0,

                "closeness": np.clip(
                    (parameters.get("closeness") - mininum_sample["closeness"]) /
                    (maximum_sample["closeness"] - mininum_sample["closeness"]),
                    0, 1
                ) if (maximum_sample["closeness"] - mininum_sample["closeness"]) > 0 else 0
            }

        metrics_payload["poi_accessibility"] = ((1-metrics_payload["proximity_score"]) + metrics_payload["density_score"] + metrics_payload["entropy_score"]) / 3.0

        save_ok = save_analysis_metrics(request.session_id, request.analysis_type, metrics_payload)
        if not save_ok:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save {request.analysis_type} analysis metrics",
            )
        
        city_average_parameters = {
            "proximity_score": np.clip(
                (avg_sample.get("proximity") - mininum_sample["proximity"]) /
                (maximum_sample["proximity"] - mininum_sample["proximity"]),
                0, 1
            ) if (maximum_sample["proximity"] - mininum_sample["proximity"]) > 0 else 0,

            "density_score": np.clip(
                (avg_sample.get("density") - mininum_sample["density"]) /
                (maximum_sample["density"] - mininum_sample["density"]),
                0, 1
            ) if (maximum_sample["density"] - mininum_sample["density"]) > 0 else 0,

            "entropy_score": np.clip(
                (avg_sample.get("entropy") - mininum_sample["entropy"]) /
                (maximum_sample["entropy"] - mininum_sample["entropy"]),
                0, 1
            ) if (maximum_sample["entropy"] - mininum_sample["entropy"]) > 0 else 0,

            "closeness": np.clip(
                (avg_sample.get("closeness") - mininum_sample["closeness"]) /
                (maximum_sample["closeness"] - mininum_sample["closeness"]),
                0, 1
            ) if (maximum_sample["closeness"] - mininum_sample["closeness"]) > 0 else 0
        }


        city_average_parameters["poi_accessibility"] =  ((1-city_average_parameters["proximity_score"]) + city_average_parameters["density_score"] + city_average_parameters["entropy_score"]) / 3.0

        #print("metrics_payload",metrics_payload)
        #print("city_average_parameters",city_average_parameters)

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
