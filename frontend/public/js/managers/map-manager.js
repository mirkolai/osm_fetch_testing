export class MapManager {
    constructor(map) {
        this.map = map;
        this.isochroneLayer = null;
        this.poiMarkers = [];
    }

    clearPoiMarkers() {
        this.poiMarkers.forEach(marker => this.map.removeLayer(marker));
        this.poiMarkers = [];
    }

    getIconClassForCategory(category) {
        const normalizedCategory = category ? category.toLowerCase() : '';

        if (normalizedCategory.includes('automotive') ||
            normalizedCategory.includes('electric_vehicle')) {
            return 'fa-solid fa-car';
        }

        if (normalizedCategory.includes('eat_and_drink') ||
            normalizedCategory.includes('bar') ||
            normalizedCategory.includes('restaurant') ||
            normalizedCategory.includes('cafe')) {
            return 'fa-solid fa-wine-glass';
        }

        if (normalizedCategory.includes('arts_and_entertainment') ||
            normalizedCategory.includes('cinema') ||
            normalizedCategory.includes('music') ||
            normalizedCategory.includes('internet_cafe')) {
            return 'fa-solid fa-music';
        }

        if (normalizedCategory.includes('beauty_and_spa') ||
            normalizedCategory.includes('barber') ||
            normalizedCategory.includes('beauty_salon')) {
            return 'fa-solid fa-spa';
        }

        if(normalizedCategory.includes('active_life') ||
            normalizedCategory.includes('sports_and_fitness_instruction') ||
            normalizedCategory.includes('sports_and_recreation_venue')){
            return 'fa-regular fa-futbol';
        }

        if(normalizedCategory.includes('pets') ||
            normalizedCategory.includes('pet_services') ||
            normalizedCategory.includes('veterinarian')){
            return 'fa-solid fa-paw';
        }

        if(normalizedCategory.includes('education') ||
            normalizedCategory.includes('college_university') ||
            normalizedCategory.includes('educational_services') ||
            normalizedCategory.includes('school')){
            return 'fa-solid fa-school';
        }

        if(normalizedCategory.includes('financial_service') ||
            normalizedCategory.includes('atms')){
            return 'fa-solid fa-dollar-sign';
        }

        if(normalizedCategory.includes('retail') ||
            normalizedCategory.includes('beverage_store') ||
            normalizedCategory.includes('drugstore') ||
            normalizedCategory.includes('food') ||
            normalizedCategory.includes('meat_shop') ||
            normalizedCategory.includes('pharmacy') ||
            normalizedCategory.includes('seafood_market') ||
            normalizedCategory.includes('shopping') ||
            normalizedCategory.includes('water_store')){
            return 'fa-solid fa-school';
        }

        if(normalizedCategory.includes('public_service_and_government') ||
            normalizedCategory.includes('children_hall') ||
            normalizedCategory.includes('civic_center') ||
            normalizedCategory.includes('community_center') ||
            normalizedCategory.includes('community_services') ||
            normalizedCategory.includes('family_service_center') ||
            normalizedCategory.includes('library') ||
            normalizedCategory.includes('police_department') ||
            normalizedCategory.includes('post_office') ||
            normalizedCategory.includes('railway_service')){
            return 'fa-solid fa-landmark';
        }

        if(normalizedCategory.includes('religious_organization') ||
            normalizedCategory.includes('buddhist_temple') ||
            normalizedCategory.includes('church_cathedral') ||
            normalizedCategory.includes('hindu_temple') ||
            normalizedCategory.includes('mosque') ||
            normalizedCategory.includes('shinto_shrines') ||
            normalizedCategory.includes('sikh_temple') ||
            normalizedCategory.includes('synagogue') ||
            normalizedCategory.includes('temple')){
            return 'fa-solid fa-person-praying';
        }

        if(normalizedCategory.includes('travel') ||
            normalizedCategory.includes('transportation')){
            return 'fa-solid fa-plane';
        }

        if(normalizedCategory.includes('professional_services') ||
            normalizedCategory.includes('bike_repair_maintenance') ||
            normalizedCategory.includes('child_care_and_day_care') ||
            normalizedCategory.includes('community_gardens') ||
            normalizedCategory.includes('emergency_service') ||
            normalizedCategory.includes('laundry_services') ||
            normalizedCategory.includes('mailbox_center') ||
            normalizedCategory.includes('package_locker') ){
            return 'fa-solid fa-user-tie';
        }

        if(normalizedCategory.includes('structure_and_geography') ||
            normalizedCategory.includes('public_plaza')){
            return 'fa-solid fa-monument';
        }

        return null;
    }

    addPoiMarkers(pois) {
        this.clearPoiMarkers();

        if (!Array.isArray(pois)) {
            console.error('Expected an array of POIs, received:', typeof pois);
            return;
        }

        pois.forEach(poi => {
            if (!poi.location || !poi.location.coordinates) {
                console.warn('Invalid POI data:', poi);
                return;
            }

            const [lat, lon] = poi.location.coordinates;
            const primaryCategory = poi.categories?.primary || '';
            const iconClass = this.getIconClassForCategory(primaryCategory);

            let marker;

            if (iconClass) {
                const icon = L.divIcon({
                    html: `<i class="${iconClass}" style="color: #483d8b; font-size: 20px;"></i>`,
                    className: 'custom-div-icon',
                    iconSize: [30, 30],
                    iconAnchor: [15, 15]
                });

                marker = L.marker([lat, lon], { icon });
            } else {
                // Usa il circleMarker di default per le altre categorie
                marker = L.circleMarker([lat, lon], {
                    radius: 6,
                    fillColor: '#483d8b',
                    color: '#483d8b',
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8
                });
            }

            const popupContent = `
                <strong>${poi.names?.primary || 'Unknown'}</strong><br>
                Category: ${poi.categories?.primary || 'Not specified'}<br>
                Distance: ${poi.distance ? `${Math.round(poi.distance)}m` : 'N/A'}
            `;

            marker.bindPopup(popupContent);
            marker.addTo(this.map);
            this.poiMarkers.push(marker);
        });
    }

    updateIsochroneLayer(data) {
        console.log('Updating isochrone layer with data:', data);

        if (this.isochroneLayer) {
            this.map.removeLayer(this.isochroneLayer);
        }

        if (!data || !data.convex_hull || !data.convex_hull.coordinates) {
            console.error('Invalid isochrone data:', data);
            return;
        }

        try {
            const coordinates = data.convex_hull.coordinates[0].map(coord => [coord[1], coord[0]]);

            this.isochroneLayer = L.polygon(coordinates, {
                color: '#483d8b',
                fillColor: '#483d8b',
                fillOpacity: 0.3,
                weight: 2
            }).addTo(this.map);

            this.map.fitBounds(this.isochroneLayer.getBounds());
        } catch (error) {
            console.error('Error drawing isochrone:', error);
        }
    }
}