"""
Endpoint FastAPI per lo user study
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import json
import os
from backend.UserStudySession import (
    CreateSessionRequest,
    SubmitDemographicsRequest,
    SubmitPreexplorationRequest,
    SelectStreetRequest,
    SelectCategoriesRequest,
    SubmitPostexplorationRequest,
    GetSessionRequest,
    AnalyzeAreaRequest,
    AnalyzePersonalizedRequest,
    UserStudySessionModel
)
from backend.userstudy_db import (
    create_session as db_create_session,
    get_session as db_get_session,
    save_demographics,
    save_preexploration,
    save_selected_street,
    save_selected_categories,
    save_results_viewed,
    save_postexploration,
    mark_session_completed,
    get_all_sessions,
    get_session_count
)
# Importa le funzioni per le API
from backend.Isochrones import get_isocronewalk_by_node_id
from backend.Poi import get_detailed_pois_by_node_id
from backend.Parameters import compute_isochrone_parameters
from backend.Nodes import get_id_node_by_coordinates
from backend.RequestModels import Coordinates

router = APIRouter(prefix="/api/userstudy", tags=["userstudy"])


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
    try:
        # Verifica che la sessione esista
        session = db_get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Parametri di default
        minutes = 15
        velocity = 5  # walking speed (km/h)
        
        # Leggi tutte le categorie da categories.json
        with open('backend/categories.json', 'r', encoding='utf-8') as f:
            categories_dict = json.load(f)
        
        # Estrai tutti i nomi delle categorie (le chiavi principali)
        all_categories = list(categories_dict.keys())
        
        coordinates = Coordinates(lat=request.latitude, lon=request.longitude)
        
        # Step 1: Trova il node_id più vicino
        status_code, message, node_id = get_id_node_by_coordinates(coordinates)
        if status_code != 200:
            raise HTTPException(status_code=404, detail=f"Node not found: {message}")
        
        # Step 2: Recupera l'isochrone
        iso_status, iso_msg, isochrone_data = get_isocronewalk_by_node_id(
            node_id=node_id,
            minute=minutes,
            velocity=velocity
        )
        if iso_status != 200:
            raise HTTPException(status_code=404, detail=f"Isochrone not found: {iso_msg}")
        
        # Step 3: Recupera i POI
        poi_status, poi_msg, pois_data, total_pois = get_detailed_pois_by_node_id(
            node_id=node_id,
            min=minutes,
            vel=velocity,
            categories=all_categories
        )
        if poi_status != 200:
            # Se non ci sono POI, continua comunque
            pois_data = []
            total_pois = 0
        
        # Step 4: Calcola i parametri per il radar chart
        parameters = compute_isochrone_parameters(
            pois_data=pois_data,
            isochrone_data=isochrone_data,
            vel=velocity,
            total_pois=total_pois,
            max_minutes=60,
            categories=all_categories
        )
        
        return {
            "status": "success",
            "node_id": node_id,
            "isochrone": isochrone_data,
            "pois": pois_data,
            "total_pois": total_pois,
            "parameters": {
                "proximity_score": parameters.get("proximity_score", 0.2),
                "density_score": parameters.get("density_score", 0.2),
                "entropy_score": parameters.get("entropy_score", 0.2),
                "poi_accessibility": parameters.get("poi_accessibility", 0.2),
                "closeness": parameters.get("closeness", 0.2)
            }
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
        velocity = 5 if request.travel_mode == "walking" else 4  # 4 km/h con bastone, 5 km/h a piedi
        categories = request.categories
        
        coordinates = Coordinates(lat=request.latitude, lon=request.longitude)
        
        # Step 1: Trova il node_id più vicino
        status_code, message, node_id = get_id_node_by_coordinates(coordinates)
        if status_code != 200:
            raise HTTPException(status_code=404, detail=f"Node not found: {message}")
        
        # Step 2: Recupera l'isochrone
        iso_status, iso_msg, isochrone_data = get_isocronewalk_by_node_id(
            node_id=node_id,
            minute=minutes,
            velocity=velocity
        )
        if iso_status != 200:
            raise HTTPException(status_code=404, detail=f"Isochrone not found: {iso_msg}")
        
        # Step 3: Recupera i POI (con le categorie selezionate)
        poi_status, poi_msg, pois_data, total_pois = get_detailed_pois_by_node_id(
            node_id=node_id,
            min=minutes,
            vel=velocity,
            categories=categories
        )
        if poi_status != 200:
            # Se non ci sono POI, continua comunque
            pois_data = []
            total_pois = 0
        
        # Step 4: Calcola i parametri per il radar chart
        parameters = compute_isochrone_parameters(
            pois_data=pois_data,
            isochrone_data=isochrone_data,
            vel=velocity,
            total_pois=total_pois,
            max_minutes=60,
            categories=categories
        )
        
        return {
            "status": "success",
            "node_id": node_id,
            "isochrone": isochrone_data,
            "pois": pois_data,
            "total_pois": total_pois,
            "parameters": {
                "proximity_score": parameters.get("proximity_score", 0.2),
                "density_score": parameters.get("density_score", 0.2),
                "entropy_score": parameters.get("entropy_score", 0.2),
                "poi_accessibility": parameters.get("poi_accessibility", 0.2),
                "closeness": parameters.get("closeness", 0.2)
            }
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
