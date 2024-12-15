document.addEventListener('DOMContentLoaded', function() {
    const map = L.map('map').setView([45.0703, 7.6869], 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
});