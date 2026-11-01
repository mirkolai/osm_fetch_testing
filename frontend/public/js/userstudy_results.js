import { renderProgressBarChart } from './components/ProgressBarChart.js';

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
let cityBoundariesLayer = null;
let hasOpenedAnalysisModal = false;

// Crea una nuova sessione e riporta l'utente all'ingresso se questo step viene aperto fuori flusso.
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

if (!currentSessionId) {
    createSessionAndRedirectToWelcome();
    throw new Error('No session ID found');
}

// Configurazione mappa Torino
const TORINO_CENTER = [45.0703, 7.6869];
const TORINO_BOUNDS = [
    [44.99, 7.58],   // Sud-Ovest
    [45.15, 7.78]    // Nord-Est
];
const MAP_MIN_ZOOM = 12;
const MAP_MAX_ZOOM = 18;

// Costruisce l'icona Leaflet per un POI a partire dalla sua categoria principale.
function createPOIIcon(category) {
    const iconClass = getIconClassForCategory(category);
    
    return L.divIcon({
        html: `<i class="${iconClass}" style="color: #483d8b; font-size: 20px;"></i>`,
        className: 'custom-div-icon',
        iconSize: [28, 28],
        iconAnchor: [14, 14]
    });
}

// Inizializza la mappa Leaflet.
// Il vincolo all'area di Torino e mantenuto commentato per poterlo riattivare facilmente.
function initializeMap() {
    map = L.map('map', {
        // maxBounds: TORINO_BOUNDS,
        // maxBoundsViscosity: 1.0,
        minZoom: MAP_MIN_ZOOM,
        maxZoom: MAP_MAX_ZOOM
    }).setView(TORINO_CENTER, 13);

    // Se vuoi ripristinare il lock sull'area di Torino, riattiva questa riga.
    // map.setMaxBounds(TORINO_BOUNDS);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap',
        maxZoom: 19
    }).addTo(map);
}

async function loadCityBoundariesLayer() {
    if (!map) {
        return;
    }

    try {
        const response = await fetch('/api/userstudy/city-boundaries');
        const payload = await response.json();
        if (!response.ok || payload.status !== 'success' || !payload.data || !Array.isArray(payload.data.features)) {
            console.warn('Confini citta non disponibili per la mappa step 5');
            return;
        }

        if (cityBoundariesLayer) {
            map.removeLayer(cityBoundariesLayer);
            cityBoundariesLayer = null;
        }

        cityBoundariesLayer = L.geoJSON(payload.data, {
            style: {
                color: '#f59e0b',
                weight: 2,
                opacity: 1,
                fillColor: '#f59e0b',
                fillOpacity: 0.3
            },
            onEachFeature: (feature, layer) => {
                const cityName = feature?.properties?.city_name || 'Citta senza nome';
                const cityCode = feature?.properties?.city_code || 'N/A';
                layer.bindTooltip(`${cityName} (${cityCode})`, {
                    sticky: true,
                    direction: 'center'
                });
            }
        }).addTo(map);

        cityBoundariesLayer.bringToBack();
    } catch (error) {
        console.error('Errore nel caricamento confini citta step 5:', error);
    }
}

