import { ApiService } from './services/apiService.js';

// funzione debounce per evitare troppe chiamate
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
        selectedAddressDiv: document.querySelector('.selected-address'),
        searchButton: document.getElementById('search-btn'),
        resetButton: document.getElementById('reset-btn')
    };

    let selectedCoordinates = null;
    let selectedCityName = null;
    let neighbourhoodLayers = []; // salviamo i layer per rimuoverli dopo

    function setupEventListeners() {
        // setup del toggle della sidebar
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
        elements.searchButton.addEventListener('click', handleSearch);
        elements.resetButton.addEventListener('click', handleReset);
        document.addEventListener('click', handleOutsideClick);
    }

    function handleReset() {
        elements.searchInput.value = '';
        selectedCoordinates = null;
        selectedCityName = null;
        elements.selectedAddressDiv.innerHTML = '';
        elements.suggestionsList.innerHTML = '';

        // puliamo i layer dei quartieri
        clearNeighbourhoodLayers();

        if (window.map) {
            window.map.setView([45.0703, 7.6869], 13);
        }
    }

    function clearNeighbourhoodLayers() {
        // rimuoviamo tutti i layer dei quartieri dalla mappa
        neighbourhoodLayers.forEach(layer => {
            if (window.map && window.map.hasLayer(layer)) {
                window.map.removeLayer(layer);
            }
        });
        neighbourhoodLayers = [];
    }

    function extractCityNameFromAddress(address) {
        // estraiamo il nome della città dall'indirizzo
        // Nominatim usa il formato: "Nome Luogo, Provincia, Regione, Italia"
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

    function attachSuggestionClickHandler(li) {
        li.addEventListener('click', () => {
            const addressText = li.textContent.trim();
            elements.searchInput.value = addressText;
            const lat = parseFloat(li.dataset.lat);
            const lon = parseFloat(li.dataset.lon);
            selectedCoordinates = [lat, lon];
            
            // estraiamo il nome della città dall'indirizzo
            selectedCityName = extractCityNameFromAddress(addressText);

            // aggiorniamo la visualizzazione dell'indirizzo selezionato
            elements.selectedAddressDiv.innerHTML = `
                <div class="alert alert-info">
                    <strong>Selected:</strong> ${addressText}<br>
                    <small>City: ${selectedCityName}</small><br>
                    <small>Coordinates: ${lat.toFixed(6)}, ${lon.toFixed(6)}</small>
                </div>
            `;

            if (window.map) {
                window.map.setView([lat, lon], 13);
            }
            elements.suggestionsList.innerHTML = '';
        });
    }

    async function handleSearch() {
        if (!selectedCoordinates) {
            alert('Per favore, seleziona prima una località dalla barra di ricerca');
            return;
        }

        try {
            // puliamo i layer esistenti dei quartieri
            clearNeighbourhoodLayers();
            
            // prendiamo tutti i quartieri per la città selezionata
            const neighbourhoods = await ApiService.fetchAllNeighbourhoods(selectedCityName);
            
            // mostriamo i quartieri sulla mappa
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

        // definiamo i colori per i quartieri
        const colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
            '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
            '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2'
        ];

        neighbourhoods.forEach((neighbourhood, index) => {
            try {
                const color = colors[index % colors.length];
                
                // creiamo il poligono dalle coordinate
                const polygon = L.polygon(neighbourhood.coordinates, {
                    color: color,
                    weight: 2,
                    opacity: 0.8,
                    fillColor: color,
                    fillOpacity: 0.3
                });

                // aggiungiamo popup con info del quartiere
                polygon.bindPopup(`
                    <div>
                        <h6>Quartiere ${neighbourhood.id || index + 1}</h6>
                        <p><strong>ID:</strong> ${neighbourhood.id || 'N/A'}</p>
                        <p><strong>Colore:</strong> ${color}</p>
                    </div>
                `);

                // aggiungiamo effetti hover
                polygon.on('mouseover', function(e) {
                    this.setStyle({
                        weight: 3,
                        fillOpacity: 0.5
                    });
                });

                polygon.on('mouseout', function(e) {
                    this.setStyle({
                        weight: 2,
                        fillOpacity: 0.3
                    });
                });

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
        if (!elements.searchInput.contains(event.target) && !elements.suggestionsList.contains(event.target)) {
            elements.suggestionsList.innerHTML = '';
        }
    }

    setupEventListeners();
});
