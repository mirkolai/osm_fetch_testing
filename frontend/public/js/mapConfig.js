// Configura la mappa con Leaflet
const map = L.map('map').setView([44.763, 8.353], 13); // Coordinate iniziali

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);