// Disegna l'isocrona supportando sia il formato geometry sia il formato convex_hull del backend.
function drawIsochrone(analysisData, layerGroup, color = '#667eea', opacity = 0.1) {
    if (!analysisData || !analysisData.isochrone) {
        console.log('drawIsochrone: mancano dati isochrone', analysisData);
        return;
    }

    // Sostegno a due formati: { isochrone: { geometry: { type, coordinates } } } e { isochrone: { convex_hull: { coordinates: [...] } } }
    let coordinates = null;
    if (analysisData.isochrone.geometry && analysisData.isochrone.geometry.type === 'Polygon') {
        coordinates = analysisData.isochrone.geometry.coordinates[0];
        console.log('drawIsochrone: formato geometry Polygon rilevato');
    } else if (analysisData.isochrone.convex_hull && analysisData.isochrone.convex_hull.coordinates) {
        coordinates = analysisData.isochrone.convex_hull.coordinates[0];
        console.log('drawIsochrone: formato convex_hull rilevato');
    } else {
        console.log('drawIsochrone: formato isochrone non supportato', analysisData.isochrone);
        return;
    }

    // Controllo contenuto coordinate
    if (!Array.isArray(coordinates) || coordinates.length === 0) {
        console.log('drawIsochrone: coordinate non valide', coordinates);
        return;
    }

    // Normalizza il formato coordinate in [lat, lon] prima di passarlo a Leaflet.
    const polygonCoords = coordinates.map(coord => {
        // Se i punti sono [lon, lat] oppure [lat, lon]
        if (coord.length >= 2) {
            // Controllo se sembra lon/lat (longitude range -180..180)
            if (Math.abs(coord[0]) <= 180 && Math.abs(coord[0]) >= 0 && Math.abs(coord[1]) <= 90) {
                return [coord[1], coord[0]]; // lon/lat -> lat/lon
            }
            return [coord[0], coord[1]]; // già lat/lon
        }
        return null;
    }).filter(p => p);

    if (polygonCoords.length === 0) {
        console.log('drawIsochrone: coordinate convertite non valide', coordinates);
        return;
    }

    console.log('drawIsochrone: disegno poligono con', polygonCoords.length, 'punti');

    const polygon = L.polygon(polygonCoords, {
        color: color,
        fillColor: color,
        fillOpacity: opacity,
        weight: 2
    });
    layerGroup.addLayer(polygon);
}

// Disegna i POI del layer corrente in piccoli batch per non bloccare il rendering della pagina.
function drawPOIs(analysisData, layerGroup) {
    if (!analysisData || !analysisData.pois || analysisData.pois.length === 0) {
        console.log('Nessun POI da disegnare');
        return;
    }
    
    console.log(`Inizio disegno ${analysisData.pois.length} POI`);
    console.log('drawPOIs: analisiData', analysisData.pois);
    const toLatLon = (coords) => {
        if (!Array.isArray(coords) || coords.length !== 2) {
            return null;
        }

        const a = Number(coords[0]);
        const b = Number(coords[1]);
        if (Number.isNaN(a) || Number.isNaN(b)) {
            return null;
        }

        // Standard GeoJSON: [lon, lat]
        if (a >= -180 && a <= 180 && b >= -90 && b <= 90) {
            return [b, a];
        }

        // Legacy fallback: [lat, lon]
        if (a >= -90 && a <= 90 && b >= -180 && b <= 180) {
            return [a, b];
        }

        return null;
    };
    
    // Campiona lungo l'ordinamento per distanza, così il limite include anche i POI più lontani.
    const MAX_POI = 1000;
    const totalPois = analysisData.pois.length;
    const poisToDisplay = totalPois <= MAX_POI
        ? analysisData.pois
        : Array.from(
            { length: MAX_POI },
            (_, index) => analysisData.pois[Math.round(index * (totalPois - 1) / (MAX_POI - 1))],
        );
    console.log(`Mostro ${poisToDisplay.length} POI distribuiti su ${totalPois} raggiungibili`);
    let count = 0;
    
    // Usa batching per non bloccare il thread
    const batchSize = 20;
    let batchIndex = 0;
    
    // Processa una finestra di marker per volta così la UI resta reattiva anche con molti POI.
    function drawBatch() {
        const start = batchIndex * batchSize;
        const end = Math.min(start + batchSize, poisToDisplay.length);
        
        for (let i = start; i < end; i++) {
            const poi = poisToDisplay[i];
            try {
                if (poi.location && poi.location.coordinates && poi.location.coordinates.length === 2) {
                    const latLon = toLatLon(poi.location.coordinates);
                    if (!latLon) {
                        continue;
                    }
                    const [lat, lon] = latLon;
                    
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

// Recupera la sessione corrente per popolare riepilogo e parametri degli endpoint successivi.
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

// Carica l'analisi baseline dello step 3 con parametri standard e tutte le categorie.
async function loadDefaultAnalysis() {
    if (!sessionData || !sessionData.selected_coordinates) return false;
    
    try {
        const coords = sessionData.selected_coordinates;

        // Riusa l'analisi default calcolata nello step 3 se riferita alla stessa sessione e posizione.
        try {
            const cached = JSON.parse(sessionStorage.getItem('default_analysis_cache') || 'null');
            if (
                cached && cached.data && cached.data.status === 'success'
                && cached.session_id === currentSessionId
                && Math.abs(cached.latitude - coords.lat) < 1e-6
                && Math.abs(cached.longitude - coords.lon) < 1e-6
            ) {
                defaultAnalysis = cached.data;
                return true;
            }
        } catch (cacheError) {
            console.warn('Cache analisi default non leggibile:', cacheError);
        }

        const response = await fetch('/api/userstudy/analyze-personalized', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                latitude: coords.lat,
                longitude: coords.lon,
                analysis_type: 'default'
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

// Carica l'analisi personalizzata basata sulle scelte fatte nello step 4.
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
                travel_mode: sessionData.travel_mode || 'walk',
                categories: sessionData.selected_categories || [],
                analysis_type: 'personalized'
            })
        });
        
        const data = await response.json();
        if (response.ok && data.status === 'success') {
            personalizedAnalysis = data;
            console.log('Analisi personalizzata caricata con successo:', personalizedAnalysis);
            return true;
        }
        return false;
    } catch (error) {
        console.error('Errore nel caricamento analisi personalizzata:', error);
        return false;
    }
}

// Trasferisce nella sidebar i dettagli scelti dall'utente negli step precedenti.
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
        const travelModeLabels = {
            walk: 'Passo normale',
            slow_walk: 'Passo lento',
            bike: 'In bicicletta',
        };
        const travelMode = travelModeLabels[sessionData.travel_mode] || travelModeLabels.walk;
        searchParams.innerHTML = `${travelTime} min • ${travelMode}`;
    }
    
    if (categoriesList) {
        if (sessionData.selected_categories && sessionData.selected_categories.length > 0) {
            categoriesList.replaceChildren(...sessionData.selected_categories.map(category => {
                const badge = document.createElement('span');
                badge.className = 'badge bg-primary';
                badge.textContent = window.getCategoryLabelIt(category);
                return badge;
            }));
        }
    }
}

