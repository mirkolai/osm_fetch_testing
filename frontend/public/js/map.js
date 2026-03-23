let mapInstance = null;

// DEBUG MODE: Set to true to disable bounding box and zoom limits for testing
const DEBUG_MODE = true;

const initializeMap = (containerId, options = {}) => {
    if (mapInstance) {
        return mapInstance;
    }

    const defaultOptions = {
        center: [45.0703, 7.6869],
        maxBounds: [
            [44.99, 7.58],  // Sud-Ovest
            [45.15, 7.78]   // Nord-Est
        ],
        maxBoundsViscosity: 1.0, // blocco rigido
        zoom: 13,
        minZoom: 12,
        maxZoom: 18
    };

    const mapOptions = { ...defaultOptions, ...options };

    // Build map config based on DEBUG_MODE
    const mapConfig = {
        minZoom: DEBUG_MODE ? 0 : mapOptions.minZoom,
        maxZoom: DEBUG_MODE ? 28 : mapOptions.maxZoom
    };

    // Only add bounding box constraints if not in debug mode
    if (!DEBUG_MODE) {
        mapConfig.maxBounds = mapOptions.maxBounds;
        mapConfig.maxBoundsViscosity = mapOptions.maxBoundsViscosity;
    }

    mapInstance = L.map(containerId, mapConfig).setView(mapOptions.center, mapOptions.zoom);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(mapInstance);

    // Log debug info
    if (DEBUG_MODE) {
        console.warn('⚠️ MAP DEBUG MODE ENABLED - Bounding box and zoom limits are DISABLED');
    }

    return mapInstance;
};

const getMap = () => mapInstance;

window.mapUtils = {
    initializeMap,
    getMap
};