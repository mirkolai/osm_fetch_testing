import math

from shapely.geometry import shape
from shapely.ops import transform
import pyproj


def compute_isochrone_parameters(
    pois_data,
    isochrone_data,
    vel,
    total_pois,
    max_minutes=60,
    categories=None,
    closeness_value=None,
):
    """
    Calcola le metriche aggregate mostrate nei grafici dello user study.

    Le metriche vengono tutte ricondotte nell'intervallo 0-1, così il frontend
    può confrontarle nello stesso radar chart senza altra normalizzazione.
    """
    if categories is None:
        categories = []

    # L'area dell'isocrona è la base per density e per interpretare il numero di POI.
    area_km2 = compute_area_km2_from_iso(isochrone_data)

    # La proximity è il tempo massimo richiesto per raggiungere un POI nell'insieme filtrato.
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
    #print("PROXIMITY NON NORM: ", proximity_min)

    if isinstance(proximity_min, str) and proximity_min == "ND":
        proximity_score = 0.0
    else:
        proximity_score = min(proximity_min / max_minutes, 1.0)

    # La density rapporta il numero totale di POI all'area dell'isocrona.
    if total_pois == 0 or area_km2 == 0:
        density_raw = 0
    else:
        density_raw = total_pois/area_km2

    # Oltre 100 POI/km^2 la metrica viene saturata a 1 per evitare valori estremi.
    if density_raw > 100:
        density_score = 1.0
    else:
        density_score = density_raw / 100.0

    # L'entropia misura quanto le categorie sono distribuite in modo vario.
    if total_pois == 0:
        entropy_score = 0.0
    else:
        counts = {cat: 0 for cat in categories}
        for poi in pois_data:
            primary = poi["categories"]["primary"]
            if primary in counts:
                counts[primary] += 1
            else:
                # Se la categoria primaria non rientra nel filtro, prova con le alternate.
                for alt in (poi["categories"].get("alternate") or []):
                    if alt in counts:
                        counts[alt] += 1
                        break

        total_pois = float(total_pois)
        H = 0.0
        for cat in categories:
            if counts[cat] > 0:
                p = counts[cat] / total_pois
                H -= p * math.log2(p)
        #print("ENTROPY NON NORM: ", H)

        k = len(categories)
        max_H = math.log2(k) if k > 1 else 1.0
        if max_H > 0:
            entropy_score = H / max_H
        else:
            entropy_score = 0.0

    # PoiAccessibility sintetizza le tre metriche principali in un unico punteggio medio.
    poi_accessibility = (proximity_score + density_score + entropy_score) / 3.0

    # La closeness arriva dalla collection connectivity; fallback 0.0 se non disponibile.
    closeness_score = 0.0 if closeness_value is None else float(closeness_value)

    return {
        "proximity": proximity_min,
        "proximity_score": proximity_score,
        "density_score": density_score,
        "entropy_score": entropy_score,
        "closeness": closeness_score,
        "poi_accessibility": poi_accessibility,
    }

def compute_area_km2_from_iso(isochrone_data: dict) -> float:
    """
    Calcola l'area in km^2 data la geometria dell'isocrona (convex_hull).
    isochrone_data è il JSON di /api/get_isochrone
    """
    try:
        coords = isochrone_data["convex_hull"]["coordinates"]  # poligono in GeoJSON

        # Costruisce una geometria GeoJSON minima che shapely può convertire in poligono.
        polygon_geojson = {
            "type": "Polygon",
            "coordinates": coords
        }

        polygon_wgs84 = shape(polygon_geojson)  # shapely geometry in WGS84

        # La trasformazione in EPSG:3857 serve per ottenere un'area metrica leggibile in m^2.
        project = pyproj.Transformer.from_crs(
            "EPSG:4326",  # WGS84
            "EPSG:3857",  # proiezione metrica
            always_xy=True
        ).transform

        polygon_m = transform(project, polygon_wgs84)
        area_m2 = polygon_m.area
        area_km2 = area_m2 / 1_000_000.0
        return area_km2
    except Exception:
        return 0.0