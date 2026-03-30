import { SpiderChart } from './components/SpiderChart.js';

let currentSessionId = sessionStorage.getItem('session_id');
let selectedStreet = null;
let selectedCoords = null;
let analysisComplete = false;
let streetSelectionLocked = false;
let spiderChart = null;

function createSessionAndRedirectToWelcome() {
    fetch('/api/userstudy/session/create', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data && data.status === 'success' && data.session_id) {
                sessionStorage.setItem('session_id', data.session_id);
            }
        })
        .catch(error => {
            console.error('Errore nella creazione sessione:', error);
        })
        .finally(() => {
            window.location.href = '/userstudy/welcome';
        });
}

let torinoCenter = [45.0703, 7.6869];
let torinoMaxBounds = [[44.99, 7.58], [45.15, 7.78]];

// DEBUG MODE: Set to true to disable bounding box and zoom limits for testing
const DEBUG_MODE = true;

// DOM Elements
const citySearch = document.getElementById('city-search');
const suggestionsList = document.getElementById('suggestions');
const selectedStreetInfo = document.getElementById('selected-street-info');
const streetNameSpan = document.getElementById('street-name');
const streetCoordsSpan = document.getElementById('street-coords');
const btnAnalyze = document.getElementById('btn-analyze');
const btnNext = document.getElementById('btn-next');
const loadingSpinner = document.getElementById('loading-spinner');
const errorMessage = document.getElementById('error-message');
const modalOverlay = document.getElementById('modal-overlay');
const modalClose = document.getElementById('modal-close');
const btnViewAnalysis = document.getElementById('btn-view-analysis');

// Session check
if (!currentSessionId) {
    createSessionAndRedirectToWelcome();
    throw new Error('No session ID found');
}

// Initialize map with DEBUG_MODE support
const mapConfig = {
    minZoom: DEBUG_MODE ? 0 : 12,
    maxZoom: DEBUG_MODE ? 28 : 18
};

// Only add bounding box constraints if not in debug mode
if (!DEBUG_MODE) {
    mapConfig.maxBounds = torinoMaxBounds;
    mapConfig.maxBoundsViscosity = 1.0;
}

const map = L.map('map', mapConfig).setView(torinoCenter, 13);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap',
    maxZoom: 19
}).addTo(map);

// Log debug info
if (DEBUG_MODE) {
    console.warn('⚠️ MAP DEBUG MODE ENABLED - Bounding box and zoom limits are DISABLED');
}

// Layer groups for map elements
let selectedMarker = null;
let isochroneLayer = null;
let poiMarkers = [];

// Debounce function
function debounce(func, delay) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

// Geocoding search
const debouncedSearch = debounce(handleSearchInput, 1500);

citySearch.addEventListener('input', debouncedSearch);

async function handleSearchInput() {
    if (streetSelectionLocked) {
        return;
    }

    const query = citySearch.value.trim();
    errorMessage.classList.remove('show');
    
    if (query.length < 3) {
        suggestionsList.innerHTML = '';
        suggestionsList.classList.remove('show');
        return;
    }
    
    try {
        const response = await fetch('/api/geocoding', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: query })
        });
        
        const results = await response.json();
        
        suggestionsList.innerHTML = '';
        if (results && results.length > 0) {
            results.slice(0, 5).forEach(result => {
                const item = document.createElement('li');
                item.className = 'list-group-item';
                item.setAttribute('data-lat', result.coordinates[0]);
                item.setAttribute('data-lon', result.coordinates[1]);
                item.textContent = result.name;
                item.addEventListener('click', () => selectStreet(result));
                suggestionsList.appendChild(item);
            });
            suggestionsList.classList.add('show');
            
            // Position dropdown with fixed positioning to avoid overflow clipping
            const searchInput = document.querySelector('.search-input-group input');
            const rect = searchInput.getBoundingClientRect();
            suggestionsList.style.position = 'fixed';
            suggestionsList.style.top = (rect.bottom + 2) + 'px';
            suggestionsList.style.left = rect.left + 'px';
            suggestionsList.style.width = (rect.width + 20) + 'px';
        }
    } catch (error) {
        console.error('Errore nella ricerca:', error);
        showError('Errore nella ricerca. Prova di nuovo.');
    }
}

function setStreetSelectionLocked(locked) {
    streetSelectionLocked = locked;
    citySearch.readOnly = locked;
    citySearch.style.backgroundColor = locked ? '#f8f9fa' : '';
    citySearch.style.cursor = locked ? 'not-allowed' : '';

    if (locked) {
        suggestionsList.innerHTML = '';
        suggestionsList.classList.remove('show');
    }
}

