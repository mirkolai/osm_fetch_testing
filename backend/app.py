from flask import Flask, request, jsonify, send_from_directory
import requests

app = Flask(__name__)

# Funzione per ottenere il bounding box di una città tramite Nominatim
def get_city_bbox(city):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': "Nizza Monferrato",
        'format': 'json',
        'limit': 1
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        if data:
            boundingbox = data[0]['boundingbox']  # Restituisce [min_lat, max_lat, min_lon, max_lon]
            return f"{boundingbox[0]},{boundingbox[2]},{boundingbox[1]},{boundingbox[3]}"
    return None

# Endpoint per servire il file HTML
@app.route('/')
def serve_frontend():
    return send_from_directory('../frontend', 'index.html')

# Endpoint per ottenere dati da OpenStreetMap
@app.route('/api/osm_data', methods=['GET'])
def get_osm_data():
    city = request.args.get('city', 'Nizza Monferrato')  # Default: Milano
    bbox = (44.7385442, 44.7947340, 8.3031507, 8.4038346)
    if not bbox:
        return jsonify({"error": f"Impossibile trovare il bounding box per la città: {city}"}), 404

    # Query per Overpass API
    query = f"""
    [out:json];
    (
      node({bbox});  // Tutti i nodi nell'area
      way({bbox});   // Tutte le strade nell'area
      relation({bbox}); // Tutte le relazioni nell'area
    );
    out body;
    >;
    out skel qt;
    """
    try:
        response = requests.get("https://overpass-api.de/api/interpreter", params={'data': query})
        response.raise_for_status()  # Solleva eccezione per errori HTTP
        return jsonify(response.json())
    except requests.RequestException as e:
        return jsonify({"error": "Impossibile ottenere i dati da Overpass API", "details": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
