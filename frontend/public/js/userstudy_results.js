/**
 * Modulo per Passo 5/7 - Esplora i Risultati
 * Mostra mappa con POI e isochrone, confronta dati personalizzati vs default
 */

let currentSessionId = sessionStorage.getItem('session_id');
let sessionData = null;
let defaultAnalysis = null;
let personalizedAnalysis = null;
let map = null;
let defaultLayer = null;
let personalizedLayer = null;
let defaultChart = null;
let personalizedChart = null;

if (!currentSessionId) {
    alert('Errore: Session non trovata.');
    window.location.href = '/userstudy/welcome';
}

// Configurazione mappa Torino
const TORINO_CENTER = [45.0703, 7.6869];
const TORINO_BOUNDS = [
    [44.99, 7.58],   // Sud-Ovest
    [45.15, 7.78]    // Nord-Est
];

// FontAwesome icon mapping per categorie (aggiornato)
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

    return 'fa-solid fa-location-dot';
}

// Ottieni il colore per una categoria - RIMOSSO (non più usato)

// Crea un divIcon con FontAwesome
function createPOIIcon(category) {
    const iconClass = getIconClassForCategory(category);
    
    return L.divIcon({
        html: `<i class="${iconClass}" style="color: #483d8b; font-size: 20px;"></i>`,
        className: 'custom-div-icon',
        iconSize: [28, 28],
        iconAnchor: [14, 14]
    });
}

// Inizializza la mappa
function initializeMap() {
    map = L.map('map', {
        maxBounds: TORINO_BOUNDS,
        maxBoundsViscosity: 1.0,
        minZoom: 12,
        maxZoom: 18
    }).setView(TORINO_CENTER, 13);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap',
        maxZoom: 19
    }).addTo(map);
}

// Disegna isochrone sulla mappa
function drawIsochrone(analysisData, layerGroup, color = '#667eea', opacity = 0.1) {
    if (!analysisData || !analysisData.isochrone || !analysisData.isochrone.geometry) {
        console.log('drawIsochrone: mancano dati isochrone', analysisData);
        return;
    }
    
    const geometry = analysisData.isochrone.geometry;
    console.log('drawIsochrone geometry type:', geometry.type);
    console.log('drawIsochrone geometry:', geometry);
    
    if (geometry.type === 'Polygon') {
        console.log('Numero di coordinate nel poligono:', geometry.coordinates[0].length);
        
        // Le coordinate in GeoJSON sono [lon, lat], dobbiamo convertirle a [lat, lon] per Leaflet
        const coordinates = geometry.coordinates[0].map(coord => {
            console.log('Coordinata originale:', coord, '-> convertita:', [coord[1], coord[0]]);
            return [coord[1], coord[0]];
        });
        
        console.log('Creando poligono con', coordinates.length, 'punti - primo:', coordinates[0], 'ultimo:', coordinates[coordinates.length-1]);
        
        const polygon = L.polygon(coordinates, {
            color: color,
            fillColor: color,
            fillOpacity: opacity,
            weight: 2
        });
        
        console.log('Poligono creato, lo aggiungo al layer...');
        layerGroup.addLayer(polygon);
        console.log('✓ Poligono aggiunto al layer');
    } else {
        console.log('drawIsochrone: geometry type non è Polygon:', geometry.type);
    }
}