function selectStreet(result) {
    if (streetSelectionLocked) {
        return;
    }

    selectedStreet = result.name;
    selectedCoords = {
        lat: result.coordinates[0],
        lon: result.coordinates[1]
    };
    
    citySearch.value = result.name;
    suggestionsList.innerHTML = '';
    suggestionsList.classList.remove('show');
    analysisComplete = false;
    btnNext.disabled = true;
    btnViewAnalysis.classList.remove('show');
    
    // Update map
    if (selectedMarker) {
        map.removeLayer(selectedMarker);
    }
    
    selectedMarker = L.marker([selectedCoords.lat, selectedCoords.lon], {
        icon: L.icon({
            iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
        })
    }).addTo(map);
    
    // Clear old isochrone and POI markers
    clearMapElements();
    
    map.setView([selectedCoords.lat, selectedCoords.lon], 14);
    
    // Show selected street info
    streetNameSpan.textContent = selectedStreet;
    streetCoordsSpan.textContent = `${selectedCoords.lat.toFixed(4)}°, ${selectedCoords.lon.toFixed(4)}°`;
    selectedStreetInfo.classList.add('show');
    
    // Enable analyze button
    btnAnalyze.disabled = false;
}

function clearMapElements() {
    if (isochroneLayer) {
        map.removeLayer(isochroneLayer);
        isochroneLayer = null;
    }
    
    poiMarkers.forEach(marker => {
        map.removeLayer(marker);
    });
    poiMarkers = [];
}

// Analyze button
btnAnalyze.addEventListener('click', analyzeArea);

async function analyzeArea() {
    if (!selectedStreet || !selectedCoords) {
        showError('Per favore, seleziona una via prima di analizzare.');
        return;
    }

    setStreetSelectionLocked(true);
    btnAnalyze.disabled = true;
    loadingSpinner.classList.add('show');
    errorMessage.classList.remove('show');
    
    try {
        const response = await fetch('/api/userstudy/analyze-area', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                latitude: selectedCoords.lat,
                longitude: selectedCoords.lon
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Errore nell\'analisi dell\'area');
        }
        
        // Clear old elements
        clearMapElements();
        
        // Visualize isochrone
        if (data.isochrone && data.isochrone.convex_hull) {
            drawIsochrone(data.isochrone.convex_hull);
        }
        
        // Visualize POIs
        if (data.pois && Array.isArray(data.pois) && data.pois.length > 0) {
            console.log('Disegnando', data.pois.length, 'POIs sulla mappa');
            drawPOIs(data.pois);
        }
        
        // Show spider chart modal
        showSpiderChartModal(data.parameters);
        
        analysisComplete = true;
        btnNext.disabled = false;
        btnViewAnalysis.classList.add('show');
        
    } catch (error) {
        console.error('Errore nell\'analisi:', error);
        showError('Errore nell\'analisi dell\'area. Prova di nuovo.');
        setStreetSelectionLocked(false);
        btnAnalyze.disabled = false;
    } finally {
        loadingSpinner.classList.remove('show');
    }
}

function drawIsochrone(convexHull) {
    if (!convexHull.coordinates || convexHull.coordinates.length === 0) {
        return;
    }
    
    // convexHull.coordinates è un array di arrays di [lon, lat]
    const coordinates = convexHull.coordinates[0].map(coord => [coord[1], coord[0]]);
    
    isochroneLayer = L.polygon(coordinates, {
        color: '#483d8b',
        weight: 2,
        opacity: 0.7,
        fillColor: '#483d8b',
        fillOpacity: 0.1
    }).addTo(map);
}