// Prepara i dataset per il radar chart partendo dalle analisi disponibili.
function buildChartDatasets() {

    const hasValidCityAverageMetrics = (params) => {
        console.log('Verifica validità city average metrics:', params);
        if (!params) {
            return false;
        }
        return Number.isFinite(params.proximity_score) &&
            Number.isFinite(params.density_score) &&
            Number.isFinite(params.entropy_score) &&
            Number.isFinite(params.poi_accessibility) &&
            Number.isFinite(params.closeness);
    };

    if (defaultAnalysis && defaultAnalysis.parameters && personalizedAnalysis && personalizedAnalysis.parameters) {
        const defaultParameters = defaultAnalysis.parameters;
        const personalizedParameters = personalizedAnalysis.parameters;
        const cityAverageParameters = hasValidCityAverageMetrics(personalizedAnalysis.city_average_parameters)
            ? personalizedAnalysis.city_average_parameters
            : null;
        const citySamplePersonalizedParameters = hasValidCityAverageMetrics(
            personalizedAnalysis.city_average_parameters,
        ) ? personalizedAnalysis.city_average_parameters : null;
        return { defaultParameters, personalizedParameters, cityAverageParameters, citySamplePersonalizedParameters };
    }

    if (personalizedAnalysis && personalizedAnalysis.parameters) {
        const personalizedParameters = personalizedAnalysis.parameters;
        const cityAverageParameters = hasValidCityAverageMetrics(personalizedAnalysis.city_average_parameters)
            ? personalizedAnalysis.city_average_parameters
            : null;
        const citySamplePersonalizedParameters = hasValidCityAverageMetrics(
            personalizedAnalysis.city_average_parameters,
        ) ? personalizedAnalysis.city_average_parameters : null;
        return {
            defaultParameters: personalizedParameters,
            personalizedParameters,
            cityAverageParameters,
            citySamplePersonalizedParameters,
        };
    }

    return null;
}

