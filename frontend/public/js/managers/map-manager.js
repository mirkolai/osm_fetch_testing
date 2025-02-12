export class MapManager {
    constructor(map) {
        this.map = map;
        this.isochroneLayer = null;
        this.poiMarkers = [];
    }

    clearPoiMarkers() {
        this.poiMarkers.forEach(marker => this.map.removeLayer(marker));
        this.poiMarkers = [];
    }

    addPoiMarkers(pois) {
        this.clearPoiMarkers();

        pois.forEach(poi => {
            const circle = L.circleMarker([
                poi.location.coordinates[0],
                poi.location.coordinates[1]
            ], {
                radius: 6,
                fillColor: '#483d8b',
                color: '#483d8b',
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
            }).bindPopup(`
                <strong>${poi.names.primary || 'Unknown'}</strong><br>
                Category: ${poi.categories.primary || 'Not specified'}<br>
                Distance: ${poi.distance.toFixed(0)}m
            `);

            circle.addTo(this.map);
            this.poiMarkers.push(circle);
        });
    }

    updateIsochroneLayer(data) {
        console.log('Updating isochrone layer with data:', data);

        if (this.isochroneLayer) {
            this.map.removeLayer(this.isochroneLayer);
        }

        if (!data || !data.convex_hull || !data.convex_hull.coordinates) {
            console.error('Invalid isochrone data:', data);
            return;
        }

        try {
            const coordinates = data.convex_hull.coordinates[0].map(coord => [coord[1], coord[0]]);

            this.isochroneLayer = L.polygon(coordinates, {
                color: '#483d8b',
                fillColor: '#483d8b',
                fillOpacity: 0.3,
                weight: 2
            }).addTo(this.map);

            this.map.fitBounds(this.isochroneLayer.getBounds());
        } catch (error) {
            console.error('Error drawing isochrone:', error);
        }
    }
}