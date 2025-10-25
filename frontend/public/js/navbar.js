document.addEventListener('DOMContentLoaded', function() { //caricato il dom
    const navbarContainer = document.getElementById('navbar-container');
    if (navbarContainer) {// se trova la navbar
        updateNavbar();
    }
});

function updateNavbar() { 
    const navbarContainer = document.getElementById('navbar-container'); //prende la navbar
    if (!navbarContainer) return;

    const isAuthenticated = localStorage.getItem('access_token') !== null; //controlla se è autenticato
    
    //decido cosa deve essere il pulsante di autenticazione
    let personalAreaLink = '';
    if (isAuthenticated) {
        personalAreaLink = `<a href="/personalArea" class="hover:text-gray-300">Area Personale</a>`;
    } else {
        personalAreaLink = `<a href="/personalArea" class="hover:text-gray-300">Accedi</a>`;
    }

    //html della navbar
    navbarContainer.innerHTML = `
        <nav class="flex justify-between items-center bg-[#5E5D87] text-white p-4">
            <div class="font-bold text-lg">
                UNITED-AND-CLOSE
            </div>
            <div class="links">
                <a href="/" class="hover:text-gray-300">Home</a>
                <a href="/search" class="hover:text-gray-300">Nearby search</a>
                <!-- <a href="/discoverArea" class="hover:text-gray-300">Discover areas for you</a> -->
                <a href="/compareAreas" class="hover:text-gray-300">Compare areas</a>
                ${personalAreaLink}
            </div>
        </nav>
    `;
}

// ai cambiamenti di access_token aggiorna la navbar
window.addEventListener('storage', function(e) {
    if (e.key === 'access_token') {
        updateNavbar();
    }
});

// ai cambiamenti di authStateChanged aggiorna la navbar
window.addEventListener('authStateChanged', function() {
    updateNavbar();
});