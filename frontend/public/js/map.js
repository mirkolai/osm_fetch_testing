/*document.addEventListener('DOMContentLoaded', function() {
    const map = L.map('map').setView([45.0703, 7.6869], 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
});*/

let map = null;

function initializeMap(containerId, options = {}) {
    if (map) {
        return map;
    }

    const defaultOptions = {
        center: [45.0703, 7.6869],
        zoom: 13
    };

    const mapOptions = { ...defaultOptions, ...options };

    map = L.map(containerId).setView(mapOptions.center, mapOptions.zoom);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    return map;
}

window.mapUtils = {
    initializeMap,
    getMap: () => map
};
