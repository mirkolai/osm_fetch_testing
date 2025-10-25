# questo file contiene quali dati servono per le richieste API (per validazione, prima di mandare al backend)

from typing import List, Optional
from pydantic import BaseModel


class Node(BaseModel):
    node_id: int
    lat: float
    lon: float


class Coordinates(BaseModel):
    lat: float
    lon: float


class ReverseGeocodingRequest(BaseModel):
    text: str


class IsochroneRequest(BaseModel):
    coords: Coordinates
    min: int
    vel: int


class PoisRequest(BaseModel):
    coords: Coordinates  # lat, lon
    min: int
    vel: int
    categories: List[str]


class NodeRequest(BaseModel):
    node_id: int


# Autenticazione
class UserCreate(BaseModel):
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class User(BaseModel):
    email: str
    preferences: Optional[dict] = None


class UserPreferences(BaseModel):
    min: int
    vel: int
    categories: List[str]


class Token(BaseModel):
    access_token: str
    token_type: str
