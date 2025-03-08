from typing import List

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