// Disegna POI sulla mappa
function drawPOIs(analysisData, layerGroup) {
    if (!analysisData || !analysisData.pois || analysisData.pois.length === 0) {
        console.log('Nessun POI da disegnare');
        return;
    }
    
    console.log(`Inizio disegno ${analysisData.pois.length} POI`);
    
    // Limita a 100 POI per evitare blocchi
    const poisToDisplay = analysisData.pois.slice(0, 100);
    let count = 0;
    
    // Usa batching per non bloccare il thread
    const batchSize = 20;
    let batchIndex = 0;
    
    function drawBatch() {
        const start = batchIndex * batchSize;
        const end = Math.min(start + batchSize, poisToDisplay.length);
        
        for (let i = start; i < end; i++) {
            const poi = poisToDisplay[i];
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
                    
                    const marker = L.marker([lat, lon], {
                        icon: createPOIIcon(primaryCategory)
                    });
                    
                    marker.bindPopup(`
                        <div style="font-size: 12px;">
                            <strong>${poiName}</strong><br>
                            <small>${primaryCategory.replace(/_/g, ' ')}</small><br>
                            <small style="color: #999;">Lat: ${lat.toFixed(4)}, Lon: ${lon.toFixed(4)}</small>
                        </div>
                    `);
                    
                    layerGroup.addLayer(marker);
                    count++;
                }
            } catch (error) {
                console.error('Errore nel disegno POI:', error, poi);
            }
        }
        
        // Se ci sono altri batch, disegna il prossimo dopo un breve delay
        if (end < poisToDisplay.length) {
            batchIndex++;
            setTimeout(drawBatch, 50);
        } else {
            console.log(`Disegnati ${count} POI totali`);
        }
    }
    
    drawBatch();
}

// Carica i dati della sessione
async function loadSessionData() {
    try {
        const response = await fetch('/api/userstudy/session/get', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentSessionId })
        });
        
        const data = await response.json();
        if (response.ok && data.status === 'success') {
            sessionData = data.session;
            return true;
        }
        return false;
    } catch (error) {
        console.error('Errore nel caricamento sessione:', error);
        return false;
    }
}

// Carica analisi default (15 min, walking, tutte le categorie)
async function loadDefaultAnalysis() {
    if (!sessionData || !sessionData.selected_coordinates) return false;
    
    try {
        const coords = sessionData.selected_coordinates;
        const response = await fetch('/api/userstudy/analyze-area', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                latitude: coords.lat,
                longitude: coords.lon
            })
        });
        
        const data = await response.json();
        if (response.ok && data.status === 'success') {
            defaultAnalysis = data;
            return true;
        }
        return false;
    } catch (error) {
        console.error('Errore nel caricamento analisi default:', error);
        return false;
    }
}

// Carica analisi personalizzata con i dati dell'utente
async function loadPersonalizedAnalysis() {
    if (!sessionData || !sessionData.selected_coordinates) return false;
    
    try {
        const coords = sessionData.selected_coordinates;
        const response = await fetch('/api/userstudy/analyze-personalized', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                latitude: coords.lat,
                longitude: coords.lon,
                travel_time: sessionData.travel_time || 15,
                travel_mode: sessionData.travel_mode || 'walking',
                categories: sessionData.selected_categories || []
            })
        });
        
        const data = await response.json();
        if (response.ok && data.status === 'success') {
            personalizedAnalysis = data;
            return true;
        }
        return false;
    } catch (error) {
        console.error('Errore nel caricamento analisi personalizzata:', error);
        return false;
    }
}

// Visualizza le informazioni della sessione
function displaySessionInfo() {
    if (!sessionData) return;
    
    const streetName = document.getElementById('street-name');
    const searchParams = document.getElementById('search-params');
    const categoriesList = document.getElementById('categories-list');
    
    if (streetName) {
        streetName.textContent = sessionData.selected_street || 'Non selezionata';
    }
    
    if (searchParams) {
        const travelTime = sessionData.travel_time || 15;
        const travelMode = sessionData.travel_mode === 'walking_cane' ? 'Con bastone' : 'A piedi';
        searchParams.innerHTML = `${travelTime} min • ${travelMode}`;
    }
    
    if (categoriesList) {
        if (sessionData.selected_categories && sessionData.selected_categories.length > 0) {
            categoriesList.innerHTML = sessionData.selected_categories
                .map(cat => `<span class="badge bg-primary">${cat}</span>`)
                .join('');
        }
    }
}

