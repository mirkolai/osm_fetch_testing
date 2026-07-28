import json
import time

import geopandas as gpd
import osmnx as ox
import networkx as nx
import gzip
import shutil
import os
import glob
import numpy as np
import overturemaps
from shapely import wkb
from db_ingest import utils


"""
Questo script scarica i Point of Interest (PoI) dal database Overture per ciascun comune di cui è disponibile la rete ciclabile estesa.
La rete ciclabile estesa include anche le aree raggiungibili a piedi e viene recuperata dalla cartella output, ad esempio:

001001_bike_extended.graphml.gz

Overture consente di estrarre i PoI che ricadono all’interno del bounding box corrispondente alla rete ciclabile estesa.
Per ogni comune viene quindi generato un file contenente tutti i PoI inclusi in tale bounding box, salvato in formato Feather con compressione zstd:

001001_PoI.feather.zstd

"""

def my_overture(bbox):
    table = overturemaps.record_batch_reader("place", bbox).read_all()
    table = table.combine_chunks()
    return table

for extended_gzip_filename in glob.glob("db_ingest/graphml/* bike extended.graphml.gz"):


    temp_path = extended_gzip_filename+".temp"
    city_code =  extended_gzip_filename.split("/")[-1].replace("bike extended.graphml.gz", " ").strip()

    if not utils.should_process_city(city_code):
        print(f"Skip {city_code} (non in CITY_CODE_FILTER)")
        continue
    print(city_code)

    gzip_geojson_path = f"db_ingest/graphml/{city_code} PoI.feather.zstd"
    if os.path.isfile(gzip_geojson_path):
        continue

    # Decomprimi il file gzip
    with gzip.open(extended_gzip_filename, 'rt', encoding='utf-8') as f_in:
        with open(temp_path, 'w', encoding='utf-8') as f_out:
            shutil.copyfileobj(f_in, f_out)

    # Carica il grafo dal file decomresso
    G = ox.load_graphml(temp_path)
    node_mapping = {node: str(node) for node in G.nodes}
    G = nx.relabel_nodes(G, node_mapping)

    # Rimuovi il file temporaneo
    os.remove(temp_path)

    west, south, east, north = utils.get_bbox_from_graph(G)
    #print((west, south, east, north))

    gzip_geojson_path = f"db_ingest/graphml/{city_code} PoI.feather.zstd"

    # specify bounding box
    bbox = west, south, east, north
    # read in Overture Maps land_cover data type
    done=False
    while not done:
        try:
            table=my_overture(bbox)
            df = table.to_pandas()
            df['geometry'] = df['geometry'].apply(lambda x: wkb.loads(x) if x else None)

            gdf = gpd.GeoDataFrame(df, geometry='geometry')
            gdf.to_feather(gzip_geojson_path, index=False, compression="zstd")
            done=True
            print("done")
            time.sleep(30)
        except  Exception as e:
            print("error",e)
            done=False
            time.sleep(60)

    time.sleep(30)

