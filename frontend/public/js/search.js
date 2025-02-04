document.addEventListener('DOMContentLoaded', () => {
    const elements = {
        searchInput: document.getElementById('city-search'),
        suggestionsList: document.getElementById('suggestions'),
        selectedServicesDiv: document.querySelector('.selected-services'),
        searchButton: document.querySelector('.btn.custom-primary'),
        timeSelect: document.querySelector('.time-select'),
        transportButtons: document.querySelectorAll('.btn-group .btn')
    };

    let isochroneLayer = null;
    let selectedCoordinates = null;
    let poiMarkers = [];

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

        document.querySelectorAll('.form-check-input').forEach(checkbox => {
            checkbox.addEventListener('change', handleServiceChange);
        });

        document.addEventListener('click', handleOutsideClick);
    }

    function handleTransportClick() {
        elements.transportButtons.forEach(btn => btn.classList.remove('active'));
        this.classList.add('active');

        if (selectedCoordinates && isochroneLayer) {
            drawIsochrone();
        }
    }

    function handleServiceChange() {
        const serviceName = this.nextElementSibling.textContent.trim();
        this.checked ? addServiceBadge(serviceName) : removeServiceBadge(serviceName);
        updateSelectedServices();
    }

    function handleOutsideClick(event) {
        if (!elements.searchInput.contains(event.target) && !elements.suggestionsList.contains(event.target)) {
            elements.suggestionsList.innerHTML = '';
        }
    }

    async function handleSearchInput() {
        const query = elements.searchInput.value.trim();
        if (query.length < 2) {
            elements.suggestionsList.innerHTML = '';
            return;
        }

        try {
            const places = await fetchPlaces(query);
            updateSuggestionsList(places);
        } catch (error) {
            console.error('Error during search:', error);
            elements.suggestionsList.innerHTML = '<li class="list-group-item">Errore durante la ricerca</li>';
        }
    }

    async function fetchPlaces(query) {
        const response = await fetch('/api/reverse_geocoding', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: query })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return response.json();
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

    async function getPoisForNode(nodeId) {
        const response = await fetch('/api/test_get_data_pois_near_node', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ node_id: nodeId })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    }

    function clearPoiMarkers() {
        poiMarkers.forEach(marker => window.map.removeLayer(marker));
        poiMarkers = [];
    }

    //per i punti di interesse
    function addPoiMarkers(pois) {
        clearPoiMarkers();

        pois.forEach(poi => {
            const circle = L.circleMarker([
                poi.location.coordinates[0],
                poi.location.coordinates[1]
            ], {
                radius: 6,
                fillColor: '#483d8b',
                color: '#483d8b',
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
            }).bindPopup(`
                <strong>${poi.names.primary || 'Unknown'}</strong><br>
                Category: ${poi.categories.primary || 'Not specified'}<br>
                Distance: ${poi.distance.toFixed(0)}m
            `);

            circle.addTo(window.map);
            poiMarkers.push(circle);
        });
    }

    async function drawIsochrone() {
        if (!selectedCoordinates) {
            alert('Per favore, seleziona prima una località dalla barra di ricerca');
            return;
        }

        try {
            const nodeResponse = await fetch('/api/get_node_id', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    lat: selectedCoordinates[0],
                    lon: selectedCoordinates[1]
                })
            });

            if (!nodeResponse.ok) {
                throw new Error('Failed to get node ID');
            }

            const nodeData = await nodeResponse.json();
            const nodeId = nodeData.node_id;

            const isochroneData = await fetchIsochroneData(nodeId);
            updateIsochroneLayer(isochroneData);

            const pois = await getPoisForNode(nodeId);
            addPoiMarkers(pois);

        } catch (error) {
            console.error('Error:', error);
            alert('Errore nel calcolo. Per favore riprova.');
        }
    }

    async function fetchIsochroneData(nodeId) {
        const response = await fetch('/api/get_isochrone_walk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                node_id: nodeId,
                minute: getSelectedTime(),
                velocity: getSelectedSpeed()
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return response.json();
    }

    function updateIsochroneLayer(data) {
        if (isochroneLayer && window.map) {
            window.map.removeLayer(isochroneLayer);
        }

        const coordinates = data.convex_hull.coordinates[0].map(coord => [coord[1], coord[0]]);

        isochroneLayer = L.polygon(coordinates, {
            color: '#483d8b',
            fillColor: '#483d8b',
            fillOpacity: 0.3,
            weight: 2
        }).addTo(window.map);

        window.map.fitBounds(isochroneLayer.getBounds());
    }

    function addServiceBadge(serviceName) {
        const badge = document.createElement('span');
        badge.classList.add('badge', 'bg-primary', 'me-1', 'mb-1');
        badge.innerHTML = `${serviceName} <i class="bi bi-x"></i>`;
        badge.querySelector('i').addEventListener('click', () => {
            removeService(serviceName);
        });
        elements.selectedServicesDiv.appendChild(badge);
    }

    function removeServiceBadge(serviceName) {
        const badges = elements.selectedServicesDiv.querySelectorAll('.badge');
        badges.forEach(badge => {
            if (badge.textContent.includes(serviceName)) {
                badge.remove();
            }
        });
    }

    function updateSelectedServices() {
        const selectedServices = Array.from(document.querySelectorAll('.form-check-input:checked'))
            .map(checkbox => checkbox.nextElementSibling.textContent.trim());

        elements.selectedServicesDiv.innerHTML = selectedServices
            .map(service => `
                <span class="badge bg-primary me-1 mb-1">
                    ${service} 
                    <i class="bi bi-x" onclick="removeService('${service}')"></i>
                </span>
            `)
            .join('');
    }

    window.removeService = function(serviceName) {
        const checkbox = Array.from(document.querySelectorAll('.form-check-input'))
            .find(cb => cb.nextElementSibling.textContent.trim() === serviceName);

        if (checkbox) {
            checkbox.checked = false;
            updateSelectedServices();
        }
    };

    setupEventListeners();
});