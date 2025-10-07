from typing import Union, List, Tuple, Dict
from backend.db import db
import logging

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def get_all_neighbourhoods(city_name: str = None) -> Tuple[int, str, Union[List[Dict], None]]:
    """
    Recupera tutti i quartieri dalla collezione 'neighbourhood_polygon'.
    
    Args:
        city_name: Nome della città per validare se i quartieri sono disponibili
    
    Returns:
        Tuple[int, str, Union[List[Dict], None]]: (status_code, message, neighbourhoods_list)
    """
    try:
        logging.info(f"Fetching neighbourhoods for city: {city_name}")
        
        # per ora abbiamo solo Torino nel database
        if city_name and city_name.lower() not in ['torino', 'turin']:
            return 404, f"No neighbourhood data available for {city_name}. Currently only Torino is supported.", None
        
        collection = db["neighbourhood_polygon"]
        
        # cerchiamo tutti i documenti con i quartieri
        documents = list(collection.find({"neighbourhoods": {"$exists": True}}))
        
        if not documents:
            return 404, "No neighbourhoods found", None
        
        neighbourhoods_list = []
        
        for doc in documents:
            # prendiamo tutti i quartieri dal documento
            doc_neighbourhoods = doc.get("neighbourhoods", [])
            
            for neighbourhood in doc_neighbourhoods:
                # prendiamo la geometria del convex_hull
                geometry = neighbourhood.get("geometry", {})
                convex_hull = geometry.get("convex_hull", {})
                
                if convex_hull and "features" in convex_hull:
                    features = convex_hull["features"]
                    
                    for feature in features:
                        feature_geometry = feature.get("geometry", {})
                        
                        if feature_geometry.get("type") == "Polygon":
                            coordinates = feature_geometry.get("coordinates", [])
                            bbox = feature.get("bbox", [])
                            
                            if coordinates:
                                # convertiamo le coordinate per Leaflet (usa [lat, lon] invece di [lon, lat])
                                polygon_coords = []
                                for ring in coordinates:
                                    converted_ring = [[coord[1], coord[0]] for coord in ring]
                                    polygon_coords.append(converted_ring)
                                
                                neighbourhood_data = {
                                    "id": neighbourhood.get("id"),
                                    "coordinates": polygon_coords,
                                    "bbox": bbox,
                                    "properties": feature.get("properties", {})
                                }
                                
                                neighbourhoods_list.append(neighbourhood_data)
        
        logging.info(f"Found {len(neighbourhoods_list)} neighbourhoods")
        return 200, "OK", neighbourhoods_list
        
    except Exception as e:
        logging.error(f"Error fetching neighbourhoods: {str(e)}")
        return 500, f"Server error: {str(e)}", None


def get_neighbourhoods_by_coordinates(lat: float, lon: float) -> Tuple[int, str, Union[List[Dict], None]]:
    """
    Trova i quartieri che contengono un punto specifico usando le coordinate.
    
    Args:
        lat: Latitudine del punto
        lon: Longitudine del punto
    
    Returns:
        Tuple[int, str, Union[List[Dict], None]]: (status_code, message, neighbourhoods_list)
    """
    try:
        logging.info(f"Finding neighbourhoods containing point: lat={lat}, lon={lon}")
        collection = db["neighbourhood_polygon"]
        
        # cerchiamo quartieri che contengono questo punto
        # MongoDB usa [lon, lat] per le coordinate
        query = {
            "neighbourhoods": {
                "$elemMatch": {
                    "geometry.convex_hull": {
                        "$geoIntersects": {
                            "$geometry": {
                                "type": "Point",
                                "coordinates": [lon, lat]
                            }
                        }
                    }
                }
            }
        }
        
        documents = list(collection.find(query))
        
        if not documents:
            return 404, "No neighbourhoods found for the given coordinates", None
        
        neighbourhoods_list = []
        
        for doc in documents:
            doc_neighbourhoods = doc.get("neighbourhoods", [])
            
            for neighbourhood in doc_neighbourhoods:
                geometry = neighbourhood.get("geometry", {})
                convex_hull = geometry.get("convex_hull", {})
                
                if convex_hull and "features" in convex_hull:
                    features = convex_hull["features"]
                    
                    for feature in features:
                        feature_geometry = feature.get("geometry", {})
                        if feature_geometry.get("type") == "Polygon":
                            coordinates = feature_geometry.get("coordinates", [])
                            bbox = feature.get("bbox", [])
                            
                            if coordinates:
                                # convertiamo le coordinate per Leaflet
                                polygon_coords = []
                                for ring in coordinates:
                                    converted_ring = [[coord[1], coord[0]] for coord in ring]
                                    polygon_coords.append(converted_ring)
                                
                                neighbourhood_data = {
                                    "id": neighbourhood.get("id"),
                                    "coordinates": polygon_coords,
                                    "bbox": bbox,
                                    "properties": feature.get("properties", {})
                                }
                                
                                neighbourhoods_list.append(neighbourhood_data)
        
        logging.info(f"Found {len(neighbourhoods_list)} neighbourhoods for coordinates")
        return 200, "OK", neighbourhoods_list
        
    except Exception as e:
        logging.error(f"Error finding neighbourhoods by coordinates: {str(e)}")
        # se la query geospaziale fallisce, prendiamo tutti i quartieri
        logging.info("Falling back to get all neighbourhoods")
        return get_all_neighbourhoods()
