let currentSessionId = sessionStorage.getItem('session_id');
let selectedCategories = new Set();
let selectedCategoryObjects = {}; // Mappa categoria padre -> array di categorie figlio selezionate

function getCategoryLabel(categoryId) {
    return window.getCategoryLabelIt(categoryId);
}

// Crea una sessione sostitutiva e riporta l'utente al welcome se lo step è aperto fuori flusso.
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

// Definizione dei colori per gli stati
const COLORS = {
    NONE: '#e0e0e0',      // Grigio - nessuna selezione
    PARTIAL: '#764ba2',   // Viola scuro - selezione parziale
    ALL: '#483d8b'        // Blu scuro - tutte selezionate
};

const DOM = {
    categoriesContainer: document.getElementById('categories-container'),
    selectedBadges: document.getElementById('selected-badges'),
    selectedCategoriesDiv: document.getElementById('selected-categories'),
    btnNext: document.getElementById('btn-next'),
    errorMessage: document.getElementById('error-message'),
    travelTime: document.getElementById('travel-time'),
    travelMode: document.querySelector('input[name="travel-mode"]:checked')
};

// Recupera la tassonomia di categorie usata per costruire l'interfaccia gerarchica.
async function loadCategories() {
    try {
        const response = await fetch('/api/userstudy/categories');
        const data = await response.json();
        
        if (data.status !== 'success' || !data.categories) {
            throw new Error('Invalid categories response');
        }
        
        return data.categories;
    } catch (error) {
        console.error('Errore nel caricamento delle categorie:', error);
        showError('Errore nel caricamento delle categorie');
        return {};
    }
}

// Inizializza l'interfaccia caricando e renderizzando le categorie disponibili.
async function initializeCategories() {
    const categories = await loadCategories();
    renderCategories(categories);
}

