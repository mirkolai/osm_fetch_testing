import { servicesList } from './config/servicesList.js';

document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('services-container');
    const selectedServicesDiv = document.querySelector('.selected-services-center');
    const selectAllButton = document.getElementById('select-all-categories');


    if (container) { //lo trova solo se l'utente è loggato
         
        Object.values(servicesList).forEach(category => {
            const element = document.createElement('service-category');
            element.setAttribute('title', category.title);
            element.setAttribute('services', JSON.stringify(category.services));
            container.appendChild(element);
        });

        let allSelected = false;
        let selectedCategories = new Set();
        
        // Event listener per gestire i cambiamenti dei servizi (identico alla search page)
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
        });

        // Funzioni per gestire i badge dei servizi selezionati (identiche alla search page)
        function addServiceBadge(id, label) {
            // Rimuovi il messaggio di default se presente
            const defaultMessage = selectedServicesDiv.querySelector('p.text-muted');
            if (defaultMessage) {
                defaultMessage.remove();
            }
            
            const badge = document.createElement('span');
            badge.classList.add('badge', 'bg-primary', 'me-1', 'mb-1', 'fs-7', 'px-2', 'py-1');
            badge.dataset.categoryId = id;
            badge.innerHTML = `${label} <i class="bi bi-x ms-1"></i>`;
            badge.querySelector('i').addEventListener('click', () => {
                const categoryId = badge.dataset.categoryId;
                selectedCategories.delete(categoryId);
                badge.remove();

                // Se non ci sono più badge, mostra il messaggio di default
                if (selectedServicesDiv.children.length === 0) {
                    selectedServicesDiv.innerHTML = '<p class="text-muted text-center mb-0"><i class="bi bi-info-circle me-2"></i>Selected services will appear here</p>';
                }


                document.querySelectorAll('service-category').forEach(component => {
                    const checkbox = component.shadowRoot?.querySelector(`input#${categoryId}`);
                    if (checkbox) {
                        checkbox.checked = false;
                    }
                });
            });
            selectedServicesDiv.appendChild(badge);
        }

        function removeServiceBadge(label) {
            const badges = selectedServicesDiv.querySelectorAll('.badge');
            badges.forEach(badge => {
                if (badge.textContent.includes(label)) {
                    const categoryId = badge.dataset.categoryId;
                    badge.remove();

                    // Se non ci sono più badge, mostra il messaggio di default
                    if (selectedServicesDiv.children.length === 0) {
                        selectedServicesDiv.innerHTML = '<p class="text-muted text-center mb-0"><i class="bi bi-info-circle me-2"></i>Selected services will appear here</p>';
                    }


                    document.querySelectorAll('service-category').forEach(component => {
                        const checkbox = component.shadowRoot?.querySelector(`input#${categoryId}`);
                        if (checkbox) {
                            checkbox.checked = false;
                        }
                    });
                }
            });
        }

        
        selectAllButton.addEventListener('click', () => {
            const serviceCategories = container.querySelectorAll('service-category');
            
            if (!allSelected) {
                //seleziona tutto
                serviceCategories.forEach(category => {
                    const checkboxes = category.shadowRoot.querySelectorAll('input[type="checkbox"]');
                    checkboxes.forEach(checkbox => {
                        if (!checkbox.checked) {
                            checkbox.checked = true;
                            checkbox.dispatchEvent(new Event('change'));
                        }
                    });
                });
                
                selectAllButton.innerHTML = '<i class="fas fa-check-square"></i> Deselect All Categories';
                allSelected = true;
            } else {
                //deseleziona tutto
                serviceCategories.forEach(category => {
                    const checkboxes = category.shadowRoot.querySelectorAll('input[type="checkbox"]');
                    checkboxes.forEach(checkbox => {
                        if (checkbox.checked) {
                            checkbox.checked = false;
                            checkbox.dispatchEvent(new Event('change'));
                        }
                    });
                });
                
                selectAllButton.innerHTML = '<i class="fas fa-square"></i> Select All Categories';
                allSelected = false;
            }
        });
    }

    // Gestione bottoni modalità di viaggio - identica alla search page
    const travelModeButtons = document.querySelectorAll('#settings-section .btn-group .btn');
    travelModeButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Rimuovi classe active da tutti i bottoni
            travelModeButtons.forEach(btn => btn.classList.remove('active'));
            // Aggiungi classe active al bottone cliccato
            button.classList.add('active');
            
            // Aggiorna la visualizzazione delle impostazioni di viaggio
            updateTravelSettingsDisplay();
        });
    });

    // Gestione selezione tempo
    const timeSelect = document.querySelector('#settings-section .time-select');
    if (timeSelect) {
        timeSelect.addEventListener('change', () => {
            updateTravelSettingsDisplay();
        });
    }

    // Gestione bottoni azione
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    const changeSettingsBtn = document.getElementById('change-settings-btn');
    const settingsSection = document.getElementById('settings-section');

    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', async () => {
            try {
                // Collect current settings
                const timeSelect = document.querySelector('.time-select');
                const timeValue = timeSelect ? parseInt(timeSelect.value) : 15;
                
                // Get active travel mode button and determine velocity
                const activeButton = document.querySelector('#settings-section .btn-group .btn.active');
                let velocity = 5; // default to walking
                if (activeButton) {
                    const icon = activeButton.querySelector('i');
                    if (icon) {
                        const iconClass = Array.from(icon.classList).find(cls => 
                            ['bi-person-walking', 'fa-person-walking-with-cane', 'bi-bicycle', 'bi-train-front'].includes(cls)
                        );
                        const velocityMap = {
                            'bi-person-walking': 5,
                            'fa-person-walking-with-cane': 3,
                            'bi-bicycle': 12,
                            'bi-train-front': 20
                        };
                        velocity = velocityMap[iconClass] || 5;
                    }
                }
                
                // Collect selected services
                const selectedCategories = [];
                document.querySelectorAll('service-category').forEach(category => {
                    const checkboxes = category.shadowRoot.querySelectorAll('input[type="checkbox"]:checked');
                    checkboxes.forEach(checkbox => {
                        selectedCategories.push(checkbox.id);
                    });
                });
                
                // Save preferences
                const token = localStorage.getItem('access_token');
                const response = await fetch('/api/auth/preferences', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        min: timeValue,
                        vel: velocity,
                        categories: selectedCategories
                    })
                });
                
                if (response.ok) {
                    // Chiudi il popup
                    if (settingsSection) {
                        settingsSection.style.display = 'none';
                    }
                    
                    // Mostra feedback visivo temporaneo
                    const originalText = saveSettingsBtn.innerHTML;
                    saveSettingsBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>Salvato!';
                    saveSettingsBtn.classList.remove('btn-primary');
                    saveSettingsBtn.classList.add('btn-success');
                    
                    // Ripristina il testo originale dopo 2 secondi
                    setTimeout(() => {
                        saveSettingsBtn.innerHTML = originalText;
                        saveSettingsBtn.classList.remove('btn-success');
                        saveSettingsBtn.classList.add('btn-primary');
                    }, 2000);
                } else {
                    throw new Error('Failed to save preferences');
                }
            } catch (error) {
                console.error('Error saving preferences:', error);
                // Show error feedback
                const originalText = saveSettingsBtn.innerHTML;
                saveSettingsBtn.innerHTML = '<i class="bi bi-exclamation-triangle me-2"></i>Errore!';
                saveSettingsBtn.classList.remove('btn-primary');
                saveSettingsBtn.classList.add('btn-danger');
                
                setTimeout(() => {
                    saveSettingsBtn.innerHTML = originalText;
                    saveSettingsBtn.classList.remove('btn-danger');
                    saveSettingsBtn.classList.add('btn-primary');
                }, 2000);
            }
        });
    }


    // Event listener per il bottone "Change Favorite Settings"
    if (changeSettingsBtn) {
        changeSettingsBtn.addEventListener('click', async () => {
            if (settingsSection) {
                settingsSection.style.display = 'block';
                // Load current preferences and apply them to the popup
                await loadUserPreferencesInPopup();
            }
        });
    }
});


