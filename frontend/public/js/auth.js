class AuthManager {
    constructor() {
        this.tokenKey = 'access_token';
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.checkAuthStatus();
    }

    setupEventListeners() {
        document.getElementById('show-login-btn')?.addEventListener('click', () => {
            this.showLoginForm();
        });

        document.getElementById('show-register-btn')?.addEventListener('click', () => {
            this.showRegisterForm();
        });

        document.getElementById('back-to-buttons')?.addEventListener('click', () => {
            this.showAuthButtons();
        });

        document.getElementById('back-to-buttons-register')?.addEventListener('click', () => {
            this.showAuthButtons();
        });

        document.getElementById('login-form-element')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleLogin();
        });

        document.getElementById('register-form-element')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleRegister();
        });

        document.getElementById('logout-btn')?.addEventListener('click', () => {
            this.logout();
        });
    }

    async checkAuthStatus() {
        if (this.isAuthenticated()) {
            try {
                const user = await this.getCurrentUser();
                if (user) {
                    this.showWelcomeSection(user.email);
                } else {
                    this.logout();
                }
            } catch (error) {
                console.error('Error checking auth status:', error);
                this.logout();
            }
        } else {
            this.showAuthButtons();
        }
    }

    isAuthenticated() {
        return localStorage.getItem(this.tokenKey) !== null;
    }

    getToken() {
        return localStorage.getItem(this.tokenKey);
    }

    async register(email, password) {
        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email, password })
            });

            if (response.ok) {
                return await response.json();
            } else {
                const error = await response.json();
                let errorMessage = 'Registration failed';
                
                if (error.detail) {
                    if (Array.isArray(error.detail)) {
                        errorMessage = error.detail.map(err => err.msg).join(', ');
                    } else if (typeof error.detail === 'string') {
                        errorMessage = error.detail;
                    }
                }
                
                throw new Error(errorMessage);
            }
        } catch (error) {
            throw error;
        }
    }

    async login(email, password) {
        try {
            const response = await fetch('/api/auth/token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email, password })
            });

            if (response.ok) {
                const data = await response.json();
                localStorage.setItem(this.tokenKey, data.access_token);
                return data;
            } else {
                const error = await response.json();
                let errorMessage = 'Login failed';
                
                if (error.detail) {
                    if (Array.isArray(error.detail)) {
                        // Handle Pydantic validation errors
                        errorMessage = error.detail.map(err => err.msg).join(', ');
                    } else if (typeof error.detail === 'string') {
                        errorMessage = error.detail;
                    }
                }
                
                if (errorMessage === 'Incorrect email or password') {
                    errorMessage = 'Email o password non corrette';
                }
                
                throw new Error(errorMessage);
            }
        } catch (error) {
            throw error;
        }
    }

    async getCurrentUser() {
        try {
            const token = this.getToken();
            if (!token) return null;

            const response = await fetch('/api/auth/me', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                return await response.json();
            } else {
                return null;
            }
        } catch (error) {
            console.error('Error getting current user:', error);
            return null;
        }
    }

    async getUserPreferences() {
        try {
            const token = this.getToken();
            if (!token) return null;

            const response = await fetch('/api/auth/preferences', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                return await response.json();
            } else {
                return null;
            }
        } catch (error) {
            console.error('Error getting user preferences:', error);
            return null;
        }
    }

    logout() {
        localStorage.removeItem(this.tokenKey);
        this.showAuthButtons();
        this.notifyAuthStateChange();
    }

    async handleLogin() {
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        const errorDiv = document.getElementById('login-error');

        // Validate email in frontend
        if (!email.includes('@')) {
            this.showError('login-error', 'Inserisci un indirizzo email valido');
            return;
        }
        
        if (!email.includes('.') || email.split('@')[1].split('.').length < 2) {
            this.showError('login-error', 'Inserisci un indirizzo email valido');
            return;
        }

        try {
            await this.login(email, password);
            const user = await this.getCurrentUser();
            await this.showWelcomeSection(user.email);
            this.hideError('login-error');
            this.notifyAuthStateChange();
        } catch (error) {
            this.showError('login-error', error.message);
        }
    }

    async handleRegister() {
        const email = document.getElementById('register-email').value;
        const password = document.getElementById('register-password').value;
        const errorDiv = document.getElementById('register-error');
        const successDiv = document.getElementById('register-success');

        // Validate email in frontend
        if (!email.includes('@')) {
            this.hideSuccess('register-success');
            this.showError('register-error', 'Inserisci un indirizzo email valido');
            return;
        }
        
        if (!email.includes('.') || email.split('@')[1].split('.').length < 2) {
            this.hideSuccess('register-success');
            this.showError('register-error', 'Inserisci un indirizzo email valido');
            return;
        }

        // Validate password in frontend
        if (password.length < 6) {
            this.hideSuccess('register-success');
            this.showError('register-error', 'Password deve essere di almeno 6 caratteri');
            return;
        }
        
        if (password.length > 72) {
            this.hideSuccess('register-success');
            this.showError('register-error', 'Password non può essere più lunga di 72 caratteri');
            return;
        }

        try {
            await this.register(email, password);
            this.hideError('register-error');
            this.showSuccess('register-success', 'Registrazione completata! Ora puoi effettuare il login.');
            
            // Clear form
            document.getElementById('register-form-element').reset();
            
            // Switch to login form after 2 seconds
            setTimeout(() => {
                this.showLoginForm();
                this.hideSuccess('register-success');
            }, 2000);
        } catch (error) {
            this.hideSuccess('register-success');
            this.showError('register-error', error.message);
        }
    }

    showAuthButtons() {
        document.getElementById('auth-buttons').style.display = 'block';
        document.getElementById('login-form').style.display = 'none';
        document.getElementById('register-form').style.display = 'none';
        document.getElementById('welcome-section').style.display = 'none';
        document.getElementById('settings-section').style.display = 'none';
        document.getElementById('travel-settings-display').style.display = 'none';
        document.getElementById('selected-services-center').style.display = 'none';
        document.getElementById('logout-container').style.display = 'none';
    }

    showLoginForm() {
        document.getElementById('auth-buttons').style.display = 'none';
        document.getElementById('login-form').style.display = 'block';
        document.getElementById('register-form').style.display = 'none';
        document.getElementById('welcome-section').style.display = 'none';
        document.getElementById('settings-section').style.display = 'none';
        document.getElementById('travel-settings-display').style.display = 'none';
        document.getElementById('selected-services-center').style.display = 'none';
        document.getElementById('logout-container').style.display = 'none';
        this.hideError('login-error');
    }

    showRegisterForm() {
        document.getElementById('auth-buttons').style.display = 'none';
        document.getElementById('login-form').style.display = 'none';
        document.getElementById('register-form').style.display = 'block';
        document.getElementById('welcome-section').style.display = 'none';
        document.getElementById('settings-section').style.display = 'none';
        document.getElementById('travel-settings-display').style.display = 'none';
        document.getElementById('selected-services-center').style.display = 'none';
        document.getElementById('logout-container').style.display = 'none';
        this.hideError('register-error');
        this.hideSuccess('register-success');
    }

    async showWelcomeSection(email) {
        document.getElementById('auth-buttons').style.display = 'none';
        document.getElementById('login-form').style.display = 'none';
        document.getElementById('register-form').style.display = 'none';
        document.getElementById('welcome-section').style.display = 'block';
        document.getElementById('settings-section').style.display = 'none';
        document.getElementById('travel-settings-display').style.display = 'block';
        document.getElementById('selected-services-center').style.display = 'block';
        document.getElementById('logout-container').style.display = 'block';
        document.getElementById('welcome-message').textContent = `Welcome ${email}`;
        
        // Load and apply user preferences
        await this.loadUserPreferences();
    }

    showError(elementId, message) {
        const errorDiv = document.getElementById(elementId);
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }

    hideError(elementId) {
        const errorDiv = document.getElementById(elementId);
        errorDiv.style.display = 'none';
    }

    showSuccess(elementId, message) {
        const successDiv = document.getElementById(elementId);
        successDiv.textContent = message;
        successDiv.style.display = 'block';
    }

    hideSuccess(elementId) {
        const successDiv = document.getElementById(elementId);
        successDiv.style.display = 'none';
    }

    async loadUserPreferences() {
        try {
            const preferences = await this.getUserPreferences();
            if (preferences) {
                this.applyUserPreferences(preferences);
            }
        } catch (error) {
            console.error('Error loading user preferences:', error);
        }
    }

    applyUserPreferences(preferences) {
        // time
        const timeSelect = document.querySelector('.time-select');
        if (timeSelect) {
            timeSelect.value = `${preferences.min} min`;
        }

        // travel mode
        const velocityToButton = {
            3: 'fa-person-walking-with-cane',   
            5: 'bi-person-walking',          
            12: 'bi-bicycle',                 
            20: 'bi-train-front'               
        };

        const travelModeButtons = document.querySelectorAll('#settings-section .btn-group .btn');
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

        if (preferences.categories && preferences.categories.length > 0) {
            this.selectServices(preferences.categories);
        }

        this.updateTravelSettingsDisplay();
    }

    selectServices(categoryIds) {
        document.querySelectorAll('service-category').forEach(category => {
            const checkboxes = category.shadowRoot.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(checkbox => {
                checkbox.checked = false;
                checkbox.dispatchEvent(new Event('change'));
            });
        });

        document.querySelectorAll('service-category').forEach(category => {
            const checkboxes = category.shadowRoot.querySelectorAll('input[type="checkbox"]');
            const mainCategoryCheckbox = checkboxes[0]; // main
            const subCategoryCheckboxes = Array.from(checkboxes).slice(1); // sub
            
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

    updateTravelSettingsDisplay() {
        const selectedTimeElement = document.getElementById('selected-time');
        const selectedModeElement = document.getElementById('selected-mode');
        
        const timeSelect = document.querySelector('.time-select');
        if (selectedTimeElement && timeSelect) {
            selectedTimeElement.textContent = timeSelect.value;
        }
        
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

    notifyAuthStateChange() {
        window.dispatchEvent(new CustomEvent('authStateChanged'));
    }
}
 // inizializza l'auth manager quando il DOM è caricato
document.addEventListener('DOMContentLoaded', function() {
    new AuthManager();
});
