import geopandas as gpd
import osmnx as ox
import networkx as nx
import gzip
import shutil
import os
import time
from db_ingest import utils


"""
Questo script scarica la rete urbana dei comuni italiani da OpenStreetMap utilizzando come riferimento le geometrie dei confini amministrativi comunali fornite da ISTAT (data/Limiti01012024_g/Com01012024_g/Com01012024_g_WGS84.shp).

I file generati vengono salvati nella cartella output, utilizzando come nome file il codice ISTAT del comune.

Per ciascun comune vengono estratti due grafi principali:

Percorso pedonale: 001001_walk.graphml.gz

Percorso ciclabile: 001001_bike.graphml.gz

Oltre ai grafi corrispondenti ai soli confini comunali, viene generata anche una versione estesa dei grafi.
Questa estensione rappresenta l’area raggiungibile a piedi o in bicicletta in 60 minuti dai confini amministrativi, consentendo di includere zone esterne al territorio comunale.

In questo modo si evitano isocrone troncate lungo i confini, garantendo una rappresentazione più realistica della rete di mobilità.
I relativi file hanno i seguenti nomi:

Percorso pedonale esteso: 001001_walk_extended.graphml.gz

Percorso ciclabile esteso: 001001_bike_extended.graphml.gz

"""



# Carica lo shapefile dei comuni Italiani (scaricato da Istat)
shapefile_path = "db_ingest/data/Limiti01012024_g/Com01012024_g/Com01012024_g_WGS84.shp"  # Specifica il percorso al tuo shapefile
gdf = gpd.read_file(shapefile_path)

# Facoltativo: filtro per provincia letto da .env (COD_PROV_FILTER)
province_filter_raw = utils.get_env("COD_PROV_FILTER", "").strip()
if province_filter_raw:
    try:
        province_filter = int(province_filter_raw)
        region_gdf = gdf[gdf['COD_PROV'] == province_filter]
    except ValueError:
        print(f"COD_PROV_FILTER non valido: '{province_filter_raw}'. Filtro ignorato.")
        region_gdf = gdf
else:
    region_gdf = gdf

# Facoltativo: filtro per codici ISTAT specifici (CITY_CODE_FILTER)
if utils.CITY_CODE_FILTER:
    print(f"CITY_CODE_FILTER attivo: {utils.CITY_CODE_FILTER}")
    region_gdf = region_gdf[region_gdf['PRO_COM_T'].apply(utils.should_process_city)]

# Verifica e trasforma il CRS in EPSG:4326 (se necessario per OSMnx)
if region_gdf.crs.to_string() != "EPSG:4326":
    region_gdf = region_gdf.to_crs("EPSG:4326")

os.makedirs("db_ingest/graphml", exist_ok=True)

# Itera su ogni città e scarica il grafo
graphs = {}
for idx, row in region_gdf.iterrows():
    city_code = row['PRO_COM_T']  # Nome della città
    print(city_code)
    city_polygon = row['geometry']  # Geometria della città
    #print(city_polygon)
    for travel_type in utils.TRAVEL_SPEEDS.keys():
        gzip_filename = f"db_ingest/graphml/{city_code} {travel_type}.graphml.gz"
        graphml_filename = f"db_ingest/graphml/{city_code} {travel_type}.graphml"

        #Se il file esiste già, non lo riscarica da OSM
        if not os.path.isfile(gzip_filename):
            time.sleep(60)  # Aggiungi un ritardo di 1 secondo tra le richieste per evitare di sovraccaricare il server OSM
            # Scarica la rete stradale per la città
            graph = ox.graph_from_polygon(city_polygon, network_type=travel_type, retain_all=True)

            ox.save_graphml(graph, graphml_filename)

            # Comprime il file GraphML in formato .gz usando gzip
            with open(graphml_filename, 'rb') as f_in:
                with gzip.open(gzip_filename, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Elimina il file GraphML non compresso, perchè non necessario
            os.remove(graphml_filename)
        else:
            # Carica il grafo dal file decomresso
            graph = ox.load_graphml(gzip_filename)


        extended_gzip_filename = f"db_ingest/graphml/{city_code} {travel_type} extended.graphml.gz"
        extended_graphml_filename = f"db_ingest/graphml/{city_code} {travel_type} extended.graphml"


        if not os.path.isfile(extended_gzip_filename):

            max_distance = int((max(utils.TRAVEL_TIMES[travel_type]) * 60) * max(utils.TRAVEL_SPEEDS[travel_type]) / 3.6)
            bbox = utils.get_extended_bebop_from_graph(graph, max_distance)
            time.sleep(60)  # Aggiungi un ritardo di 1 secondo tra le richieste per evitare di sovraccaricare il server OSM
            G = ox.graph_from_bbox(bbox=bbox, network_type=travel_type, retain_all=True)
            print(f"BBox and graph recovered: {bbox}")
            node_mapping = {node: str(node) for node in G.nodes}
            G = nx.relabel_nodes(G, node_mapping)
            # Esporta il grafo in formato GraphML compresso con gzip
            ox.save_graphml(G, extended_graphml_filename)

            # Comprime il file GraphML in formato .gz usando gzip
            with open(extended_graphml_filename, 'rb') as f_in:
                with gzip.open(extended_gzip_filename, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Elimina il file GraphML non compresso, perchè non necessario
            os.remove(extended_graphml_filename)