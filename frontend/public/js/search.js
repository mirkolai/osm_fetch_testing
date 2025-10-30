import { MapManager } from './managers/mapManager.js';
import { ApiService } from './services/apiService.js';
import { SpiderChart } from './components/SpiderChart.js';

let spiderChart;

// Funzione debounce
function debounce(func, delay) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            func.apply(this, args);
        }, delay);
    };
}


document.addEventListener('DOMContentLoaded', () => {
    const elements = {
        searchInput: document.getElementById('city-search'),
        suggestionsList: document.getElementById('suggestions'),
        selectedServicesDiv: document.querySelector('.selected-services'),
        searchButton: document.querySelector('.btn.custom-primary'),
        resetButton: document.querySelector('.btn.btn-outline-secondary'),
        timeSelect: document.querySelector('.time-select'),
        transportButtons: document.querySelectorAll('.btn-group .btn'),
        spiderChartContainer: document.getElementById('spider-chart')
    };

    let selectedCoordinates = null;
    let selectedCategories = new Set();
    const mapManager = new MapManager(window.map);

    const transportSpeeds = {
        'bi-person-walking': 5,
        'bi-person-wheelchair': 3,
        'bi-bicycle': 12,
        'bi-train-front': 20
    };



    initializeSpiderChart();

    function initializeSpiderChart() {
        console.log('Initializing spider chart component...');

        try {
            if (typeof d3 === 'undefined') {
                console.error('D3.js is not available! Spider chart cannot be initialized.');
                return;
            }

            if (!elements.spiderChartContainer) {
                console.error('Spider chart container not found!');
                return;
            }

            spiderChart = new SpiderChart('spider-chart', {
                width: 200,
                height: 200,
                margin: 100,
                maxValue: 1,
                levels: 5,
                color: '#483d8b',
                data: [
                    {
                        className: "metrics",
                        axes: [
                            { axis: "Proximity", value: 0.2 },
                            { axis: "Density", value: 0.2 },
                            { axis: "Entropy", value: 0.2 },
                            { axis: "Accessibility", value: 0.2 },
                            { axis: "Closeness", value: 0.2 }
                        ]
                    }
                ]
            });

            console.log('Spider chart initialized successfully!');
        } catch (error) {
            console.error('Error initializing spider chart:', error);
        }
    }

    function setupEventListeners() {
        elements.transportButtons.forEach(button => {
            button.addEventListener('click', handleTransportClick);
        });

        const selectedServicesDiv = document.querySelector('.selected-services');
        if (selectedServicesDiv) {
            const observer = new MutationObserver(function(mutations) {
                updateSidebarHeight();
            });

            observer.observe(selectedServicesDiv, {
                childList: true,
                subtree: true,
                attributes: true
            });
        }

        function setupSidebarToggle() {
            const sidebar = document.querySelector('.overlay-sidebar');
            const toggleBtn = document.getElementById('sidebar-toggle-btn');
            const toggleIcon = toggleBtn.querySelector('i');

            toggleBtn.addEventListener('click', () => {
                sidebar.classList.toggle('collapsed');

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
        elements.searchInput.addEventListener('input', debounce(handleSearchInput, 1500));
        //elements.searchInput.addEventListener('input', handleSearchInput);
        elements.searchButton.addEventListener('click', handleSearch);
        elements.resetButton.addEventListener('click', handleReset);
        document.addEventListener('click', handleOutsideClick);
        window.addEventListener('resize', updateSidebarHeight);
        updateSidebarHeight();
    }


    function handleReset() {
        selectedCategories.clear();
        elements.selectedServicesDiv.innerHTML = '';

        document.querySelectorAll('service-category').forEach(component => {
            const checkboxes = component.shadowRoot?.querySelectorAll('input[type="checkbox"]');
            if (checkboxes) {
                checkboxes.forEach(checkbox => {
                    checkbox.checked = false;
                });
            }
        });

        elements.searchInput.value = '';
        selectedCoordinates = null;

        if (mapManager.isochroneLayer) {
            mapManager.map.removeLayer(mapManager.isochroneLayer);
            mapManager.isochroneLayer = null;
        }
        mapManager.clearPoiMarkers();
        mapManager.map.setView([45.0703, 7.6869], 13);

        resetSpiderChart();
    }

    function resetSpiderChart() {
        if (spiderChart) {
            spiderChart.updateData([
                {
                    className: "metrics",
                    axes: [
                        { axis: "Proximity", value: 0.2 },
                        { axis: "Density", value: 0.2 },
                        { axis: "Entropy", value: 0.2 },
                        { axis: "Accessibility", value: 0.2 },
                        { axis: "Closeness", value: 0.2 }
                    ]
                }
            ]);
        } else {
            initializeSpiderChart();
        }
    }

    document.addEventListener('service-changed', (e) => {
        const { id, label, checked, isMainCategory, isFromSelectAll } = e.detail;
        if (isFromSelectAll) {
            if (checked) {
                if (!selectedCategories.has(id)) {
                    selectedCategories.add(id);
                    addServiceBadge(id, label);
                }
            } else {
                if (selectedCategories.has(id)) {
                    selectedCategories.delete(id);
                    removeServiceBadge(label);
                }
            }
        }
        else{
            if (checked) {
                selectedCategories.add(id);
                addServiceBadge(id, label);
            } else {
                selectedCategories.delete(id);
                removeServiceBadge(label);
            }
        }
        updateSidebarHeight();
    });

    function addServiceBadge(id, label) {
        const badge = document.createElement('span');
        badge.classList.add('badge', 'bg-primary', 'me-1', 'mb-1');
        badge.dataset.categoryId = id;
        badge.innerHTML = `${label} <i class="bi bi-x"></i>`;
        badge.querySelector('i').addEventListener('click', () => {
            const categoryId = badge.dataset.categoryId;
            selectedCategories.delete(categoryId);
            badge.remove();

            document.querySelectorAll('service-category').forEach(component => {
                const checkbox = component.shadowRoot?.querySelector(`input#${categoryId}`);
                if (checkbox) {
                    checkbox.checked = false;
                }
            });
        });
        elements.selectedServicesDiv.appendChild(badge);
        updateSidebarHeight();
    }

    function removeServiceBadge(label) {
        const badges = elements.selectedServicesDiv.querySelectorAll('.badge');
        badges.forEach(badge => {
            if (badge.textContent.includes(label)) {
                const categoryId = badge.dataset.categoryId;
                badge.remove();

                document.querySelectorAll('service-category').forEach(component => {
                    const checkbox = component.shadowRoot?.querySelector(`input#${categoryId}`);
                    if (checkbox) {
                        checkbox.checked = false;
                    }
                });
            }
        });
        updateSidebarHeight();
    }

    function handleTransportClick() {
        elements.transportButtons.forEach(btn => btn.classList.remove('active'));
        this.classList.add('active');

        if (selectedCoordinates && mapManager.isochroneLayer) {
            handleSearch();
        }
    }

    async function handleSearchInput() {
        const query = elements.searchInput.value.trim();
        if (query.length < 2) {
            elements.suggestionsList.innerHTML = '';
            return;
        }

        try {
            console.log('Searching for:', query);
            const places = await ApiService.fetchPlaces(query);
            console.log('Places found:', places);
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

    function attachSuggestionClickHandler(li) {
        li.addEventListener('click', () => {
            elements.searchInput.value = li.textContent.trim();
            const lat = parseFloat(li.dataset.lat);
            const lon = parseFloat(li.dataset.lon);
            selectedCoordinates = [lat, lon];

            if (window.map) {
                window.map.setView([lat, lon], 13);
            }
            elements.suggestionsList.innerHTML = '';
        });
    }

    function getSelectedSpeed() {
        const activeTransport = document.querySelector('.btn-group .btn.active i');
        if (!activeTransport) return 5;

        for (const [className, speed] of Object.entries(transportSpeeds)) {
            if (activeTransport.classList.contains(className)) {
                return speed;
            }
        }
        return 5;
    }

    function getSelectedTime() {
        return parseInt(elements.timeSelect.value.split(' ')[0]);
    }

    async function handleSearch() {
        if (!selectedCoordinates) {
            alert('Per favore, seleziona prima una località dalla barra di ricerca');
            return;
        }

        document.body.style.cursor = 'wait';

        const requestData = {
            coordinates: selectedCoordinates,
            minutes: getSelectedTime(),
            velocity: getSelectedSpeed(),
            categories: Array.from(selectedCategories)
        };

        try {
            const results = await ApiService.runSearch(
                requestData.coordinates,
                requestData.minutes,
                requestData.velocity,
                requestData.categories
            );

            mapManager.updateIsochroneLayer(results.isochrone);
            mapManager.addPoiMarkers(results.pois);
            updateSpiderChartDisplay(results.parameters);

        } catch (error) {
            console.error('Error in handleSearch:', error);
            alert('Errore durante la ricerca. Per favore riprova.');
        } finally {
            document.body.style.cursor = 'default';
            updateSidebarHeight();
        }
    }

    function updateSpiderChartDisplay(parameters) {
        try {
            if (!spiderChart) {
                console.error('Spider chart not initialized!');
                initializeSpiderChart();
                if (!spiderChart) {
                    throw new Error('Failed to initialize spider chart');
                }
            }

            const formattedData = [
                {
                    className: "metrics",
                    axes: [
                        { axis: "Proximity", value: typeof parameters.proximity_score === 'number' ? parameters.proximity_score : 0.2 },
                        { axis: "Density", value: typeof parameters.density_score === 'number' ? parameters.density_score : 0.2 },
                        { axis: "Entropy", value: typeof parameters.entropy_score === 'number' ? parameters.entropy_score : 0.2 },
                        { axis: "Accessibility", value: typeof parameters.poi_accessibility === 'number' ? parameters.poi_accessibility : 0.2 },
                        { axis: "Closeness", value: typeof parameters.closeness === 'number' ? parameters.closeness : 0.2 }
                    ]
                }
            ];

            console.log('Formatted data for spider chart:', formattedData);
            spiderChart.updateData(formattedData);
        } catch (error) {
            console.error('Error updating spider chart display:', error);
        }
    }

    function handleOutsideClick(event) {
        if (!elements.searchInput.contains(event.target) && !elements.suggestionsList.contains(event.target)) {
            elements.suggestionsList.innerHTML = '';
        }
    }

    function updateSidebarHeight() {
        const sidebar = document.querySelector('.overlay-sidebar');
        const content = sidebar.querySelector('.sidebar-content');

        sidebar.style.height = 'auto';
        const contentHeight = content.scrollHeight;
        sidebar.style.height = (contentHeight + 20) + 'px';
        const maxHeight = window.innerHeight - 100;

        if (contentHeight > maxHeight) {
            sidebar.style.height = maxHeight + 'px';
            sidebar.style.overflowY = 'auto';
        } else {
            sidebar.style.overflowY = 'visible';
        }
    }

    setupEventListeners();
    
    loadUserPreferences();
});

async function loadUserPreferences() {
    try {
        const token = localStorage.getItem('access_token');
        if (!token) {
            return null; // non fare niente se non autenticato
        }

        const response = await fetch('/api/auth/preferences', { // richiede le preferenze dell'utente
            headers: {
                'Authorization': `Bearer ${token}`  
            }
        });

        if (response.ok) { 
            const preferences = await response.json();
            applyPreferencesToUI(preferences);
            return preferences;
        } else {
            console.log('Failed to load preferences, using default settings');
            return null;
        }
    } catch (error) {
        console.error('Error loading user preferences:', error);
        return null;
    }
}

function applyPreferencesToUI(preferences) {
    // time
    const timeSelect = document.querySelector('.time-select');
    if (timeSelect && preferences.min) {
        timeSelect.value = `${preferences.min} min`;
    }

    // travel mode
    const velocityToButton = {
        3: 'fa-person-walking-with-cane',   
        5: 'bi-person-walking',          
        12: 'bi-bicycle',                 
        20: 'bi-train-front'               
    };

    const travelModeButtons = document.querySelectorAll('.btn-group .btn');
    travelModeButtons.forEach(button => {
        button.classList.remove('active');
        const icon = button.querySelector('i');
        if (icon) {
            const iconClass = Array.from(icon.classList).find(cls => 
                velocityToButton[preferences.vel] === cls
            );
            if (iconClass) {
                button.classList.add('active');
            }
        }
    });

    // services
    if (preferences.categories && preferences.categories.length > 0) {
        selectServicesInUI(preferences.categories);
    }
}

function selectServicesInUI(categoryIds) {
    // Clear 
    document.querySelectorAll('service-category').forEach(category => {
        const checkboxes = category.shadowRoot.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
            checkbox.dispatchEvent(new Event('change'));
        });
    });

    document.querySelectorAll('service-category').forEach(category => {
        const checkboxes = category.shadowRoot.querySelectorAll('input[type="checkbox"]');
        const mainCategoryCheckbox = checkboxes[0]; //la categoria
        const subCategoryCheckboxes = Array.from(checkboxes).slice(1); // sottocategorie
        
        const mainCategoryId = mainCategoryCheckbox.id;
        const selectedSubCategories = subCategoryCheckboxes.filter(cb => categoryIds.includes(cb.id));
        
        if (categoryIds.includes(mainCategoryId)) {
            mainCategoryCheckbox.checked = true;
            mainCategoryCheckbox.dispatchEvent(new Event('change'));
        } else if (selectedSubCategories.length > 0) {
            selectedSubCategories.forEach(checkbox => {
                checkbox.checked = true;
                checkbox.dispatchEvent(new Event('change'));
            });
        }
    });
}