function getIconClassForCategory(category) {
    const normalizedCategory = category ? category.toLowerCase() : '';

    if (normalizedCategory.includes('automotive') ||
        normalizedCategory.includes('electric_vehicle')) {
        return 'fa-solid fa-car';
    }

    if (normalizedCategory.includes('eat_and_drink') ||
        normalizedCategory.includes('bar') ||
        normalizedCategory.includes('restaurant') ||
        normalizedCategory.includes('cafe')) {
        return 'fa-solid fa-wine-glass';
    }

    if (normalizedCategory.includes('arts_and_entertainment') ||
        normalizedCategory.includes('cinema') ||
        normalizedCategory.includes('music') ||
        normalizedCategory.includes('internet_cafe')) {
        return 'fa-solid fa-music';
    }

    if (normalizedCategory.includes('beauty_and_spa') ||
        normalizedCategory.includes('barber') ||
        normalizedCategory.includes('beauty_salon')) {
        return 'fa-solid fa-spa';
    }

    if (normalizedCategory.includes('active_life') ||
        normalizedCategory.includes('sports_and_fitness_instruction') ||
        normalizedCategory.includes('sports_and_recreation_venue')) {
        return 'fa-regular fa-futbol';
    }

    if (normalizedCategory.includes('pets') ||
        normalizedCategory.includes('pet_services') ||
        normalizedCategory.includes('veterinarian')) {
        return 'fa-solid fa-paw';
    }

    if (normalizedCategory.includes('education') ||
        normalizedCategory.includes('college_university') ||
        normalizedCategory.includes('educational_services') ||
        normalizedCategory.includes('school')) {
        return 'fa-solid fa-school';
    }

    if (normalizedCategory.includes('financial_service') ||
        normalizedCategory.includes('atms')) {
        return 'fa-solid fa-dollar-sign';
    }

    if (normalizedCategory.includes('retail') ||
        normalizedCategory.includes('beverage_store') ||
        normalizedCategory.includes('drugstore') ||
        normalizedCategory.includes('food') ||
        normalizedCategory.includes('meat_shop') ||
        normalizedCategory.includes('pharmacy') ||
        normalizedCategory.includes('seafood_market') ||
        normalizedCategory.includes('shopping') ||
        normalizedCategory.includes('water_store')) {
        return 'fa-solid fa-bag-shopping';
    }

    if (normalizedCategory.includes('health_and_medical') ||
        normalizedCategory.includes('ambulance') ||
        normalizedCategory.includes('hospital') ||
        normalizedCategory.includes('dentist') ||
        normalizedCategory.includes('doctor') ||
        normalizedCategory.includes('emergency_room') ||
        normalizedCategory.includes('urgent_care')) {
        return 'fa-solid fa-hospital';
    }

    if (normalizedCategory.includes('public_service_and_government') ||
        normalizedCategory.includes('children_hall') ||
        normalizedCategory.includes('civic_center') ||
        normalizedCategory.includes('community_center') ||
        normalizedCategory.includes('community_services') ||
        normalizedCategory.includes('family_service_center') ||
        normalizedCategory.includes('library') ||
        normalizedCategory.includes('police_department') ||
        normalizedCategory.includes('post_office') ||
        normalizedCategory.includes('railway_service')) {
        return 'fa-solid fa-landmark';
    }

    if (normalizedCategory.includes('religious_organization') ||
        normalizedCategory.includes('buddhist_temple') ||
        normalizedCategory.includes('church_cathedral') ||
        normalizedCategory.includes('hindu_temple') ||
        normalizedCategory.includes('mosque') ||
        normalizedCategory.includes('shinto_shrines') ||
        normalizedCategory.includes('sikh_temple') ||
        normalizedCategory.includes('synagogue') ||
        normalizedCategory.includes('temple')) {
        return 'fa-solid fa-person-praying';
    }

    if (normalizedCategory.includes('travel') ||
        normalizedCategory.includes('transportation')) {
        return 'fa-solid fa-plane';
    }

    if (normalizedCategory.includes('professional_services') ||
        normalizedCategory.includes('bike_repair_maintenance') ||
        normalizedCategory.includes('child_care_and_day_care') ||
        normalizedCategory.includes('community_gardens') ||
        normalizedCategory.includes('emergency_service') ||
        normalizedCategory.includes('laundry_services') ||
        normalizedCategory.includes('mailbox_center') ||
        normalizedCategory.includes('package_locker')) {
        return 'fa-solid fa-user-tie';
    }

    if (normalizedCategory.includes('structure_and_geography') ||
        normalizedCategory.includes('public_plaza') ||
        normalizedCategory.includes('attractions_and_activities') ||
        normalizedCategory.includes('park') ||
        normalizedCategory.includes('plaza')) {
        return 'fa-solid fa-monument';
    }

    return null;
}

