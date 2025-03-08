class ServiceCategory extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
    }

    static get observedAttributes() {
        return ['title', 'services'];
    }

    connectedCallback() {
        this.render();
        this.setupEventListeners();
    }

    setupEventListeners() {
        const button = this.shadowRoot.querySelector('button');
        const checkboxes = this.shadowRoot.querySelectorAll('input[type="checkbox"]');

        button.addEventListener('click', () => {
            const collapse = this.shadowRoot.querySelector('.pointOfInterest-collapse');
            collapse.classList.toggle('show');
        });

        const mainCategoryName = this.getAttribute('title').toLowerCase().replace(/\s+/g, '_');
        const mainCheckbox = checkboxes[0];

        checkboxes.forEach((checkbox, idx) => {
            checkbox.dataset.index = idx;
        });

        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {

                const index = parseInt(e.target.dataset.index);
                const isChecked = e.target.checked;

                if (index === 0 && isChecked) {
                    this.selectAllCheckboxes();
                } else if (index === 0 && !isChecked) {
                    this.deselectAllCheckboxes();
                } else if (index > 0) {
                    if (!isChecked) {
                        this.deselectMainCategory();
                        this.deselectAllSubcategories();
                    } else {
                        this.updateMainCategoryState();
                    }
                }

                const event = new CustomEvent('service-changed', {
                    bubbles: true,
                    composed: true,
                    detail: {
                        id: e.target.id,
                        label: e.target.nextElementSibling.textContent.trim(),
                        checked: e.target.checked,
                        isMainCategory: index === 0,
                        isFromSelectAll: index === 0 && isChecked
                    }
                });
                this.dispatchEvent(event);
            });
        });
    }

    updateMainCategoryState() {
        const checkboxes = this.shadowRoot.querySelectorAll('input[type="checkbox"]');
        const mainCheckbox = checkboxes[0];
        const subcategoryCheckboxes = Array.from(checkboxes).slice(1); // Tutte tranne la prima

        const allSubcategoriesChecked = subcategoryCheckboxes.every(cb => cb.checked);

        if (allSubcategoriesChecked && !mainCheckbox.checked) {

            mainCheckbox.checked = true;

            const event = new CustomEvent('service-changed', {
                bubbles: true,
                composed: true,
                detail: {
                    id: mainCheckbox.id,
                    label: mainCheckbox.nextElementSibling.textContent.trim(),
                    checked: true,
                    isMainCategory: true
                }
            });
            this.dispatchEvent(event);
        }
    }

    deselectMainCategory() {
        const mainCheckbox = this.shadowRoot.querySelector('input[type="checkbox"][data-index="0"]');
        if (mainCheckbox && mainCheckbox.checked) {
            mainCheckbox.checked = false;

            const event = new CustomEvent('service-changed', {
                bubbles: true,
                composed: true,
                detail: {
                    id: mainCheckbox.id,
                    label: mainCheckbox.nextElementSibling.textContent.trim(),
                    checked: false,
                    isMainCategory: true
                }
            });
            this.dispatchEvent(event);
        }
    }

    selectAllCheckboxes() {
        const checkboxes = this.shadowRoot.querySelectorAll('input[type="checkbox"]');

        checkboxes.forEach((checkbox) => {
            const index = parseInt(checkbox.dataset.index);
            if (index > 0 && !checkbox.checked) {
                checkbox.checked = true;

                const event = new CustomEvent('service-changed', {
                    bubbles: true,
                    composed: true,
                    detail: {
                        id: checkbox.id,
                        label: checkbox.nextElementSibling.textContent.trim(),
                        checked: true,
                        isFromSelectAll: true
                    }
                });
                this.dispatchEvent(event);
            }
        });
    }

    deselectAllSubcategories() {
        const checkboxes = this.shadowRoot.querySelectorAll('input[type="checkbox"]');

        checkboxes.forEach((checkbox) => {
            const index = parseInt(checkbox.dataset.index);
            if (index > 0 && checkbox.checked) {
                checkbox.checked = false;

                const event = new CustomEvent('service-changed', {
                    bubbles: true,
                    composed: true,
                    detail: {
                        id: checkbox.id,
                        label: checkbox.nextElementSibling.textContent.trim(),
                        checked: false,
                        isFromSelectAll: true
                    }
                });
                this.dispatchEvent(event);
            }
        });
    }

    deselectAllCheckboxes() {
        const checkboxes = this.shadowRoot.querySelectorAll('input[type="checkbox"]');

        checkboxes.forEach((checkbox) => {
            const index = parseInt(checkbox.dataset.index);
            if (index > 0 && checkbox.checked) {
                checkbox.checked = false;

                const event = new CustomEvent('service-changed', {
                    bubbles: true,
                    composed: true,
                    detail: {
                        id: checkbox.id,
                        label: checkbox.nextElementSibling.textContent.trim(),
                        checked: false,
                        isFromSelectAll: true
                    }
                });
                this.dispatchEvent(event);
            }
        });
    }

    render() {
        const title = this.getAttribute('title');
        const services = JSON.parse(this.getAttribute('services') || '[]');

        this.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: block;
                }
                .pointOfInterest-toggle {
                    flex: 0 1 auto;
                }
                .pointOfInterest-button-custom {
                    background-color: #9966cc;
                    color: #fff;
                    border: none;
                    border-radius: 8px;
                    padding: 4px 7px;
                    font-size: 12px;
                    white-space: nowrap;
                    cursor: pointer;
                    text-align: center;
                }
                .pointOfInterest-button-custom:hover {
                    background-color: #483d8b;
                }
                .pointOfInterest-collapse {
                    display: none;
                    margin-top: 8px;
                }
                .pointOfInterest-collapse.show {
                    display: block;
                }
                .pointOfInterest-body {
                    padding: 4px 15px;
                    background-color: #fff;
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                }
                .form-check {
                    margin-bottom: 8px;
                }
                .form-check-input {
                    margin-right: 8px;
                }
                .form-check-label {
                    font-size: 14px;
                }
                .main-category {
                    font-weight: bold;
                }
            </style>
            <div class="pointOfInterest-toggle">
                <button class="pointOfInterest-button-custom" type="button">
                    ${title}
                </button>
            </div>
            <div class="pointOfInterest-collapse">
                <div class="pointOfInterest-body">
                    ${services.map((service, index) => `
                        <div class="form-check">
                            <input class="form-check-input" 
                                   type="checkbox" 
                                   id="${service.id}">
                            <label class="form-check-label ${index === 0 ? 'main-category' : ''}" for="${service.id}">
                                ${service.label}
                            </label>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
}

customElements.define('service-category', ServiceCategory);