async function loadUserPreferencesInPopup() {
    try {
        const token = localStorage.getItem('access_token');
        if (!token) return;

        const response = await fetch('/api/auth/preferences', { //richiedi preferenze
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            const preferences = await response.json();
            applyPreferencesToPopup(preferences); //metti preferenze
        }
    } catch (error) {
        console.error('Error loading user preferences:', error);
    }
}

function applyPreferencesToPopup(preferences) {
    // tempo
    const timeSelect = document.querySelector('.time-select');
    if (timeSelect) {
        timeSelect.value = `${preferences.min} min`;
    }

    // velocità
    const velocityToButton = { //definire le icone
        3: 'fa-person-walking-with-cane',  
        5: 'bi-person-walking',            
        12: 'bi-bicycle',                  
        20: 'bi-train-front'               
    };

    const travelModeButtons = document.querySelectorAll('#settings-section .btn-group .btn');
    travelModeButtons.forEach(button => {
        button.classList.remove('active');
        const icon = button.querySelector('i');
        if (icon) { //scegli che icona mettere
            const iconClass = Array.from(icon.classList).find(cls => 
                velocityToButton[preferences.vel] === cls
            );
            if (iconClass) {
                button.classList.add('active'); //coloro box selezionato
            }
        }
    });

    // servizi
    if (preferences.categories && preferences.categories.length > 0) {
        selectServicesInPopup(preferences.categories);
    }

    updateTravelSettingsDisplay();
}

function selectServicesInPopup(categoryIds) {
    // Clear
    document.querySelectorAll('service-category').forEach(category => {
        const checkboxes = category.shadowRoot.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
            checkbox.dispatchEvent(new Event('change'));
        });
    });

    //mette i servizi selezionati
    document.querySelectorAll('service-category').forEach(category => {
        const checkboxes = category.shadowRoot.querySelectorAll('input[type="checkbox"]');
        const mainCategoryCheckbox = checkboxes[0]; // main category
        const subCategoryCheckboxes = Array.from(checkboxes).slice(1); // subcategories
        
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

function updateTravelSettingsDisplay() {
    const selectedTimeElement = document.getElementById('selected-time');
    const selectedModeElement = document.getElementById('selected-mode');
    const timeSelect = document.querySelector('#settings-section .time-select');
    
    // scrive tempo selezionato (testo)
    if (selectedTimeElement && timeSelect) {
        selectedTimeElement.textContent = timeSelect.value;
    }
    
    // scrive nome modalità selezionata (testo)
    if (selectedModeElement) {
        const activeButton = document.querySelector('#settings-section .btn-group .btn.active');
        if (activeButton) {
            const icon = activeButton.querySelector('i');
            if (icon) {
                const modeMap = {
                    'bi-person-walking': 'Walking',
                    'fa-person-walking-with-cane': 'Walking with cane',
                    'bi-bicycle': 'Cycling',
                    'bi-train-front': 'Public transport'
                };
                
                const modeClass = Array.from(icon.classList).find(cls => 
                    modeMap[cls] !== undefined
                );
                
                selectedModeElement.textContent = modeClass ? modeMap[modeClass] : 'Walking';
            }
        }
    }
} 