function drawSpiderChart(
    elementId,
    defaultParameters,
    personalizedParameters,
    cityAverageParameters = null,
    citySamplePersonalizedParameters = null,
) {
    if (!document.getElementById(elementId)) {
        return;
    }
    renderProgressBarChart(`${elementId}-standard`, defaultParameters, cityAverageParameters, '#483d8b');
    renderProgressBarChart(
        `${elementId}-personalized`,
        personalizedParameters,
        citySamplePersonalizedParameters,
        '#f56565',
    );
    ['step5-standard-legend', 'step5-personalized-legend'].forEach((id) => {
        const legend = document.getElementById(id);
        if (legend) {
            legend.replaceChildren();
        }
    });
}

function renderStep5RadarLegend(containerId, traces) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }

    container.replaceChildren();

    traces.forEach(trace => {
        const row = document.createElement('div');
        row.style.display = 'flex';
        row.style.alignItems = 'center';
        row.style.gap = '8px';

        const swatch = document.createElement('span');
        swatch.style.display = 'inline-block';
        swatch.style.width = '14px';
        swatch.style.height = '14px';
        swatch.style.border = `1px solid ${trace.color}`;
        swatch.style.background = trace.color;
        swatch.style.opacity = String(trace.opacity);

        const label = document.createElement('span');
        label.textContent = trace.label;

        row.appendChild(swatch);
        row.appendChild(label);
        container.appendChild(row);
    });
}

// Coordina il caricamento dello step 5: sessione, analisi, mappa, grafico e stato UI.
async function loadAndDisplay() {
    console.log('=== INIZIO loadAndDisplay ===');
    document.getElementById('loading-spinner').style.display = 'block';
    document.getElementById('info-container').style.display = 'none';

    const btnAnalyze = document.getElementById('btn-analyze');
    const btnNext = document.getElementById('btn-next');
    if (btnAnalyze) {
        btnAnalyze.disabled = true;
    }
    if (btnNext) {
        btnNext.disabled = true;
    }
    
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
        await loadCityBoundariesLayer();
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
            console.log(`  - Default avg: ${defaultAnalysis.pois?.length || 0} POI, parametri:`, defaultAnalysis.city_average_parameters);

        }
        if (personalizedAnalysis) {
            console.log(`  - Personalizzata: ${personalizedAnalysis.pois?.length || 0} POI, parametri:`, personalizedAnalysis.parameters);
            console.log(`  - Personalizzata avg: ${personalizedAnalysis.pois?.length || 0} POI, parametri:`, personalizedAnalysis.city_average_parameters);
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
            console.log('  - POI default non visualizzati (mostriamo solo POI personalizzati)');
        }
        
        if (personalizedAnalysis) {
            console.log('  - Disegnando layer personalizzato...');
            personalizedLayer = L.featureGroup();
            drawIsochrone(personalizedAnalysis, personalizedLayer, '#f56565', 0.15);
            personalizedLayer.addTo(map);
            console.log('  ✓ Isochrone personalizzato disegnato');
            drawPOIs(personalizedAnalysis, personalizedLayer,'#f56565');
            console.log('  ✓ POI personalizzati in coda di disegno');
        }
        
        // Centra la mappa sulle coordinate selezionate, allargando la vista per includere l'isocrona personalizzata
        // (e quindi i POI raggiungibili anche lontani dalla via).
        if (sessionData.selected_coordinates) {
            const coords = sessionData.selected_coordinates;
            console.log('6. Centraggio mappa su:', coords);
            // Pin della via selezionata, sopra i marker dei POI.
            L.marker([coords.lat, coords.lon], {
                icon: L.divIcon({
                    html: '<i class="fa-solid fa-location-dot" style="color: #483d8b; font-size: 32px;"></i>',
                    className: 'custom-div-icon',
                    iconSize: [32, 32],
                    iconAnchor: [16, 32]
                }),
                zIndexOffset: 1000,
                title: sessionData.selected_street || 'Via selezionata'
            }).addTo(map);
            const bounds = L.latLngBounds([[coords.lat, coords.lon]]);
            if (personalizedLayer && personalizedLayer.getBounds().isValid()) {
                bounds.extend(personalizedLayer.getBounds());
            }
            // La sidebar fissa a destra copre la mappa: la escludo dall'area utile.
            const sidebar = document.querySelector('.results-sidebar');
            const sidebarWidth = sidebar ? sidebar.offsetWidth + 40 : 0;
            if (bounds.getNorthEast().equals(bounds.getSouthWest())) {
                map.setView([coords.lat, coords.lon], 14);
            } else {
                map.fitBounds(bounds, {
                    paddingTopLeft: [20, 20],
                    paddingBottomRight: [sidebarWidth, 20],
                    maxZoom: 14,
                });
            }
            console.log('✓ Mappa centrata');
        }
        
        // I dati del grafico sono pronti ma la visualizzazione avviene solo su click del bottone Analizza.
        console.log('7. Dati grafico pronti; in attesa del click su Analizza');
        
        // Mostra i contenitori
        console.log('8. Mostra contenitori...');
        document.getElementById('info-container').style.display = 'block';
        document.getElementById('loading-spinner').style.display = 'none';
        if (btnAnalyze) {
            btnAnalyze.disabled = false;
        }
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

