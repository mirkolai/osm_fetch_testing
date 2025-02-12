import { MapManager } from './managers/map-manager.js';
import { ApiService } from './services/api-service.js';

document.addEventListener('DOMContentLoaded', () => {
    const elements = {
        searchInput: document.getElementById('city-search'),
        suggestionsList: document.getElementById('suggestions'),
        selectedServicesDiv: document.querySelector('.selected-services'),
        searchButton: document.querySelector('.btn.custom-primary'),
        timeSelect: document.querySelector('.time-select'),
        transportButtons: document.querySelectorAll('.btn-group .btn')
    };

    let selectedCoordinates = null;
    const mapManager = new MapManager(window.map);

    const transportSpeeds = {
        'bi-person-walking': 5,
        'bi-person-wheelchair': 3,
        'bi-bicycle': 12,
        'bi-train-front': 20
    };

    function setupEventListeners() {
        elements.transportButtons.forEach(button => {
            button.addEventListener('click', handleTransportClick);
        });

        elements.searchInput.addEventListener('input', handleSearchInput);
        elements.searchButton.addEventListener('click', drawIsochrone);
        document.addEventListener('click', handleOutsideClick);
    }

    function handleTransportClick() {
        elements.transportButtons.forEach(btn => btn.classList.remove('active'));
        this.classList.add('active');

        if (selectedCoordinates && mapManager.isochroneLayer) {
            drawIsochrone();
        }
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

    async function drawIsochrone() {
        if (!selectedCoordinates) {
            alert('Per favore, seleziona prima una località dalla barra di ricerca');
            return;
        }

        const time = getSelectedTime();
        const speed = getSelectedSpeed();

        console.log('Drawing isochrone with params:', {
            coordinates: selectedCoordinates,
            time,
            speed
        });

        try {
            const isochroneData = await ApiService.fetchIsochroneData(
                selectedCoordinates,
                time,
                speed
            );
            mapManager.updateIsochroneLayer(isochroneData);

            // Fetch and draw POIs
            const poisData = await ApiService.getPoisInIsochrone(
                selectedCoordinates,
                time,
                speed
            );
            mapManager.addPoiMarkers(poisData);

        } catch (error) {
            console.error('Error in drawIsochrone:', error);
            alert('Errore nel calcolo dell\'isocrona. Per favore riprova.');
        }
    }

    async function fetchIsochroneData(nodeId) {
        return ApiService.fetchIsochroneData(nodeId, getSelectedTime(), getSelectedSpeed());
    }

    function handleOutsideClick(event) {
        if (!elements.searchInput.contains(event.target) && !elements.suggestionsList.contains(event.target)) {
            elements.suggestionsList.innerHTML = '';
        }
    }

    setupEventListeners();
});