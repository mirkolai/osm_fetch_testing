"""
Modello per gestire le sessioni dello user study
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId
import uuid

# Modelli Pydantic per le risposte ai questionari

class DemographicsResponse(BaseModel):
    """Risposte del primo questionario (dati demografici)"""
    age_group: str  # "<18", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"
    gender: str  # "donna", "uomo", "altro", "non-rispondere"
    education_level: str  # "media", "superiore", "triennale", "magistrale", "master_dottorato"
    education_field: str  # "umanistico", "linguistico", "scientifico", etc.
    occupation: str  # "studente", "lavoratore", "disoccupato", etc.
    transport_modes: List[str]  # ["auto", "mezzi_pubblici", "bicicletta", "piedi"]
    housing_type: str  # "appartamento", "casa_indipendente", etc.
    urban_area: str  # "centro", "periferia", "suburbana", "rurale"

class PreexplorationResponse(BaseModel):
    """Risposte del secondo questionario (pre-esplorazione)"""
    accessibility: int  # 0-5
    proximity_avg_minutes: int  # minuti
    proximity_max_minutes: int  # minuti
    density: int  # 0-5
    entropy: int  # 0-5
    closeness: int  # 0-5

class PostexplorationResponse(BaseModel):
    """Risposte del terzo questionario (post-esplorazione)"""
    accessibility: int  # 0-5
    proximity_avg_minutes: int  # minuti
    proximity_max_minutes: int  # minuti
    density: int  # 0-5
    entropy: int  # 0-5
    closeness: int  # 0-5
    platform_understanding_help: int  # 0-5
    opinion_revision: int  # 0-5
    additional_comments: str  # testo libero

class UserStudySessionModel(BaseModel):
    """Modello per una sessione di user study completa"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Step 1: Dati demografici
    demographics: Optional[DemographicsResponse] = None
    demographics_completed_at: Optional[datetime] = None
    
    # Step 2: Pre-esplorazione
    preexploration: Optional[PreexplorationResponse] = None
    preexploration_completed_at: Optional[datetime] = None
    
    # Step 3: Selezione via (search)
    selected_street: Optional[str] = None
    selected_coordinates: Optional[Dict[str, float]] = None  # {"lat": ..., "lon": ...}
    street_selected_at: Optional[datetime] = None
    
    # Step 4: Selezione categorie (personal)
    selected_categories: List[str] = []
    travel_time: Optional[int] = None  # minuti
    travel_mode: Optional[str] = None  # "walking", "walking_cane", etc.
    categories_selected_at: Optional[datetime] = None
    
    # Step 5: Risultati e grafico (calcolati automaticamente)
    results_viewed_at: Optional[datetime] = None
    
    # Step 6: Post-esplorazione
    postexploration: Optional[PostexplorationResponse] = None
    postexploration_completed_at: Optional[datetime] = None
    
    # Step 7: Ringraziamenti
    thanked_at: Optional[datetime] = None
    
    # Metadati
    current_step: int = 1  # Traccia in quale step siamo
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "123abc",
                "created_at": "2024-01-01T12:00:00",
                "current_step": 1
            }
        }

# Modelli per le richieste API

class CreateSessionRequest(BaseModel):
    """Richiesta per creare una nuova sessione"""
    pass  # No parameters needed - generiamo automaticamente il sessionId


class SubmitDemographicsRequest(BaseModel):
    """Richiesta per sottomettere i dati demografici"""
    session_id: str
    demographics: DemographicsResponse


class SubmitPreexplorationRequest(BaseModel):
    """Richiesta per sottomettere pre-esplorazione"""
    session_id: str
    preexploration: PreexplorationResponse


class SelectStreetRequest(BaseModel):
    """Richiesta per salvare la via selezionata"""
    session_id: str
    street_name: str
    latitude: float
    longitude: float


class SelectCategoriesRequest(BaseModel):
    """Richiesta per salvare categorie e impostazioni"""
    session_id: str
    categories: List[str]
    travel_time: int  # minuti
    travel_mode: str  # walking, walking_cane, etc.


class SubmitPostexplorationRequest(BaseModel):
    """Richiesta per sottomettere post-esplorazione"""
    session_id: str
    postexploration: PostexplorationResponse


class GetSessionRequest(BaseModel):
    """Richiesta per recuperare una sessione"""
    session_id: str


class AnalyzeAreaRequest(BaseModel):
    """Richiesta per analizzare un'area con parametri di default"""
    session_id: str
    latitude: float
    longitude: float


class AnalyzePersonalizedRequest(BaseModel):
    """Richiesta per analizzare un'area con parametri personalizzati"""
    session_id: str
    latitude: float
    longitude: float
    travel_time: int  # minuti
    travel_mode: str  # "walking", "walking_cane", etc.
    categories: List[str]  # categorie selezionate
