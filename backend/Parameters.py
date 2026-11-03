import math

from shapely.geometry import shape
from shapely.ops import transform
import pyproj

from backend.postgres_db import get_postgres_connection
from backend.Connectivity import get_closeness_by_node_id
from backend.category_mapping import aggregate_secondary_counts, get_new_groups



def get_precomputed_metrics_rows(node_id, velocity, city_code, network_mode):
    """
    Legge da precomputed_metrics_rows le righe del nodo per velocity, city_code e network_mode.

    Restituisce una riga per ogni tempo di percorrenza, ordinate per travel_time.
    """
    query = """
        SELECT
            city_code,
            neighbourhood_id,
            network_mode,
            travel_time,
            velocity_kmh,
            node_id,
            category_primary_counts,
            category_secondary_counts,
            isochrone_area_km2,
            total_pois
        FROM precomputed_metrics_rows
        WHERE node_id = %s
          AND velocity_kmh = %s
          AND city_code = %s
          AND network_mode = %s
    """
    query += " ORDER BY travel_time"

    conn = get_postgres_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (node_id, velocity, city_code, network_mode))
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()





def compute_isochrone_parameters(
    node_id,
    city_code,
    velocity,
    travel_time,
    network_mode,
    max_minutes,
    selected_categories,
):
    """
    Calcola le metriche aggregate mostrate nei grafici dello user study.

    Le metriche vengono tutte ricondotte nell'intervallo 0-1, così il frontend
    può confrontarle nello stesso radar chart senza altra normalizzazione.
    """

    result=get_precomputed_metrics_rows(node_id, velocity, city_code, network_mode)

    #print("result", result)
    #esempio di result:
    #[{'city_code': '001272', 'neighbourhood_id': '1', 'network_mode': 'walk', 'travel_time': 5, 'velocity_kmh': 5, 'node_id': 438238719, 'category_primary_counts': [1, 3, 1, 2, 8, 0, 117, 15, 3, 194, 17, 8, 6], 'category_secondary_counts': [0, 0, 1, 0, 0, 2, 0, 15, 0, 9, 0, 0, 0, 3, 2, 0, 20, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 2, 0, 0, 3, 0, 26, 1, 0, 2, 0, 0, 1, 1, 0, 3, 0, 0, 1, 0, 1, 0, 0, 0, 0, 1, 69, 0, 0, 0, 2, 1, 0, 0, 0, 0, 0, 0, 1, 111, 0, 0, 0, 6, 2, 0, 0, 2, 26, 0, 0, 1, 13, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 4, 11, 0, 0, 5, 2, 1, 0, 0, 0, 3, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 7], 'isochrone_area_km2': 0.13498390210836358, 'total_pois': 378}, {'city_code': '001272', 'neighbourhood_id': '1', 'network_mode': 'walk', 'travel_time': 10, 'velocity_kmh': 5, 'node_id': 438238719, 'category_primary_counts': [35, 36, 16, 31, 138, 1, 458, 125, 35, 909, 275, 43, 47], 'category_secondary_counts':...
    for row in result:
        if row["travel_time"] == travel_time:
            category_secondary_counts = row["category_secondary_counts"] 
            break
    
    # DENSITY
    area_km2 = 0
    total_pois = 0

    area_km2 = row["isochrone_area_km2"]
            
    # I conteggi del DB (categorie originali) vengono aggregati per NewSecondaryName.
    aggregated_counts = aggregate_secondary_counts(category_secondary_counts)
    selected_categories = [cat for cat in dict.fromkeys(selected_categories) if cat in aggregated_counts]

    for cat in selected_categories:
        total_pois = total_pois + aggregated_counts[cat]

    
    if total_pois == 0 or area_km2 == 0:
        density = 0
    else:
        density = total_pois/area_km2
    #print("density", density)

    # ENTROPY
    counts = {cat: aggregated_counts[cat] for cat in selected_categories}



    H = 0.0
    for cat in selected_categories:
        if counts[cat] > 0:
            p = counts[cat] / total_pois
            H -= p * math.log2(p)

    k = len(selected_categories)
    max_H = math.log2(k) if k > 1 else 1.0
    if max_H > 0:
        entropy = H / max_H
    else:
        entropy = 0
    #print("entropy", entropy)


    # PROXIMITY
    sorted_precomputed_row = sorted(result, key=lambda x: x['travel_time'])
    proximity = max_minutes

    selected_set = set(selected_categories)
    # Solo le primary con almeno una categoria selezionata sono richieste.
    required_groups = {
        primary: [s for s in secondary_list if s in selected_set]
        for primary, secondary_list in get_new_groups().items()
    }
    required_groups = [sl for sl in required_groups.values() if sl]

    for item in sorted_precomputed_row if required_groups else []:
        item_counts = aggregate_secondary_counts(item['category_secondary_counts'])

        # Ogni primary (con categorie selezionate) deve avere almeno una categoria presente
        if all(any(item_counts[s] > 0 for s in secondary_list) for secondary_list in required_groups):
            proximity = item['travel_time']
            break


    #print("proximity", proximity)
    # La closeness arriva dalla collection connectivity; fallback 0.0 se non disponibile.
    
    closeness_status, _, closeness = get_closeness_by_node_id(
        node_id=node_id,
        travel_mode=network_mode,
    )
    if closeness_status != 200:
        closeness = 0.0

    #print("closeness", closeness)
    return {
        "proximity": proximity,
        "density": density,
        "entropy": entropy,
        "closeness": closeness,
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