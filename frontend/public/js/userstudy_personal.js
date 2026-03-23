let currentSessionId = sessionStorage.getItem('session_id');
let selectedCategories = new Set();
let selectedCategoryObjects = {}; // Mappa categoria padre -> array di categorie figlio selezionate

if (!currentSessionId) {
    alert('Errore: Session non trovata. Torna alla pagina di inizio.');
    window.location.href = '/userstudy/welcome';
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

// Carica le categorie da categories.json
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

async function initializeCategories() {
    const categories = await loadCategories();
    renderCategories(categories);
}

function renderCategories(categories) {
    DOM.categoriesContainer.innerHTML = '';
    
    Object.entries(categories).forEach(([parentCategory, subCategories]) => {
        const categoryId = parentCategory;
        selectedCategoryObjects[categoryId] = [];
        
        // Crea il contenitore della categoria padre
        const categoryDiv = document.createElement('div');
        categoryDiv.className = 'category-group';
        categoryDiv.style.marginBottom = '20px';
        categoryDiv.style.padding = '15px';
        categoryDiv.style.backgroundColor = '#f9f9f9';
        categoryDiv.style.borderRadius = '8px';
        
        // Bottone della categoria padre
        const button = document.createElement('button');
        button.className = 'category-parent-btn';
        button.type = 'button';
        button.dataset.categoryId = categoryId;
        button.style.width = '100%';
        button.style.padding = '12px 15px';
        button.style.marginBottom = '10px';
        button.style.border = '2px solid #ddd';
        button.style.borderRadius = '6px';
        button.style.backgroundColor = COLORS.NONE;
        button.style.color = '#333';
        button.style.fontWeight = '600';
        button.style.cursor = 'pointer';
        button.style.transition = 'all 0.3s';
        button.style.display = 'flex';
        button.style.justifyContent = 'space-between';
        button.style.alignItems = 'center';
        button.style.flexWrap = 'wrap';
        button.style.gap = '10px';
        
        // Formatta il nome della categoria padre
        const displayName = parentCategory
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
        
        const textSpan = document.createElement('span');
        textSpan.textContent = displayName;
        textSpan.style.flex = '1';
        textSpan.style.textAlign = 'left';
        textSpan.style.wordBreak = 'break-word';
        
        const toggleIcon = document.createElement('i');
        toggleIcon.className = 'bi bi-chevron-down';
        toggleIcon.style.fontSize = '14px';
        toggleIcon.style.flexShrink = '0';
        toggleIcon.style.marginLeft = '10px';
        
        button.appendChild(textSpan);
        button.appendChild(toggleIcon);
        
        // Container per le sottocategorie (collassabile)
        const collapseDiv = document.createElement('div');
        collapseDiv.className = 'subcategories-collapse';
        collapseDiv.style.display = 'none';
        collapseDiv.style.paddingTop = '10px';
        collapseDiv.style.borderTop = '1px solid #ddd';
        
        // Crea checkbox per ogni sottocategoria
        subCategories.forEach(subCategory => {
            const itemDiv = document.createElement('div');
            itemDiv.style.marginBottom = '8px';
            itemDiv.style.display = 'flex';
            itemDiv.style.alignItems = 'center';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = subCategory;
            checkbox.value = subCategory;
            checkbox.className = 'category-checkbox';
            checkbox.dataset.parentCategory = categoryId;
            checkbox.style.marginRight = '8px';
            checkbox.style.cursor = 'pointer';
            
            const label = document.createElement('label');
            label.htmlFor = subCategory;
            label.textContent = subCategory
                .split('_')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
            label.style.cursor = 'pointer';
            label.style.fontSize = '13px';
            label.style.marginBottom = '0';
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
        
        // Event listener per espansione/collasso
        button.addEventListener('click', (e) => {
            e.preventDefault();
            const isVisible = collapseDiv.style.display !== 'none';
            collapseDiv.style.display = isVisible ? 'none' : 'block';
            toggleIcon.style.transform = isVisible ? 'rotate(0deg)' : 'rotate(180deg)';
            toggleIcon.style.transition = 'transform 0.3s';
        });
        
        categoryDiv.appendChild(button);
        categoryDiv.appendChild(collapseDiv);
        DOM.categoriesContainer.appendChild(categoryDiv);
    });
}

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
    
    // Aggiungi o togli il checkmark
    let checkmark = button.querySelector('.checkmark');
    if (selectedCount > 0 && !checkmark) {
        checkmark = document.createElement('i');
        checkmark.className = 'bi bi-check-circle-fill checkmark';
        checkmark.style.marginRight = '8px';
        checkmark.style.color = 'white';
        button.insertBefore(checkmark, button.firstChild);
    } else if (selectedCount === 0 && checkmark) {
        checkmark.remove();
    }
}

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
        badge.textContent = category
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
        badge.style.display = 'inline-block';
        badge.style.backgroundColor = '#667eea';
        badge.style.color = 'white';
        badge.style.padding = '6px 12px';
        badge.style.borderRadius = '20px';
        badge.style.fontSize = '12px';
        badge.style.margin = '5px 5px 5px 0';
        
        DOM.selectedBadges.appendChild(badge);
    });
}

function updateNextButtonState() {
    const travelTime = document.getElementById('travel-time').value;
    const hasCategories = selectedCategories.size > 0;
    
    DOM.btnNext.disabled = !hasCategories || !travelTime;
}

// Event listener per cambio tempo di viaggio
document.getElementById('travel-time').addEventListener('change', updateNextButtonState);

// Event listener per bottone Avanti
DOM.btnNext.addEventListener('click', proceedToNextStep);

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

function showError(message) {
    DOM.errorMessage.textContent = message;
    DOM.errorMessage.style.display = 'block';
}

// Inizializza al caricamento
document.addEventListener('DOMContentLoaded', () => {
    initializeCategories();
});
