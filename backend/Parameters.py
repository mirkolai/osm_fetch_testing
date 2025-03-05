import math
from shapely.geometry import shape
from shapely.ops import transform
import pyproj


def compute_isochrone_parameters(pois_data, isochrone_data, vel, total_pois, max_minutes=60, categories=None):
    """
    Calcola i parametri:
    - Proximity
    - Density
    - Entropy
    - Poi Accessibility
    """
    if categories is None:
        categories = []

    # 1) Calcolo area isocrona
    area_km2 = compute_area_km2_from_iso(isochrone_data)  # funzione vista sopra
    print("KM2: ", area_km2)

    # 2) Calcolo proximity (in minuti): POI più "lontano" in termini di tempo
    #    distance in metri, velocità vel (km/h) => tempo_min = distance / (vel*1000/60)
    if not pois_data:
        proximity_min = "ND"
    else:
        speed_m_min = (vel * 1000) / 60.0
        times = []
        for poi in pois_data:
            d_m = poi["distance"]
            t = d_m / speed_m_min
            times.append(t)
        proximity_min = max(times)  # in minuti
    print("PROXIMITY NON NORM: ", proximity_min)

    # 3) Normalizzo proximity in [0..1]
    if isinstance(proximity_min, str) and proximity_min == "ND":
        proximity_score = 0.0
    else:
        proximity_score = min(proximity_min / max_minutes, 1.0)

    # 4) Calcolo density
    print("TOT POIS in Param: ", total_pois)

    if total_pois == 0 or area_km2 == 0:
        density_raw = 0
    else:
        density_raw = total_pois/area_km2
    print("DENSITY NON NORM: ", density_raw)
    # Normalizza [0..1], con > 100 => 1
    if density_raw > 100:
        density_score = 1.0
    else:
        density_score = density_raw / 100.0

    # 5) Calcolo entropia
    if total_pois == 0:
        entropy_score = 0.0
    else:
        # Conta quante volte appare ogni categoria
        counts = {cat: 0 for cat in categories}
        for poi in pois_data:
            primary = poi["categories"]["primary"]
            if primary in counts:
                counts[primary] += 1
            else:
                # se non è nella primary, guarda le alternate
                for alt in poi["categories"].get("alternate", []):
                    if alt in counts:
                        counts[alt] += 1
                        break
        print("NUMERI PER CATEGORIA")
        for cat in categories:
            print(cat, ":", counts[cat])

        # Entropia di Shannon (in base 2)
        total_pois = float(total_pois)
        H = 0.0
        for cat in categories:
            if counts[cat] > 0:
                p = counts[cat] / total_pois
                H -= p * math.log2(p)
        print("ENTROPY NON NORM: ", H)

        # Normalizzi su log2(k)
        k = len(categories)
        max_H = math.log2(k) if k > 1 else 1.0
        if max_H > 0:
            entropy_score = H / max_H
        else:
            entropy_score = 0.0

    # 6) Calcolo PoiAccessibility = media (proximity_score, density_score, entropy_score)
    poi_accessibility = (proximity_score + density_score + entropy_score) / 3.0
    print("POIS ACCECCIBILITY: ", poi_accessibility)

    return {
        "proximity": proximity_min,
        "proximity_score": proximity_score,
        "density_score": density_score,
        "entropy_score": entropy_score,
        "poi_accessibility": poi_accessibility,
    }

def compute_area_km2_from_iso(isochrone_data: dict) -> float:
    """
    Calcola l'area in km^2 data la geometria dell'isocrona (convex_hull).
    isochrone_data è il JSON di /api/get_isochrone
    """
    try:
        coords = isochrone_data["convex_hull"]["coordinates"]  # poligono in GeoJSON

        # Costruisci un dict GeoJSON "minimo" di tipo Polygon
        polygon_geojson = {
            "type": "Polygon",
            "coordinates": coords
        }

        polygon_wgs84 = shape(polygon_geojson)  # shapely geometry in WGS84

        # Proiezione in metri (EPSG:3857 o altra proiezione consona)
        project = pyproj.Transformer.from_crs(
            "EPSG:4326",  # WGS84
            "EPSG:3857",  # proiezione metrica
            always_xy=True
        ).transform

        polygon_m = transform(project, polygon_wgs84)
        area_m2 = polygon_m.area
        area_km2 = area_m2 / 1_000_000.0
        return area_km2
    except:
        return 0.0