// Disegna spider chart
function drawSpiderChart(elementId, data) {
    const svgWidth = 280;
    const svgHeight = 280;
    
    const container = document.getElementById(elementId);
    if (!container) return;
    
    container.innerHTML = '';
    
    const svg = d3.select(`#${elementId}`)
        .append('svg')
        .attr('width', svgWidth)
        .attr('height', svgHeight);
    
    const g = svg.append('g')
        .attr('transform', `translate(${svgWidth / 2}, ${svgHeight / 2})`);
    
    const radius = 80;
    const angleSlice = Math.PI * 2 / Object.keys(data).length;
    
    // Disegna i raggi
    Object.keys(data).forEach((key, i) => {
        const angle = angleSlice * i - Math.PI / 2;
        const x = radius * Math.cos(angle);
        const y = radius * Math.sin(angle);
        
        g.append('line')
            .attr('x1', 0).attr('y1', 0)
            .attr('x2', x).attr('y2', y)
            .style('stroke', '#ddd').style('stroke-width', 1);
        
        g.append('text')
            .attr('x', x * 1.2).attr('y', y * 1.2)
            .attr('text-anchor', 'middle')
            .style('font-size', '11px')
            .style('fill', '#666')
            .text(key);
    });
    
    // Disegna i livelli circolari
    for (let i = 1; i <= 5; i++) {
        const r = (radius / 5) * i;
        g.append('circle')
            .attr('cx', 0).attr('cy', 0).attr('r', r)
            .style('fill', 'none')
            .style('stroke', '#e0e0e0')
            .style('stroke-width', 0.5);
    }
    
    // Disegna il poligono dei dati
    const points = Object.values(data).map((value, i) => {
        const angle = angleSlice * i - Math.PI / 2;
        const r = (radius / 5) * value;
        return [r * Math.cos(angle), r * Math.sin(angle)];
    });
    
    const line = d3.line();
    g.append('path')
        .attr('d', line(points) + 'Z')
        .style('fill', '#667eea')
        .style('fill-opacity', 0.3)
        .style('stroke', '#667eea')
        .style('stroke-width', 2);
}