// Mostra la modale con lo spider chart e abilita il pulsante Avanti alla prima apertura.
function showAnalysisModal() {
    const chartDatasets = buildChartDatasets();
    if (!chartDatasets) {
        console.warn('Dati grafico non disponibili');
        return;
    }

    drawSpiderChart(
        'spider-chart-modal',
        chartDatasets.defaultParameters,
        chartDatasets.personalizedParameters,
        chartDatasets.cityAverageParameters || null,
        chartDatasets.citySamplePersonalizedParameters || null,
    );

    const modalOverlay = document.getElementById('modal-overlay');
    if (modalOverlay) {
        modalOverlay.classList.add('show');
    }

    if (!hasOpenedAnalysisModal) {
        hasOpenedAnalysisModal = true;
        const btnNext = document.getElementById('btn-next');
        if (btnNext) {
            btnNext.disabled = false;
        }
    }
}

// Configura apertura e chiusura della finestra di analisi.
function setupAnalysisModal() {
    const btnAnalyze = document.getElementById('btn-analyze');
    const modalOverlay = document.getElementById('modal-overlay');
    const modalClose = document.getElementById('modal-close');

    if (btnAnalyze) {
        btnAnalyze.addEventListener('click', showAnalysisModal);
    }

    if (modalClose) {
        modalClose.addEventListener('click', () => {
            modalOverlay.classList.remove('show');
        });
    }

    if (modalOverlay) {
        modalOverlay.addEventListener('click', (event) => {
            if (event.target === modalOverlay) {
                modalOverlay.classList.remove('show');
            }
        });
    }
}

// Registra sul backend che l'utente ha raggiunto e visto lo step risultati.
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

// Collega il bottone finale dello step 5 al questionario di post-esplorazione.
function setupNextButton() {
    const btnNext = document.getElementById('btn-next');
    if (btnNext) {
        btnNext.disabled = true;
        btnNext.addEventListener('click', () => {
            console.log('Navigating to questionnaire 3');
            window.location.href = '/userstudy/questionnaire3';
        });
    }
}

// Avvia il caricamento
// Controlliamo se il documento è già caricato prima di aspettare l'evento
if (document.readyState === 'loading') {
    // Dom ancora non pronto, aspettiamo
    document.addEventListener('DOMContentLoaded', () => {
        console.log('DOMContentLoaded event');
        setupNextButton();
        setupAnalysisModal();
        loadAndDisplay();
    });
} else {
    // Dom già pronto, eseguiamo subito
    console.log('DOM già pronto, eseguiamo subito');
    setupNextButton();
    setupAnalysisModal();
    loadAndDisplay();
}
