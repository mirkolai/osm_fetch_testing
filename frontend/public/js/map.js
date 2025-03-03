let mapInstance = null;

const initializeMap = (containerId, options = {}) => {
    if (mapInstance) {
        return mapInstance;
    }

    const defaultOptions = {
        center: [45.0703, 7.6869],
        zoom: 13
    };

    const mapOptions = { ...defaultOptions, ...options };

    mapInstance = L.map(containerId).setView(mapOptions.center, mapOptions.zoom);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(mapInstance);

    return mapInstance;
};

const getMap = () => mapInstance;

window.mapUtils = {
    initializeMap,
    getMap
};