// Carica i dati a default (15 min, walking, tutte le categorie) e personalizati
async function loadAndDisplay() {
    console.log('=== INIZIO loadAndDisplay ===');
    document.getElementById('loading-spinner').style.display = 'block';
    document.getElementById('info-container').style.display = 'none';
    document.getElementById('chart-container').style.display = 'none';
    
    try {
        // Carica i dati di sessione
        console.log('1. Caricamento dati sessione...');
        if (!await loadSessionData()) {
            console.error('Errore nel caricamento della sessione');
            document.getElementById('loading-spinner').style.display = 'none';
            return;
        }
        console.log('✓ Sessione caricata', sessionData);
        
        // Inizializza la mappa
        console.log('2. Inizializzazione mappa...');
        initializeMap();
        console.log('✓ Mappa inizializzata');
        
        // Carica entrambe le analisi in parallelo
        console.log('3. Caricamento analisi in parallelo...');
        const [defaultOk, personalizedOk] = await Promise.all([
            loadDefaultAnalysis(),
            loadPersonalizedAnalysis()
        ]);
        
        console.log(`✓ Analisi caricate - Default: ${defaultOk}, Personalizzata: ${personalizedOk}`);
        if (defaultAnalysis) {
            console.log(`  - Default: ${defaultAnalysis.pois?.length || 0} POI, parametri:`, defaultAnalysis.parameters);
        }
        if (personalizedAnalysis) {
            console.log(`  - Personalizzata: ${personalizedAnalysis.pois?.length || 0} POI, parametri:`, personalizedAnalysis.parameters);
        }
        
        // Visualizza le informazioni della sessione
        console.log('4. Visualizzazione info sessione...');
        displaySessionInfo();
        console.log('✓ Info sessione visualizzate');
        
        // Disegna i dati sulla mappa
        console.log('5. Disegno layer sulla mappa...');
        if (defaultAnalysis) {
            console.log('  - Disegnando layer default...');
            defaultLayer = L.featureGroup();
            drawIsochrone(defaultAnalysis, defaultLayer, '#999999', 0.05);
            defaultLayer.addTo(map);
            console.log('  ✓ Isochrone default disegnato');
            drawPOIs(defaultAnalysis, defaultLayer);
            console.log('  ✓ POI default in coda di disegno');
        }
        
        if (personalizedAnalysis) {
            console.log('  - Disegnando layer personalizzato...');
            personalizedLayer = L.featureGroup();
            drawIsochrone(personalizedAnalysis, personalizedLayer, '#667eea', 0.15);
            personalizedLayer.addTo(map);
            console.log('  ✓ Isochrone personalizzato disegnato');
            drawPOIs(personalizedAnalysis, personalizedLayer);
            console.log('  ✓ POI personalizzati in coda di disegno');
        }
        
        // Centra la mappa sulle coordinate selezionate
        if (sessionData.selected_coordinates) {
            const coords = sessionData.selected_coordinates;
            console.log('6. Centraggio mappa su:', coords);
            map.setView([coords.lat, coords.lon], 14);
            console.log('✓ Mappa centrata');
        }
        
        // Disegna i spider chart
        console.log('7. Disegno spider chart...');
        if (defaultAnalysis && defaultAnalysis.parameters) {
            const defaultData = {
                'Prossimità': defaultAnalysis.parameters.proximity_score,
                'Densità': defaultAnalysis.parameters.density_score,
                'Varietà': defaultAnalysis.parameters.entropy_score,
                'Accessibilità': defaultAnalysis.parameters.poi_accessibility,
                'Connettività': defaultAnalysis.parameters.closeness
            };
            console.log('  - Disegnando chart default...');
            drawSpiderChart('spider-chart-default', defaultData);
            console.log('  ✓ Chart default disegnato');
        }
        
        if (personalizedAnalysis && personalizedAnalysis.parameters) {
            const personalizedData = {
                'Prossimità': personalizedAnalysis.parameters.proximity_score,
                'Densità': personalizedAnalysis.parameters.density_score,
                'Varietà': personalizedAnalysis.parameters.entropy_score,
                'Accessibilità': personalizedAnalysis.parameters.poi_accessibility,
                'Connettività': personalizedAnalysis.parameters.closeness
            };
            console.log('  - Disegnando chart personalizzato...');
            drawSpiderChart('spider-chart-personalized', personalizedData);
            console.log('  ✓ Chart personalizzato disegnato');
        }
        
        // Mostra i contenitori
        console.log('8. Mostra contenitori...');
        document.getElementById('info-container').style.display = 'block';
        document.getElementById('chart-container').style.display = 'block';
        document.getElementById('loading-spinner').style.display = 'none';
        console.log('✓ Contenitori visibili');
        
        // Registra la visualizzazione dei risultati
        console.log('9. Registrazione visualizzazione risultati...');
        markResultsViewed();
        
        console.log('=== FINE loadAndDisplay (SUCCESSO) ===');
    } catch (error) {
        console.error('=== ERRORE IN loadAndDisplay ===', error);
        document.getElementById('loading-spinner').style.display = 'none';
    }
}

// Registra la visualizzazione dei risultati
async function markResultsViewed() {
    try {
        await fetch('/api/userstudy/results/viewed', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentSessionId })
        });
    } catch (error) {
        console.error('Errore nel segnare i risultati visti:', error);
    }
}

// Avvia il caricamento
// Controlliamo se il documento è già caricato prima di aspettare l'evento
if (document.readyState === 'loading') {
    // Dom ancora non pronto, aspettiamo
    document.addEventListener('DOMContentLoaded', () => {
        console.log('DOMContentLoaded event');
        loadAndDisplay();
    });
} else {
    // Dom già pronto, eseguiamo subito
    console.log('DOM già pronto, eseguiamo subito');
    loadAndDisplay();
}
