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

        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const event = new CustomEvent('service-changed', {
                    bubbles: true,
                    composed: true,
                    detail: {
                        id: e.target.id,
                        label: e.target.nextElementSibling.textContent.trim(),
                        checked: e.target.checked
                    }
                });
                this.dispatchEvent(event);
            });
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
            </style>
            <div class="pointOfInterest-toggle">
                <button class="pointOfInterest-button-custom" type="button">
                    ${title}
                </button>
            </div>
            <div class="pointOfInterest-collapse">
                <div class="pointOfInterest-body">
                    ${services.map(service => `
                        <div class="form-check">
                            <input class="form-check-input" 
                                   type="checkbox" 
                                   id="${service.id}">
                            <label class="form-check-label" for="${service.id}">
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