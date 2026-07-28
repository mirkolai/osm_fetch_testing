import sys
from pathlib import Path


from pymongo import MongoClient
from pymongo.errors import OperationFailure
import geopandas as gpd

from shapely.geometry import MultiPolygon, Polygon
from db_ingest import utils

"""
Questo script inserisce in un database MongoDB i confini amministrativi comunali insieme ai relativi codici ISTAT e ai vari livelli territoriali associati.
Per ciascun comune, oltre ai metadati, viene salvata anche la geometria del confine amministrativo.

In questo modo è possibile interrogare la collezione per ottenere, dato un punto geografico, il comune (e i relativi codici ISTAT) in cui quel punto ricade.
Questo consente, ad esempio, di determinare automaticamente le informazioni amministrative corrispondenti a una coordinata geografica.

Campi salvati nella collezione [city_polygon]

Campo	Descrizione
PRO_COM_T	Codice ISTAT completo del comune (testuale)
PRO_COM	Codice ISTAT numerico del comune
COD_UTS	Codice Unità Territoriale Sovracomunale (se presente)
COD_CM	Codice Comunità Montana
COD_PROV	Codice Provincia
COD_REG	Codice Regione
COD_RIP	Codice Ripartizione geografica
COMUNE	Nome del comune
Shape_Leng	Lunghezza del perimetro del confine
Shape_Area	Area del confine
geometry	Geometria del confine amministrativo (poligono GeoJSON)
"""

# Create a connection using MongoClient. You can import MongoClient or use pymongo.MongoClient
client = MongoClient(utils.CONNECTION_STRING)
db = client[utils.MONGO_DB_NAME]  # Nome del database
collection = db["city_polygon"]  # Nome della collezione




collection.drop()

collection.create_index([("PRO_COM_T", 1)], unique=True)
collection.create_index([("geometry", "2dsphere")])

# Carica lo shapefile
shapefile_path = "db_ingest/data/Limiti01012024_g/Com01012024_g/Com01012024_g_WGS84.shp"  # Specifica il percorso al tuo shapefile
gdf = gpd.read_file(shapefile_path)

# Facoltativo: filtro per provincia letto da .env (COD_PROV_FILTER)
province_filter_raw = utils.get_env("COD_PROV_FILTER", "").strip()
if province_filter_raw:
    try:
        province_filter = int(province_filter_raw)
        gdf = gdf[gdf['COD_PROV'] == province_filter]
    except ValueError:
        print(f"COD_PROV_FILTER non valido: '{province_filter_raw}'. Filtro ignorato.")

# Facoltativo: filtro per codici ISTAT specifici (CITY_CODE_FILTER)
if utils.CITY_CODE_FILTER:
    print(f"CITY_CODE_FILTER attivo: {utils.CITY_CODE_FILTER}")
    gdf = gdf[gdf['PRO_COM_T'].apply(utils.should_process_city)]

# Verifica e trasforma il CRS in EPSG:4326 (se necessario per OSMnx)
print(gdf.crs.to_string())
if gdf.crs.to_string() != "EPSG:4326":
    gdf = gdf.to_crs("EPSG:4326")

# Itera su ogni città e scarica il grafo
graphs = {}
for idx, row in gdf.iterrows():
    print(row['COMUNE'])

    # Supponiamo che row['geometry'] contenga un MultiPolygon
    #print(type(row['geometry'])) #<class 'shapely.geometry.polygon.Polygon'>
    geometry = row['geometry'].__geo_interface__


    print("inserting")

    city_data = {
        "PRO_COM_T": row['PRO_COM_T'],
        "PRO_COM": row['PRO_COM'],
        "COD_UTS": row['COD_UTS'],
        "COD_CM": row['COD_CM'],
        "COD_PROV": row['COD_PROV'],
        "COD_REG": row['COD_REG'],
        "COD_RIP": row['COD_RIP'],
        "COMUNE": row['COMUNE'],
        "Shape_Leng": row['Shape_Leng'],
        "Shape_Area": row['Shape_Area'],
        "geometry": geometry
    }

    # Inserisci nel database MongoDB
    try:
        collection.insert_one(city_data)  # Inserisce il documento
    except Exception as e:
        print(f"Errore nell'inserimento del comune {row['COMUNE']}")




# Esegui la funzione con un punto di esempio
utils.trova_citta_per_punto(collection,12.345, 45.678)

