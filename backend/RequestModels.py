# questo file contiene quali dati servono per le richieste API (per validazione, prima di mandare al backend)

from typing import List
from pydantic import BaseModel


class Coordinates(BaseModel):
    lat: float
    lon: float


class GeocodingRequest(BaseModel):
    text: str

class Place(BaseModel):
    name: str
    importance: float
    coordinates: List[float]