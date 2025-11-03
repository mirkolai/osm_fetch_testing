import { ApiService } from './services/apiService.js';
import { SpiderChart } from './components/SpiderChart.js';
import { ParallelCoordinates } from './components/ParallelCoordinates.js';
import { servicesList } from './config/servicesList.js';

// delay tra le chiamate
function debounce(func, delay) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            func.apply(this, args);
        }, delay);
    };
}

document.addEventListener('DOMContentLoaded', () => { // aspetta che la pagina sia caricata
    const elements = {
        searchInput: document.getElementById('city-search'), //barra indirizzo
        suggestionsList: document.getElementById('suggestions'), //indirizzi suggeriti
        selectedAddressDiv: document.querySelector('.selected-address'), //mostra l'indirizzo selezionato
        searchButton: document.getElementById('search-btn'), //bottone research
        resetButton: document.getElementById('reset-btn'), //bottone reset
        compareButton: document.getElementById('compare-btn') //bottone compare
    };

    let selectedCoordinates = null; //coordinate selezionate
    let selectedCityName = null; //nome della città selezionata
    let neighbourhoodLayers = []; //zone colorate
    let selectedNeighbourhoods = []; //quartieri selezionati
    let nodeMarkers = []; // pallini 
    let spiderCharts = [];
    let parallelCharts = [];
    let neighbourhoodColors = {}; // mappa dei colori per quartiere
    let currentChartType = 'spider'; // 'spider' o 'parallel'

    initializeSpiderCharts();
    initializeParallelCharts();

    function initializeSpiderCharts() {

        try {
            if (typeof d3 === 'undefined') {
                console.error('D3.js error');
                return;
            }

            // dati di default per il spider chart
            const defaultData = [
                {
                    className: "metrics-quartiere1", // classe per il quartiere 1
                    axes: [ //impostati tutti al valore di default
                        { axis: "Proximity", value: 0.2 },
                        { axis: "Density", value: 0.2 },
                        { axis: "Entropy", value: 0.2 },
                        { axis: "Accessibility", value: 0.2 },
                        { axis: "Closeness", value: 0.2 }
                    ]
                },
                {
                    className: "metrics-quartiere2", // classe per il quartiere 2
                    axes: [
                        { axis: "Proximity", value: 0.2 },
                        { axis: "Density", value: 0.2 },
                        { axis: "Entropy", value: 0.2 },
                        { axis: "Accessibility", value: 0.2 },
                        { axis: "Closeness", value: 0.2 }
                    ]
                }
            ];

            const chart1 = document.getElementById('spider-chart-1'); // contenitore spiderchart
            if (chart1) { //se trova il contenitore
                chart1.style.display = 'flex';
                
                // crea spider chart
                const spiderChart1 = new SpiderChart('spider-chart-1', {
                    width: 200,
                    height: 200,
                    margin: 100,
                    maxValue: 1,
                    levels: 5,
                    labelFactor: 1.3, //distanza etichette dal centro
                    color: d3.scaleOrdinal(['#483d8b', '#ff6b6b']), // Due colori diversi
                    data: defaultData
                });

                spiderCharts.push({ id: 'chart1', chart: spiderChart1, container: chart1 }); // aggiunge lo spider chart all'array
            }

            // prendi e nascondi il secondo chart
            const chart2 = document.getElementById('spider-chart-2');
            if (chart2) {
                chart2.style.display = 'none';
            }

        } catch (error) {
            console.error('Error initializing spider chart:', error);
        }
    }

    function initializeParallelCharts() {
        try {
            if (typeof d3 === 'undefined') {
                console.error('D3.js error');
                return;
            }

            // dati di default per il parallel coordinates
            const defaultData = [
                {
                    className: "metrics-quartiere1",
                    axes: [
                        { axis: "Proximity", value: 0.2 },
                        { axis: "Density", value: 0.2 },
                        { axis: "Entropy", value: 0.2 },
                        { axis: "Accessibility", value: 0.2 },
                        { axis: "Closeness", value: 0.2 }
                    ]
                },
                {
                    className: "metrics-quartiere2",
                    axes: [
                        { axis: "Proximity", value: 0.2 },
                        { axis: "Density", value: 0.2 },
                        { axis: "Entropy", value: 0.2 },
                        { axis: "Accessibility", value: 0.2 },
                        { axis: "Closeness", value: 0.2 }
                    ]
                }
            ];

            const chart1 = document.getElementById('parallel-coordinates-1');
            if (chart1) {
                chart1.style.display = 'none'; // nascondi il parallel chart all'avvio
                
                // crea parallel coordinates
                const parallelChart1 = new ParallelCoordinates('parallel-coordinates-1', {
                    width: 300,
                    height: 250,
                    margin: { top: 70, right: 0, bottom: 10, left: 0 },
                    maxValue: 1,
                    color: d3.scaleOrdinal(['#483d8b', '#ff6b6b']),
                    data: defaultData
                });

                parallelCharts.push({ id: 'chart1', chart: parallelChart1, container: chart1 });
            }

        } catch (error) {
            console.error('Error initializing parallel coordinates:', error);
        }
    }

    function setupEventListeners() {
        // setup sidebar e bottone per nasconderla
        function setupSidebarToggle() {
            const sidebar = document.querySelector('.overlay-sidebar');
            const toggleBtn = document.getElementById('sidebar-toggle-btn');
            const toggleIcon = toggleBtn.querySelector('i'); // icona del bottone "<"

            toggleBtn.addEventListener('click', () => {
                sidebar.classList.toggle('collapsed'); //se ha la classe la toglie, se non la ha la aggiunge

                if (sidebar.classList.contains('collapsed')) {
                    toggleIcon.classList.remove('bi-chevron-left'); 
                    toggleIcon.classList.add('bi-chevron-right');
                } else {
                    toggleIcon.classList.remove('bi-chevron-right');
                    toggleIcon.classList.add('bi-chevron-left');
                }
            });
        }

        setupSidebarToggle();
        
        // bottone per cambiare il tipo di chart
        const swapButton = document.getElementById('chart-swap-btn');
        if (swapButton) {
            swapButton.addEventListener('click', toggleChartType);
        }
        
        elements.searchInput.addEventListener('input', debounce(handleSearchInput, 1500)); //quando inserisco qualcosa nella barra indirizzo, chiamo la funzione handleSearchInput
        // funzioni da chiamare quando clicco sui bottoni
        elements.searchButton.addEventListener('click', handleSearch); 
        elements.resetButton.addEventListener('click', handleReset); 
        elements.compareButton.addEventListener('click', handleCompare);
        document.addEventListener('click', handleOutsideClick); //quando clicco fuori dalla barra indirizzo (ovunque)
    }

    function toggleChartType() {
        const spiderContainer = document.getElementById('spider-chart-1');
        const parallelContainer = document.getElementById('parallel-coordinates-1');
        
        if (currentChartType === 'spider') {
            // passa al parallel coordinates
            spiderContainer.style.display = 'none';
            parallelContainer.style.display = 'flex';
            currentChartType = 'parallel';
        } else {
            // passa al spider chart
            parallelContainer.style.display = 'none';
            spiderContainer.style.display = 'flex';
            currentChartType = 'spider';
        }
    }

    async function getAuthPreferences() {
        try {
            const token = localStorage.getItem('access_token');
            if (!token) return null;
            const res = await fetch('/api/auth/preferences', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            if (!res.ok) return null;
            return await res.json();
        } catch (error) {
            console.error('Error fetching auth preferences:', error);
            return null;
        }
    }

    function handleReset() {
        elements.searchInput.value = '';
        selectedCoordinates = null;
        selectedCityName = null;
        selectedNeighbourhoods = [];
        elements.selectedAddressDiv.innerHTML = '';
        elements.suggestionsList.innerHTML = '';
        
        // cancello il progress counter
        document.querySelectorAll('[id^="progress-"]').forEach(el => el.textContent = '');
        
        updateSelectedNeighbourhoodsDisplay();

        // puliamo i quartieri i nodi e gli spider chart
        clearNeighbourhoodLayers();
        clearNodeMarkers();
        clearSpiderCharts();
        
        // puliamo le variabili globali
        window.currentNeighbourhoods = null;
        window.neighbourhoodLayers = {};
        neighbourhoodColors = {};

        if (window.map) {
            window.map.setView([45.0703, 7.6869], 13);
        }
    }

    async function handleCompare() {
        if (selectedNeighbourhoods.length === 0) {
            alert('Per favore, seleziona almeno un quartiere per confrontare');
            return;
        }

        if (selectedNeighbourhoods.length !== 2) {
            alert('Devi selezionare esattamente 2 quartieri per confrontarli');
            return;
        }
      
        // Tutte le categorie disponibili prese da servicesList
        const allCategories = Array.from(new Set(
            Object.values(servicesList)
                .flatMap(group => (group?.services || []).map(s => s.id))
        ));

        // Preferenze utente se autenticato, altrimenti default
        const defaults = { minutes: 15, velocity: 5, categories: allCategories };
        const prefs = await getAuthPreferences();
        const minutes = Number.isFinite(prefs?.min) ? prefs.min : defaults.minutes;
        const velocity = Number.isFinite(prefs?.vel) ? prefs.vel : defaults.velocity;
        const categories = Array.isArray(prefs?.categories) && prefs.categories.length > 0 ? prefs.categories : defaults.categories;

        // Puliamo i marcatori esistenti prima di iniziare
        clearNodeMarkers();
        clearSpiderCharts();
        document.querySelectorAll('[id^="progress-"]').forEach(el => el.textContent = '');
        //non serve pulire le neighbourhoodLayers perchè selezionando un altro quartiere già si pulisce il layer precedente

        // Per ogni quartiere selezionato... (per ora solo 2)
        for (const neighbourhood of selectedNeighbourhoods) {
            console.log(`\n=== Processing Neighbourhood ${neighbourhood.id} ===`);
            
            // raccoglie le metriche di tutti i nodi del quartiere per poter fare la media
            const neighbourhoodMetrics = {
                proximity: [],
                density: [],
                entropy: [],
                accessibility: [],
                closeness: []
            };
            
            let nodeCoordinates = null;
            
             // Estrai le coordinate del quartiere
            if (neighbourhood.coordinates && neighbourhood.coordinates.length > 0 && neighbourhood.coordinates[0]) {
                nodeCoordinates = neighbourhood.coordinates[0]; //tutte le coordinate dei nodi di quel quartiere
                console.log(`Found ${nodeCoordinates.length} nodes in neighbourhood ${neighbourhood.id}`);
                
                // max nodi: 25
                const maxNodes = Math.min(nodeCoordinates.length, 25);
                
                // inizializzo il progress counter
                const progressElement = document.getElementById(`progress-${neighbourhood.id}`);
                if (progressElement) {
                    progressElement.textContent = `0/${maxNodes}`;
                }
                
                // per ogni nodo del quartiere
                for (let i = 0; i < maxNodes; i++) {
                    const nodeCoords = nodeCoordinates[i];
                    console.log(`\n--- Processing Node ${i + 1}/${maxNodes} ---`);
                    console.log(`Coordinates: [${nodeCoords[0]}, ${nodeCoords[1]}]`);
                    
                    // Aggiungi un marker sulla mappa per questo nodo
                    let marker = null;
                    if (window.map) {
                        marker = L.circleMarker([nodeCoords[0], nodeCoords[1]], {
                            radius: 6,
                            fillColor: '#ff7800',
                            color: '#000',
                            weight: 2,
                            opacity: 1,
                            fillOpacity: 0.8
                        }).addTo(window.map);
                        
                        // Aggiungi popup con informazioni del nodo
                        marker.bindPopup(`
                            <div class="popup-content">
                                <h6 class="popup-title">Nodo Quartiere ${neighbourhood.id}</h6>
                                <p class="popup-info"><strong>Posizione:</strong> ${i + 1}/${maxNodes}</p>
                                <p class="popup-info"><strong>Coordinate:</strong> ${nodeCoords[0].toFixed(6)}, ${nodeCoords[1].toFixed(6)}</p>
                                <p class="popup-info"><strong>Stato:</strong> In elaborazione...</p>
                            </div>
                        `);
                        
                        nodeMarkers.push(marker); //aggiunge il marker al array dei marker
                    }
                    
                    try {
                        // Chiama ApiService.runSearch per questo nodo
                        const results = await ApiService.runSearch(
                            [nodeCoords[0], nodeCoords[1]], // coordinates [lat, lon]
                            minutes, // minutes
                            velocity,  // velocity
                            categories // categorie da preferenze o default
                        );
                        
                        const metrics = results.parameters;
                        
                        // Raccogli i risultati per il calcolo della media
                        if (metrics.proximity_score !== null && metrics.proximity_score !== undefined) {
                            neighbourhoodMetrics.proximity.push(metrics.proximity_score);
                        }
                        if (metrics.density_score !== null && metrics.density_score !== undefined) {
                            neighbourhoodMetrics.density.push(metrics.density_score);
                        }
                        if (metrics.entropy_score !== null && metrics.entropy_score !== undefined) {
                            neighbourhoodMetrics.entropy.push(metrics.entropy_score);
                        }
                        if (metrics.poi_accessibility !== null && metrics.poi_accessibility !== undefined) {
                            neighbourhoodMetrics.accessibility.push(metrics.poi_accessibility);
                        }
                        if (metrics.closeness !== null && metrics.closeness !== undefined) {
                            neighbourhoodMetrics.closeness.push(metrics.closeness);
                        }
                        
                        // Aggiorna il marker con i risultati
                        if (marker) {
                            marker.setPopupContent(`
                                <div class="popup-content">
                                    <h6 class="popup-title">Nodo Quartiere ${neighbourhood.id}</h6>
                                    <p class="popup-info"><strong>Posizione:</strong> ${i + 1}/${maxNodes}</p>
                                    <p class="popup-info"><strong>Coordinate:</strong> ${nodeCoords[0].toFixed(6)}, ${nodeCoords[1].toFixed(6)}</p>
                                    <p class="popup-info"><strong>Proximity:</strong> ${metrics.proximity_score || 'N/A'}</p>
                                    <p class="popup-info"><strong>Density:</strong> ${metrics.density_score || 'N/A'}</p>
                                    <p class="popup-info"><strong>Entropy:</strong> ${metrics.entropy_score || 'N/A'}</p>
                                    <p class="popup-info"><strong>Accessibility:</strong> ${metrics.poi_accessibility || 'N/A'}</p>
                                    <p class="popup-info"><strong>Closeness:</strong> ${metrics.closeness || 'N/A'}</p>
                                </div>
                            `);
                            
                            // Cambia colore del marker per indicare completamento
                            // Usa il colore del quartiere se disponibile, altrimenti usa il verde
                            const neighbourhoodColor = neighbourhoodColors[neighbourhood.id] || '#28a745';
                            marker.setStyle({
                                fillColor: neighbourhoodColor,
                                color: '#000', // bordo nero 
                                weight: 1
                            });
                        }
                        
                    } catch (error) {
                        console.error(`Error processing node ${i + 1}:`, error);
                        
                        // Aggiorna il marker per indicare errore
                        if (marker) {
                            marker.setPopupContent(`
                                <div class="popup-content">
                                    <h6 class="popup-title">Nodo Quartiere ${neighbourhood.id}</h6>
                                    <p class="popup-info"><strong>Posizione:</strong> ${i + 1}/${maxNodes}</p>
                                    <p class="popup-info"><strong>Coordinate:</strong> ${nodeCoords[0].toFixed(6)}, ${nodeCoords[1].toFixed(6)}</p>
                                    <p class="popup-info"><strong>Stato:</strong> <span class="error-message">Errore nell'elaborazione</span></p>
                                </div>
                            `);
                            
                            marker.setStyle({
                                fillColor: '#dc3545',
                                color: '#721c24'
                            });
                        }
                    }
                    
                    // aggiorno il progress counter dopo ogni nodo
                    const progressElement = document.getElementById(`progress-${neighbourhood.id}`);
                    if (progressElement) {
                        progressElement.textContent = `${i + 1}/${maxNodes}`;
                    }
                }
            } else {
                console.log(`No valid coordinates found for neighbourhood ${neighbourhood.id}`);
            }
            
            // otteniamo i valori del quartiere con la media dei valori di ogni nodo
            const averages = {
                proximity: neighbourhoodMetrics.proximity.length > 0 ? 
                    (neighbourhoodMetrics.proximity.reduce((sum, val) => sum + val, 0) / neighbourhoodMetrics.proximity.length).toFixed(4) : 'N/A',
                density: neighbourhoodMetrics.density.length > 0 ? 
                    (neighbourhoodMetrics.density.reduce((sum, val) => sum + val, 0) / neighbourhoodMetrics.density.length).toFixed(4) : 'N/A',
                entropy: neighbourhoodMetrics.entropy.length > 0 ? 
                    (neighbourhoodMetrics.entropy.reduce((sum, val) => sum + val, 0) / neighbourhoodMetrics.entropy.length).toFixed(4) : 'N/A',
                accessibility: neighbourhoodMetrics.accessibility.length > 0 ? 
                    (neighbourhoodMetrics.accessibility.reduce((sum, val) => sum + val, 0) / neighbourhoodMetrics.accessibility.length).toFixed(4) : 'N/A',
                closeness: neighbourhoodMetrics.closeness.length > 0 ? 
                    (neighbourhoodMetrics.closeness.reduce((sum, val) => sum + val, 0) / neighbourhoodMetrics.closeness.length).toFixed(4) : 'N/A'
            };
            
            console.log(`VALORI QUARTIERE ${neighbourhood.id}:`);
            console.log(`   Proximity: ${averages.proximity} (da ${neighbourhoodMetrics.proximity.length} nodi)`);
            console.log(`   Density: ${averages.density} (da ${neighbourhoodMetrics.density.length} nodi)`);
            console.log(`   Entropy: ${averages.entropy} (da ${neighbourhoodMetrics.entropy.length} nodi)`);
            console.log(`   Accessibility: ${averages.accessibility} (da ${neighbourhoodMetrics.accessibility.length} nodi)`);
            console.log(`   Closeness: ${averages.closeness} (da ${neighbourhoodMetrics.closeness.length} nodi)`);
            
            // Aggiorna i chart con i dati di questo quartiere
            initializeSpiderChart('spider-chart-1', neighbourhood.id, averages);
            initializeParallelChart('parallel-coordinates-1', neighbourhood.id, averages);
        }

        // assicurati che il chart visibile sia quello corretto
        const spiderContainer = document.getElementById('spider-chart-1');
        const parallelContainer = document.getElementById('parallel-coordinates-1');
        if (currentChartType === 'spider') {
            spiderContainer.style.display = 'flex';
            parallelContainer.style.display = 'none';
        } else {
            spiderContainer.style.display = 'none';
            parallelContainer.style.display = 'flex';
        }
        
        // Stampa un riassunto finale del confronto
        console.log(`\n🏆 RIASSUNTO FINALE - CONFRONTO TRA ${selectedNeighbourhoods.length} QUARTIERI:`);
        console.log(`Quartieri analizzati: ${selectedNeighbourhoods.map(n => n.id).join(', ')}`);
        console.log(`Totale nodi processati: ${nodeMarkers.length}`);
    }

    function clearNeighbourhoodLayers() {
        // rimuoviamo tutti i contorni dei quartieri dalla mappa
        neighbourhoodLayers.forEach(layer => {
            if (window.map && window.map.hasLayer(layer)) {
                window.map.removeLayer(layer);
            }
        });
        neighbourhoodLayers = [];
    }

    function clearNodeMarkers() {
        // rimuoviamo tutti i marcatori dei nodi dalla mappa
        nodeMarkers.forEach(marker => {
            if (window.map && window.map.hasLayer(marker)) {
                window.map.removeLayer(marker);
            }
        });
        nodeMarkers = [];
    }

    function clearSpiderCharts() {
        // valori di default
        const defaultData = [
            {
                className: "metrics-quartiere1",
                axes: [
                    { axis: "Proximity", value: 0.2 },
                    { axis: "Density", value: 0.2 },
                    { axis: "Entropy", value: 0.2 },
                    { axis: "Accessibility", value: 0.2 },
                    { axis: "Closeness", value: 0.2 }
                ]
            },
            {
                className: "metrics-quartiere2",
                axes: [
                    { axis: "Proximity", value: 0.2 },
                    { axis: "Density", value: 0.2 },
                    { axis: "Entropy", value: 0.2 },
                    { axis: "Accessibility", value: 0.2 },
                    { axis: "Closeness", value: 0.2 }
                ]
            }
        ];

        // Reset spider chart 
        const chart1 = document.getElementById('spider-chart-1');
        if (chart1) {
            const chart1Obj = spiderCharts.find(chart => chart.id === 'chart1');
            if (chart1Obj) {
                chart1Obj.chart.updateData(defaultData);
                chart1Obj.id = 'chart1';
            }
        }

        // Reset parallel chart
        const parallelChart1 = document.getElementById('parallel-coordinates-1');
        if (parallelChart1) {
            const parallelChart1Obj = parallelCharts.find(chart => chart.id === 'chart1');
            if (parallelChart1Obj) {
                parallelChart1Obj.chart.updateData(defaultData);
            }
        }
    }

    function initializeSpiderChart(containerId, neighborhoodId, averages) {
        try {
            if (typeof d3 === 'undefined') {
                console.error('D3.js is not available! Spider chart cannot be initialized.');
                return;
            }

            const container = document.getElementById(containerId);
            if (!container) {
                console.error(`Spider chart container ${containerId} not found!`);
                return;
            }

            // Non modificare il display qui - sarà gestito da currentChartType

            // Trova lo spider chart esistente
            const chartIndex = spiderCharts.findIndex(chart => chart.id === 'chart1');
            if (chartIndex !== -1) {
                // Determina se è il primo o secondo quartiere
                const neighborhoodIndex = selectedNeighbourhoods.indexOf(selectedNeighbourhoods.find(n => n.id === neighborhoodId));
                const className = neighborhoodIndex === 0 ? "metrics-quartiere1" : "metrics-quartiere2";
                
                // Ottieni i dati esistenti del chart
                let currentData = spiderCharts[chartIndex].chart.data || [];
                
                // se non ci sono dati, inizializza con valori di default
                if (currentData.length === 0) {
                    currentData = [
                        {
                            className: "metrics-quartiere1",
                            axes: [
                                { axis: "Proximity", value: 0.2 },
                                { axis: "Density", value: 0.2 },
                                { axis: "Entropy", value: 0.2 },
                                { axis: "Accessibility", value: 0.2 },
                                { axis: "Closeness", value: 0.2 }
                            ]
                        },
                        {
                            className: "metrics-quartiere2",
                            axes: [
                                { axis: "Proximity", value: 0.2 },
                                { axis: "Density", value: 0.2 },
                                { axis: "Entropy", value: 0.2 },
                                { axis: "Accessibility", value: 0.2 },
                                { axis: "Closeness", value: 0.2 }
                            ]
                        }
                    ];
                }
                
                // Aggiorna i dati del quartiere
                const neighborhoodDataIndex = currentData.findIndex(d => d.className === className);
                if (neighborhoodDataIndex !== -1) {
                    currentData[neighborhoodDataIndex] = {
                        className: className,
                        axes: [
                            { axis: "Proximity", value: parseFloat(averages.proximity) || 0.2 },
                            { axis: "Density", value: parseFloat(averages.density) || 0.2 },
                            { axis: "Entropy", value: parseFloat(averages.entropy) || 0.2 },
                            { axis: "Accessibility", value: parseFloat(averages.accessibility) || 0.2 },
                            { axis: "Closeness", value: parseFloat(averages.closeness) || 0.2 }
                        ]
                    };
                }

                spiderCharts[chartIndex].chart.updateData(currentData);
                console.log(`Spider chart updated for neighbourhood ${neighborhoodId} (${className})`);
            }
            
        } catch (error) {
            console.error(`Error updating spider chart for neighbourhood ${neighborhoodId}:`, error);
        }
    }

    function initializeParallelChart(containerId, neighborhoodId, averages) {
        try {
            if (typeof d3 === 'undefined') {
                console.error('D3.js is not available! Parallel coordinates cannot be initialized.');
                return;
            }

            const container = document.getElementById(containerId);
            if (!container) {
                console.error(`Parallel coordinates container ${containerId} not found!`);
                return;
            }

            // Trova il parallel chart esistente
            const chartIndex = parallelCharts.findIndex(chart => chart.id === 'chart1');
            if (chartIndex !== -1) {
                // Determina se è il primo o secondo quartiere
                const neighborhoodIndex = selectedNeighbourhoods.indexOf(selectedNeighbourhoods.find(n => n.id === neighborhoodId));
                const className = neighborhoodIndex === 0 ? "metrics-quartiere1" : "metrics-quartiere2";
                
                // Ottieni i dati esistenti del chart
                let currentData = parallelCharts[chartIndex].chart.data || [];
                
                // se non ci sono dati, inizializza con valori di default
                if (currentData.length === 0) {
                    currentData = [
                        {
                            className: "metrics-quartiere1",
                            axes: [
                                { axis: "Proximity", value: 0.2 },
                                { axis: "Density", value: 0.2 },
                                { axis: "Entropy", value: 0.2 },
                                { axis: "Accessibility", value: 0.2 },
                                { axis: "Closeness", value: 0.2 }
                            ]
                        },
                        {
                            className: "metrics-quartiere2",
                            axes: [
                                { axis: "Proximity", value: 0.2 },
                                { axis: "Density", value: 0.2 },
                                { axis: "Entropy", value: 0.2 },
                                { axis: "Accessibility", value: 0.2 },
                                { axis: "Closeness", value: 0.2 }
                            ]
                        }
                    ];
                }
                
                // Aggiorna i dati del quartiere
                const neighborhoodDataIndex = currentData.findIndex(d => d.className === className);
                if (neighborhoodDataIndex !== -1) {
                    currentData[neighborhoodDataIndex] = {
                        className: className,
                        axes: [
                            { axis: "Proximity", value: parseFloat(averages.proximity) || 0.2 },
                            { axis: "Density", value: parseFloat(averages.density) || 0.2 },
                            { axis: "Entropy", value: parseFloat(averages.entropy) || 0.2 },
                            { axis: "Accessibility", value: parseFloat(averages.accessibility) || 0.2 },
                            { axis: "Closeness", value: parseFloat(averages.closeness) || 0.2 }
                        ]
                    };
                }

                parallelCharts[chartIndex].chart.updateData(currentData);
                console.log(`Parallel coordinates updated for neighbourhood ${neighborhoodId} (${className})`);
            }
            
        } catch (error) {
            console.error(`Error updating parallel coordinates for neighbourhood ${neighborhoodId}:`, error);
        }
    }

    function toggleNeighbourhoodSelection(neighbourhood, layer) {
        const neighbourhoodId = neighbourhood.id;
        const existingIndex = selectedNeighbourhoods.findIndex(n => n.id === neighbourhoodId); //controllo se il quartiere è già selezionato
        
        if (existingIndex !== -1) { //se gia selezionato
            // Rimuovi dai selezionati
            selectedNeighbourhoods.splice(existingIndex, 1);
            // Ripristina il colore originale
            layer.setStyle({
                weight: 2,
                fillOpacity: 0.3
            });
        } else { //se non era selezionato
            if (selectedNeighbourhoods.length >= 2) {
                alert('Puoi selezionare al massimo 2 quartieri per il confronto');
                return;
            }
            
            // aggiungo alla lista dei selezionati
            selectedNeighbourhoods.push(neighbourhood);
            // Cambia il colore per indicare la selezione
            layer.setStyle({
                weight: 3,
                fillOpacity: 0.6
            });
        }
        
        updateSelectedNeighbourhoodsDisplay();
    }

    function updateSelectedNeighbourhoodsDisplay() {
        const container = document.getElementById('selected-neighbourhoods');
        
        if (selectedNeighbourhoods.length === 0) {
            container.innerHTML = '<small class="text-muted">Nessun quartiere selezionato</small>';
            return;
        }
        
        let limitMessage = '';
        if (selectedNeighbourhoods.length === 2) { //creo solo se ci sono 2 quartieri selezionati
            limitMessage = '<small class="text-success d-block mb-2"><i class="bi bi-check-circle"></i> Max 2 </small>';
        }
        
        //aggiungi messaggio di limitazioe e i quartieri selezionati
        //con anche la progress bar e il pulsante per rimuovere il quartiere
        container.innerHTML = limitMessage + selectedNeighbourhoods.map(neighbourhood => `
            <div class="d-flex justify-content-between align-items-center mb-2 p-2 bg-light rounded neighbourhood-item">
                <span>
                    <strong>Quartiere ${neighbourhood.id}</strong>
                    <span id="progress-${neighbourhood.id}" class="ms-2 text-muted"></span>
                </span>
                <button class="btn btn-sm btn-outline-danger" onclick="removeNeighbourhood(${neighbourhood.id})">
                    <i class="bi bi-x"></i>
                </button>
            </div>
        `).join('');
    }

    function removeNeighbourhood(neighbourhoodId) {
        const index = selectedNeighbourhoods.findIndex(n => n.id === neighbourhoodId);
        if (index !== -1) {
            selectedNeighbourhoods.splice(index, 1);
        }
        
        neighbourhoodLayers.forEach(layer => {
            if (layer.neighbourhoodId === neighbourhoodId) {
                layer.setStyle({
                    weight: 2,
                    fillOpacity: 0.3
                });
            }
        });
        
        updateSelectedNeighbourhoodsDisplay();
    }

    window.removeNeighbourhood = removeNeighbourhood;
    
    // funzione chiamata quando clicchiamo sul bottone "Seleziona/Deseleziona" del quartiere nel popup
    window.toggleNeighbourhoodFromPopup = function(neighbourhoodId) {
        //recupera quartiere e layer
        const neighbourhood = window.currentNeighbourhoods ? 
            window.currentNeighbourhoods.find(n => n.id === neighbourhoodId) : null;
        
        if (!neighbourhood) {
            return;
        }
        
        const layer = window.neighbourhoodLayers ? window.neighbourhoodLayers[neighbourhoodId] : null;
        
        if (!layer) {
            return;
        }
        
        //se trova entrambi, chiama la funzione per selezionare/deselezionare il quartiere
        toggleNeighbourhoodSelection(neighbourhood, layer);
        // e chiude il popup
        if (layer.isPopupOpen()) {
            layer.closePopup();
        }
    };

    function extractCityNameFromAddress(address) {
        
        const parts = address.split(',');
        if (parts.length >= 1) {
            return parts[0].trim();
        }
        return address.trim();
    }

    async function handleSearchInput() {
        const query = elements.searchInput.value.trim();
        if (query.length < 2) {
            elements.suggestionsList.innerHTML = '';
            return;
        }

        try {
            const places = await ApiService.fetchPlaces(query);
            updateSuggestionsList(places);
        } catch (error) {
            console.error('Error during search:', error);
            elements.suggestionsList.innerHTML = '<li class="list-group-item">Errore durante la ricerca</li>';
        }
    }

    function updateSuggestionsList(places) {
        if (!places || places.length === 0) {
            elements.suggestionsList.innerHTML = '<li class="list-group-item">Nessun risultato trovato</li>';
            return;
        }

        elements.suggestionsList.innerHTML = places
            .map(place => createSuggestionItem(place))
            .join('');

        elements.suggestionsList.querySelectorAll('li').forEach(attachSuggestionClickHandler);
    }

    function createSuggestionItem(place) {
        return `
            <li class="list-group-item" data-lat="${place.coordinates[0]}" data-lon="${place.coordinates[1]}">
                ${place.name}
            </li>
        `;
    }

    function attachSuggestionClickHandler(li) { //quando premi su un suggerimento
        li.addEventListener('click', () => {
            const addressText = li.textContent.trim();
            elements.searchInput.value = addressText;
            const lat = parseFloat(li.dataset.lat);
            const lon = parseFloat(li.dataset.lon);
            selectedCoordinates = [lat, lon]; //salva la posizione selezionata
            
            selectedCityName = extractCityNameFromAddress(addressText);

            //mostra cosa hai selezionato
            elements.selectedAddressDiv.innerHTML = `
                <div class="alert alert-info">
                    <small>City: ${selectedCityName}</small><br>
                    <small>Coordinates: ${lat.toFixed(6)}, ${lon.toFixed(6)}</small>
                </div>
            `;

            if (window.map) { //centro la mappa sulla città selezionata
                window.map.setView([lat, lon], 13);
            }
            elements.suggestionsList.innerHTML = ''; //pulisco i suggerimenti
        });
    }

    async function handleSearch() {
        if (!selectedCoordinates) {
            alert('Per favore, seleziona prima una località dalla barra di ricerca');
            return;
        }

        try {
            clearNeighbourhoodLayers();
            
            const neighbourhoods = await ApiService.fetchAllNeighbourhoods(selectedCityName);
            
            displayNeighbourhoodsOnMap(neighbourhoods);
            
        } catch (error) {
            console.error('Error fetching neighbourhoods:', error);
            alert(`Errore: ${error.message}`);
        }
    }

    function displayNeighbourhoodsOnMap(neighbourhoods) {
        if (!window.map || !neighbourhoods || neighbourhoods.length === 0) {
            return;
        }
        
        window.currentNeighbourhoods = neighbourhoods;

        // colori per i quartieri
        const colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
            '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
            '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2'
        ];

        neighbourhoods.forEach((neighbourhood, index) => { //per ogni quartiere
            try {
                const color = colors[index % colors.length]; //scelgo un colore
                neighbourhoodColors[neighbourhood.id] = color; //lo salvo per quando voglio fare i nodi dello stesso colore
                
                const polygon = L.polygon(neighbourhood.coordinates, { //creo quartiere
                    color: color,
                    weight: 2,
                    opacity: 0.8,
                    fillColor: color,
                    fillOpacity: 0.3
                });

                polygon.neighbourhoodId = neighbourhood.id;

                // pop up quando clicchiamo sul quartiere
                polygon.bindPopup(`
                    <div class="neighbourhood-popup">
                        <h6>Quartiere ${neighbourhood.id || index + 1}</h6>
                        <button class="btn btn-sm btn-primary" onclick="toggleNeighbourhoodFromPopup(${neighbourhood.id})">
                            Seleziona/Deseleziona
                        </button>
                    </div>
                `);

                // effetti hover
                polygon.on('mouseover', function(e) {
                    if (!selectedNeighbourhoods.find(n => n.id === neighbourhood.id)) {
                        this.setStyle({
                            weight: 3,
                            fillOpacity: 0.5
                        });
                    }
                });

                polygon.on('mouseout', function(e) {
                    if (!selectedNeighbourhoods.find(n => n.id === neighbourhood.id)) {
                        this.setStyle({
                            weight: 2,
                            fillOpacity: 0.3
                        });
                    }
                });

                window.neighbourhoodLayers = window.neighbourhoodLayers || [];
                window.neighbourhoodLayers[neighbourhood.id] = polygon;

                // aggiungiamo alla mappa e salviamo il riferimento
                polygon.addTo(window.map);
                neighbourhoodLayers.push(polygon);

            } catch (error) {
                console.error(`Error creating polygon for neighbourhood ${index}:`, error);
            }
        });

        // adattiamo la mappa per mostrare tutti i quartieri
        if (neighbourhoodLayers.length > 0) {
            const group = new L.featureGroup(neighbourhoodLayers);
            window.map.fitBounds(group.getBounds().pad(0.1));
        }
    }

    function handleOutsideClick(event) {
        // se clicco fuori dalla barra indirizzo, pulisco i suggerimenti
        if (!elements.searchInput.contains(event.target) && !elements.suggestionsList.contains(event.target)) {
            elements.suggestionsList.innerHTML = '';
        }
    }

    setupEventListeners();
});