// Costruisce dinamicamente la UI delle categorie padre/figlio con stato di selezione persistito in memoria.
function renderCategories(categories) {
    DOM.categoriesContainer.innerHTML = '';
    
    Object.entries(categories).forEach(([parentCategory, subCategories], categoryIndex) => {
        const categoryId = parentCategory;
        selectedCategoryObjects[categoryId] = [];
        
        // Crea il contenitore della categoria padre
        const categoryDiv = document.createElement('div');
        categoryDiv.className = 'category-group';
        
        const categoryHeader = document.createElement('div');
        categoryHeader.className = 'category-header';

        const selectAllCheckbox = document.createElement('input');
        selectAllCheckbox.type = 'checkbox';
        selectAllCheckbox.id = `select-all-category-${categoryIndex}`;
        selectAllCheckbox.className = 'select-all-checkbox';
        selectAllCheckbox.setAttribute('aria-label', `Seleziona tutte le sottocategorie di ${getCategoryLabel(parentCategory)}`);

        const selectAllLabel = document.createElement('label');
        selectAllLabel.htmlFor = selectAllCheckbox.id;
        selectAllLabel.className = 'select-all-label';
        selectAllLabel.textContent = 'Tutte';
        selectAllLabel.style.display = 'none';

        // Il bottone della categoria padre apre e chiude le sottocategorie.
        const button = document.createElement('button');
        button.className = 'category-parent-btn';
        button.type = 'button';
        button.dataset.categoryId = categoryId;
        button.setAttribute('aria-expanded', 'false');
        button.setAttribute('aria-label', `Mostra o nascondi le sottocategorie di ${getCategoryLabel(parentCategory)}`);
        button.style.backgroundColor = COLORS.NONE;
        button.style.color = '#333';
        
        // Formatta il nome della categoria padre
        const displayName = getCategoryLabel(parentCategory);
        
        const textSpan = document.createElement('span');
        textSpan.className = 'category-parent-label';
        textSpan.textContent = displayName;
        
        const toggleIcon = document.createElement('i');
        toggleIcon.className = 'bi bi-chevron-down category-toggle-icon';
        
        button.appendChild(textSpan);
        button.appendChild(toggleIcon);
        categoryHeader.appendChild(selectAllCheckbox);
        categoryHeader.appendChild(selectAllLabel);
        categoryHeader.appendChild(button);
        
        // Container per le sottocategorie (collassabile)
        const collapseDiv = document.createElement('div');
        collapseDiv.className = 'subcategories-collapse';
        collapseDiv.style.display = 'none';
        
        // Ogni sottocategoria aggiorna sia lo stato locale sia l'anteprima delle selezioni effettuate.
        subCategories.forEach(subCategory => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'subcategory-item';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `subcategory-${categoryIndex}-${collapseDiv.children.length}`;
            checkbox.value = subCategory;
            checkbox.className = 'category-checkbox';
            checkbox.dataset.parentCategory = categoryId;
            checkbox.style.cursor = 'pointer';
            
            const label = document.createElement('label');
            label.htmlFor = checkbox.id;
            label.textContent = getCategoryLabel(subCategory);
            label.style.fontWeight = '400';
            label.className = 'subcategory-label';
            
            checkbox.addEventListener('change', () => {
                // Aggiorna il fontWeight della label
                label.style.fontWeight = checkbox.checked ? '700' : '400';
                updateCategorySelection(categoryId, subCategory, checkbox.checked);
                updateParentButtonColor(categoryId, subCategories);
                updateSelectedBadges();
                updateNextButtonState();
            });
            
            itemDiv.appendChild(checkbox);
            itemDiv.appendChild(label);
            collapseDiv.appendChild(itemDiv);
        });
        
        // Il bottone padre apre e chiude il contenitore delle sottocategorie senza cambiare selezione.
        button.addEventListener('click', (e) => {
            e.preventDefault();
            const isVisible = collapseDiv.style.display !== 'none';
            collapseDiv.style.display = isVisible ? 'none' : 'block';
            button.setAttribute('aria-expanded', String(!isVisible));
            toggleIcon.style.transform = isVisible ? 'rotate(0deg)' : 'rotate(180deg)';
            toggleIcon.style.transition = 'transform 0.3s';
        });

        selectAllCheckbox.addEventListener('change', () => {
            const checkboxes = collapseDiv.querySelectorAll('.category-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.checked = selectAllCheckbox.checked;
                checkbox.nextElementSibling.style.fontWeight = selectAllCheckbox.checked ? '700' : '400';
                updateCategorySelection(categoryId, checkbox.value, selectAllCheckbox.checked);
            });

            updateParentButtonColor(categoryId, subCategories);
            updateSelectedBadges();
            updateNextButtonState();
        });
        
        categoryDiv.appendChild(categoryHeader);
        categoryDiv.appendChild(collapseDiv);
        DOM.categoriesContainer.appendChild(categoryDiv);
    });
}

// Sincronizza le strutture dati interne quando una sottocategoria viene selezionata o deselezionata.
function updateCategorySelection(parentCategory, subCategory, isChecked) {
    if (isChecked) {
        selectedCategories.add(subCategory);
        if (!selectedCategoryObjects[parentCategory]) {
            selectedCategoryObjects[parentCategory] = [];
        }
        if (!selectedCategoryObjects[parentCategory].includes(subCategory)) {
            selectedCategoryObjects[parentCategory].push(subCategory);
        }
    } else {
        selectedCategories.delete(subCategory);
        if (selectedCategoryObjects[parentCategory]) {
            selectedCategoryObjects[parentCategory] = selectedCategoryObjects[parentCategory].filter(cat => cat !== subCategory);
        }
    }
}

