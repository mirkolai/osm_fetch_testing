document.addEventListener('DOMContentLoaded', () => {
    // Existing elements from current version
    const searchInput = document.getElementById('city-search');
    const suggestionsList = document.getElementById('suggestions');
    const selectedServicesDiv = document.querySelector('.selected-services');

    // Add transport buttons functionality from old version
    const transportButtons = document.querySelectorAll('.btn-group .btn');
    transportButtons.forEach(button => {
        button.addEventListener('click', function() {
            transportButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
        });
    });

    // Autocomplete functionality from current version
    searchInput.addEventListener('input', async () => {
        const query = searchInput.value.trim();
        console.log('Input value:', query);

        if (query.length < 2) {
            suggestionsList.innerHTML = '';
            return;
        }

        try {
            const response = await fetch('/api/reverse_geocoding', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: query
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const places = await response.json();

            if (!places || places.length === 0) {
                suggestionsList.innerHTML = '<li class="list-group-item">Nessun risultato trovato</li>';
                return;
            }

            suggestionsList.innerHTML = places
                .map(place => `
                    <li class="list-group-item" data-lat="${place.coordinates[0]}" data-lon="${place.coordinates[1]}">
                        ${place.name}
                    </li>
                `)
                .join('');

            suggestionsList.querySelectorAll('li').forEach(li => {
                li.addEventListener('click', () => {
                    searchInput.value = li.textContent.trim();
                    const lat = parseFloat(li.dataset.lat);
                    const lon = parseFloat(li.dataset.lon);
                    if (window.map) {
                        window.map.setView([lat, lon], 13);
                    }
                    suggestionsList.innerHTML = '';
                });
            });

        } catch (error) {
            console.error('Error during search:', error);
            suggestionsList.innerHTML = '<li class="list-group-item">Errore durante la ricerca</li>';
        }
    });

    // Improved service selection handling (combining both versions)
    document.querySelectorAll('.form-check-input').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const serviceName = this.nextElementSibling.textContent.trim();
            if (this.checked) {
                addServiceBadge(serviceName);
            } else {
                removeServiceBadge(serviceName);
            }
            updateSelectedServices();
        });
    });

    function addServiceBadge(serviceName) {
        const badge = document.createElement('span');
        badge.classList.add('badge', 'bg-primary', 'me-1', 'mb-1');
        badge.innerHTML = `${serviceName} <i class="bi bi-x"></i>`;
        badge.querySelector('i').addEventListener('click', () => {
            removeService(serviceName);
        });
        selectedServicesDiv.appendChild(badge);
    }

    function removeServiceBadge(serviceName) {
        const badges = selectedServicesDiv.querySelectorAll('.badge');
        badges.forEach(badge => {
            if (badge.textContent.includes(serviceName)) {
                badge.remove();
            }
        });
    }

    function updateSelectedServices() {
        const selectedServices = [];
        document.querySelectorAll('.form-check-input:checked').forEach(checkbox => {
            const serviceName = checkbox.nextElementSibling.textContent.trim();
            selectedServices.push(serviceName);
        });

        selectedServicesDiv.innerHTML = selectedServices
            .map(service => `
                <span class="badge bg-primary me-1 mb-1">
                    ${service} 
                    <i class="bi bi-x" onclick="removeService('${service}')"></i>
                </span>
            `)
            .join('');
    }

    // Global removeService function
    window.removeService = function(serviceName) {
        const checkbox = Array.from(document.querySelectorAll('.form-check-input')).find(
            cb => cb.nextElementSibling.textContent.trim() === serviceName
        );
        if (checkbox) {
            checkbox.checked = false;
            updateSelectedServices();
        }
    };

    // Close suggestions when clicking outside
    document.addEventListener('click', (event) => {
        if (!searchInput.contains(event.target) && !suggestionsList.contains(event.target)) {
            suggestionsList.innerHTML = '';
        }
    });
});