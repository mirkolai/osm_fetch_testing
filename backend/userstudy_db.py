"""
Funzioni per gestire le sessioni dello user study in MongoDB
"""
from datetime import datetime
from typing import Optional, Dict, Any
from backend.db import db
from backend.UserStudySession import UserStudySessionModel
import uuid

# Collezione MongoDB
sessions_collection = db["userstudy_sessions"]

def create_session() -> UserStudySessionModel:
    """
    Crea una nuova sessione di user study
    
    Returns:
        UserStudySessionModel: La sessione creata
    """
    session = UserStudySessionModel()
    
    # Salva nel database
    session_dict = session.dict()
    session_dict["created_at"] = session.created_at
    session_dict["updated_at"] = session.updated_at
    
    result = sessions_collection.insert_one(session_dict)
    
    return session


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Recupera una sessione dal database
    
    Args:
        session_id: ID della sessione
        
    Returns:
        Dict con i dati della sessione, None se non trovata
    """
    return sessions_collection.find_one({"session_id": session_id})


def update_session(session_id: str, update_data: Dict[str, Any]) -> bool:
    """
    Aggiorna una sessione
    
    Args:
        session_id: ID della sessione
        update_data: Dati da aggiornare
        
    Returns:
        True se l'aggiornamento è stato fatto, False altrimenti
    """
    update_data["updated_at"] = datetime.utcnow()
    
    result = sessions_collection.update_one(
        {"session_id": session_id},
        {"$set": update_data}
    )
    
    return result.modified_count > 0


def save_demographics(session_id: str, demographics: Dict[str, Any]) -> bool:
    """
    Salva i dati demografici per una sessione
    
    Args:
        session_id: ID della sessione
        demographics: Dati demografici
        
    Returns:
        True se salvato correttamente
    """
    return update_session(session_id, {
        "demographics": demographics,
        "demographics_completed_at": datetime.utcnow(),
        "current_step": 2
    })


def save_preexploration(session_id: str, preexploration: Dict[str, Any]) -> bool:
    """
    Salva i dati di pre-esplorazione
    """
    return update_session(session_id, {
        "preexploration": preexploration,
        "preexploration_completed_at": datetime.utcnow(),
        "current_step": 3
    })


def save_selected_street(
    session_id: str, 
    street_name: str, 
    latitude: float, 
    longitude: float
) -> bool:
    """
    Salva la via selezionata
    """
    return update_session(session_id, {
        "selected_street": street_name,
        "selected_coordinates": {"lat": latitude, "lon": longitude},
        "street_selected_at": datetime.utcnow(),
        "current_step": 4
    })


def save_selected_categories(
    session_id: str,
    categories: list,
    travel_time: int,
    travel_mode: str
) -> bool:
    """
    Salva le categorie e le impostazioni di viaggio selezionate
    """
    return update_session(session_id, {
        "selected_categories": categories,
        "travel_time": travel_time,
        "travel_mode": travel_mode,
        "categories_selected_at": datetime.utcnow(),
        "current_step": 5
    })


def save_results_viewed(session_id: str) -> bool:
    """
    Registra che l'utente ha visto i risultati
    """
    return update_session(session_id, {
        "results_viewed_at": datetime.utcnow(),
        "current_step": 6
    })


def save_postexploration(session_id: str, postexploration: Dict[str, Any]) -> bool:
    """
    Salva i dati di post-esplorazione
    """
    return update_session(session_id, {
        "postexploration": postexploration,
        "postexploration_completed_at": datetime.utcnow(),
        "current_step": 7
    })


def mark_session_completed(session_id: str) -> bool:
    """
    Marca la sessione come completata
    """
    return update_session(session_id, {
        "thanked_at": datetime.utcnow(),
        "current_step": 7
    })


def get_all_sessions() -> list:
    """
    Recupera tutte le sessioni (per analisi)
    """
    return list(sessions_collection.find({}, {"_id": 0}))


def get_session_count() -> int:
    """
    Conta il numero di sessioni completate
    """
    return sessions_collection.count_documents({"thanked_at": {"$exists": True, "$ne": None}})