function drawPOIs(pois) {
    console.log('Iniziando disegnamento POIs. Total:', pois.length);
    
    pois.forEach((poi, index) => {
        try {
            if (poi.location && poi.location.coordinates && poi.location.coordinates.length === 2) {
                // Coordinates are [lat, lon] in this API (not standard GeoJSON)
                const lat = poi.location.coordinates[0];
                const lon = poi.location.coordinates[1];
                
                // Get POI name (could be object or string)
                let poiName = 'POI';
                if (typeof poi.names === 'string') {
                    poiName = poi.names;
                } else if (poi.names && poi.names.primary) {
                    poiName = poi.names.primary;
                }
                
                // Get category and icon
                const primaryCategory = poi.categories?.primary || '';
                const iconClass = getIconClassForCategory(primaryCategory);
                
                let marker;
                
                // Create marker with icon or circle
                if (iconClass) {
                    const icon = L.divIcon({
                        html: `<i class="${iconClass}" style="color: #483d8b; font-size: 22px;"></i>`,
                        className: 'custom-div-icon',
                        iconSize: [30, 30],
                        iconAnchor: [15, 15]
                    });
                    marker = L.marker([lat, lon], { icon });
                } else {
                    marker = L.circleMarker([lat, lon], {
                        radius: 6,
                        fillColor: '#483d8b',
                        color: '#483d8b',
                        weight: 1,
                        opacity: 1,
                        fillOpacity: 0.8
                    });
                }
                
                const popupContent = `
                    <strong>${poiName}</strong><br>
                    Categoria: ${primaryCategory || 'Non specificato'}<br>
                    Distanza: ${poi.distance ? `${Math.round(poi.distance / 1000 * 100) / 100} km` : 'N/A'}
                `;
                
                marker.bindPopup(popupContent);
                marker.addTo(map);
                poiMarkers.push(marker);
                console.log(`POI ${index + 1} disegnato:`, poiName, `(${lat.toFixed(6)}, ${lon.toFixed(6)})`, `- Categoria: ${primaryCategory}`);
            }
        } catch (error) {
            console.error('Errore nel disegnare POI:', error, poi);
        }
    });
    
    console.log(`Totale POIs disegnati: ${poiMarkers.length}`);
}

function showSpiderChartModal(parameters) {
    // Initialize spider chart
    const chartData = [
        {
            className: "metrics",
            axes: [
                { axis: "Proximity", value: Math.min(parameters.proximity_score, 1) },
                { axis: "Density", value: Math.min(parameters.density_score, 1) },
                { axis: "Entropy", value: Math.min(parameters.entropy_score, 1) },
                { axis: "Accessibility", value: Math.min(parameters.poi_accessibility, 1) },
                { axis: "Closeness", value: Math.min(parameters.closeness, 1) }
            ]
        }
    ];
    
    if (spiderChart) {
        spiderChart.updateData(chartData);
    } else {
        spiderChart = new SpiderChart('spider-chart-modal', {
            width: 250,
            height: 250,
            margin: 80,
            maxValue: 1,
            levels: 5,
            color: '#483d8b',
            data: chartData
        });
    }
    
    modalOverlay.classList.add('show');
}

// Modal close button
modalClose.addEventListener('click', () => {
    modalOverlay.classList.remove('show');
});

// Click outside modal to close
modalOverlay.addEventListener('click', (e) => {
    if (e.target === modalOverlay) {
        modalOverlay.classList.remove('show');
    }
});

// View analysis button - reopen modal
btnViewAnalysis.addEventListener('click', () => {
    modalOverlay.classList.add('show');
});

// Next button
btnNext.addEventListener('click', proceedToNextStep);

async function proceedToNextStep() {
    if (!analysisComplete) {
        showError('Per favore, analizza l\'area prima di procedere.');
        return;
    }
    
    if (!selectedStreet || !selectedCoords) {
        showError('Errore: Dati mancanti.');
        return;
    }
    
    btnNext.disabled = true;
    btnNext.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Salvataggio...';
    
    try {
        const response = await fetch('/api/userstudy/street/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                street_name: selectedStreet,
                latitude: selectedCoords.lat,
                longitude: selectedCoords.lon
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            window.location.href = '/userstudy/personal';
        } else {
            showError(`Errore: ${data.detail || 'Non è stato possibile salvare.'}`);
            btnNext.disabled = false;
            btnNext.innerHTML = 'Avanti <i class="bi bi-arrow-right ms-2"></i>';
        }
    } catch (error) {
        console.error('Errore:', error);
        showError('Errore di rete. Prova di nuovo.');
        btnNext.disabled = false;
        btnNext.innerHTML = 'Avanti <i class="bi bi-arrow-right ms-2"></i>';
    }
}

function showError(message) {
    errorMessage.textContent = message;
    errorMessage.classList.add('show');
}