// Aggiorna il colore del pulsante padre per riflettere selezione nulla, parziale o completa.
function updateParentButtonColor(parentCategory, totalSubCategories) {
    const button = document.querySelector(`[data-category-id="${parentCategory}"]`);
    if (!button) return;
    
    const selectedCount = selectedCategoryObjects[parentCategory]?.length || 0;
    const totalCount = totalSubCategories.length;
    
    let color = COLORS.NONE;
    
    if (selectedCount === totalCount && selectedCount > 0) {
        color = COLORS.ALL;
    } else if (selectedCount > 0) {
        color = COLORS.PARTIAL;
    }
    
    button.style.backgroundColor = color;
    button.style.color = selectedCount > 0 ? 'white' : '#333';
    const selectAllCheckbox = button.closest('.category-group')?.querySelector('.select-all-checkbox');
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = selectedCount === totalCount && totalCount > 0;
        selectAllCheckbox.indeterminate = selectedCount > 0 && selectedCount < totalCount;
    }
    
    // Il checkmark rende immediatamente visibile che almeno una sottocategoria è attiva.
    //let checkmark = button.querySelector('.checkmark');
    //if (selectedCount > 0 && !checkmark) {
        //checkmark = document.createElement('i');
        //checkmark.className = 'bi bi-check-circle-fill checkmark';
        //checkmark.style.marginRight = '8px';
        //checkmark.style.color = 'white';
        //button.insertBefore(checkmark, button.firstChild);
    //} else if (selectedCount === 0 && checkmark) {
    //    checkmark.remove();
    //}
}

// Mostra l'elenco sintetico delle categorie selezionate nel box riepilogativo in basso.
function updateSelectedBadges() {
    DOM.selectedBadges.innerHTML = '';
    
    if (selectedCategories.size === 0) {
        DOM.selectedCategoriesDiv.classList.remove('show');
        return;
    }
    
    DOM.selectedCategoriesDiv.classList.add('show');
    
    Array.from(selectedCategories).forEach(category => {
        const badge = document.createElement('span');
        badge.className = 'category-badge';
        badge.textContent = getCategoryLabel(category);
        
        DOM.selectedBadges.appendChild(badge);
    });
}

// Abilita il passaggio successivo solo quando l'utente ha scelto almeno una categoria valida.
function updateNextButtonState() {
    const travelTime = document.getElementById('travel-time').value;
    const hasCategories = selectedCategories.size > 0;
    
    DOM.btnNext.disabled = !hasCategories || !travelTime;
}

// Event listener per cambio tempo di viaggio
document.getElementById('travel-time').addEventListener('change', updateNextButtonState);

// Event listener per bottone Avanti
DOM.btnNext.addEventListener('click', proceedToNextStep);

// Salva categorie, tempo e modalità di viaggio e porta l'utente allo step risultati.
async function proceedToNextStep() {
    const travelTime = parseInt(document.getElementById('travel-time').value);
    const travelMode = document.querySelector('input[name="travel-mode"]:checked').value;
    
    if (selectedCategories.size === 0) {
        showError('Seleziona almeno una categoria di servizi');
        return;
    }
    
    DOM.btnNext.disabled = true;
    DOM.btnNext.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Salvataggio...';
    
    try {
        const response = await fetch('/api/userstudy/categories/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                categories: Array.from(selectedCategories),
                travel_time: travelTime,
                travel_mode: travelMode
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            window.location.href = '/userstudy/results';
        } else {
            showError(`Errore: ${data.detail || 'Non è stato possibile salvare.'}`);
            DOM.btnNext.disabled = false;
            DOM.btnNext.innerHTML = 'Avanti <i class="bi bi-arrow-right ms-2"></i>';
        }
    } catch (error) {
        console.error('Errore:', error);
        showError('Errore di rete. Prova di nuovo.');
        DOM.btnNext.disabled = false;
        DOM.btnNext.innerHTML = 'Avanti <i class="bi bi-arrow-right ms-2"></i>';
    }
}

// Visualizza errori di validazione o rete nel contenitore dedicato del passo 4.
function showError(message) {
    DOM.errorMessage.textContent = message;
    DOM.errorMessage.style.display = 'block';
}

// Inizializza al caricamento
document.addEventListener('DOMContentLoaded', () => {
    initializeCategories();
});
