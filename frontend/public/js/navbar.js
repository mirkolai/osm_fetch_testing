document.addEventListener('DOMContentLoaded', function() {
    const navbarContainer = document.getElementById('navbar-container');
    if (navbarContainer) {
        navbarContainer.innerHTML = `
            <nav class="flex justify-between items-center bg-[#5E5D87] text-white p-4">
                <div class="font-bold text-lg">
                    UNITED-AND-CLOSE
                </div>
                <div class="links">
                    <a href="/" class="hover:text-gray-300">Home</a>
                    <a href="/search" class="hover:text-gray-300">Nearby search</a>
                    <a href="/discoverArea" class="hover:text-gray-300">Discover areas for you</a>
                    <a href="/compareAreas" class="hover:text-gray-300">Compare areas</a>
                </div>
            </nav>
        `;
    }
});