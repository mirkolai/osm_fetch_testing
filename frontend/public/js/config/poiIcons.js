// Icone Font Awesome per i POI, condivise dagli step 3 e 5 (esposte come global).
(function (root) {
    // Icone dedicate per categoria atomica (tassonomia Overture usata dal backend).
    const POI_ICONS_BY_CATEGORY = (() => {
        const groups = {
            'fa-solid fa-masks-theater': ['performing_arts_venue', 'event_venue', 'festival_venue', 'amusement_attraction'],
            'fa-solid fa-film': ['movie_theater', 'media_service'],
            'fa-solid fa-palette': ['arts_and_crafts_space', 'design_service'],
            'fa-solid fa-paw': ['animal_attraction', 'animal_or_pet_service'],
            'fa-solid fa-gamepad': ['gaming_venue'],
            'fa-solid fa-landmark': ['museum', 'government_office', 'civic_organization', 'historic_site', 'cultural_center'],
            'fa-solid fa-martini-glass-citrus': ['nightlife_venue', 'alcoholic_beverage_venue'],
            'fa-solid fa-tractor': ['rural_attraction', 'agricultural_service'],
            'fa-solid fa-flask': ['science_attraction', 'research_institute'],
            'fa-solid fa-people-group': ['social_club', 'social_or_community_service', 'family_service'],
            'fa-solid fa-person-praying': ['spiritual_advising', 'place_of_worship', 'religious_landmark', 'religious_retreat_or_center'],
            'fa-solid fa-futbol': ['stadium_arena', 'sport_team', 'sport_league', 'sport_or_recreation_club'],
            'fa-solid fa-ticket': ['ticket_office_or_booth'],
            'fa-solid fa-shield-halved': ['military_site', 'public_safety_service', 'security_service'],
            'fa-solid fa-building-columns': ['public_facility'],
            'fa-solid fa-bolt': ['public_utility', 'utility_energy_infrastructure'],
            'fa-solid fa-monument': ['memorial_site', 'built_feature'],
            'fa-solid fa-graduation-cap': ['place_of_learning'],
            'fa-solid fa-utensils': ['casual_eatery'],
            'fa-solid fa-mug-saucer': ['non_alcoholic_beverage_venue'],
            'fa-solid fa-mountain': ['land_feature', 'mountain_hut'],
            'fa-solid fa-binoculars': ['scenic_viewpoint'],
            'fa-solid fa-water': ['water_feature'],
            'fa-solid fa-stethoscope': ['medical_service', 'outpatient_care_facility'],
            'fa-solid fa-hospital': ['specialized_medical_facility'],
            'fa-solid fa-spa': ['personal_or_beauty_service', 'wellness_service'],
            'fa-solid fa-hotel': ['hotel', 'resort', 'inn', 'lodge', 'hostel', 'service_apartment'],
            'fa-solid fa-bed': ['bed_and_breakfast', 'private_lodging', 'retreat', 'ryokan', 'self_catering_accommodation'],
            'fa-solid fa-house-chimney': ['cabin', 'cottage', 'country_house', 'houseboat', 'housing_or_property_service', 'real_estate_service'],
            'fa-solid fa-campground': ['campground'],
            'fa-solid fa-briefcase': ['b2b_service', 'corporate_or_business_office', 'professional_service', 'legal_service'],
            'fa-solid fa-helmet-safety': ['building_or_construction_service', 'industrial_facility_or_service'],
            'fa-solid fa-seedling': ['environmental_or_ecological_service'],
            'fa-solid fa-bell-concierge': ['event_or_party_service', 'home_service', 'laundry_service'],
            'fa-solid fa-print': ['printing_service'],
            'fa-solid fa-key': ['rental_service'],
            'fa-solid fa-truck': ['shipping_or_delivery_service'],
            'fa-solid fa-warehouse': ['storage_facility', 'warehouse_club_store'],
            'fa-solid fa-wrench': ['technical_service', 'vehicle_service'],
            'fa-solid fa-tower-cell': ['telecommunications_service'],
            'fa-solid fa-cart-shopping': ['convenience_store', 'superstore', 'discount_store', 'market'],
            'fa-solid fa-store': ['department_store', 'specialty_store', 'kiosk', 'second_hand_store'],
            'fa-solid fa-shirt': ['fashion_and_apparel_store'],
            'fa-solid fa-car': ['vehicle_dealer'],
            'fa-solid fa-dumbbell': ['sport_or_fitness_facility'],
            'fa-solid fa-bicycle': ['recreational_equipment_rental'],
            'fa-solid fa-person-hiking': ['recreational_trail_or_path'],
            'fa-solid fa-plane': ['air_transport_facility_or_service'],
            'fa-solid fa-gas-pump': ['fueling_station'],
            'fa-solid fa-bus': ['ground_transport_facility_or_service'],
            'fa-solid fa-train': ['transport_interchange'],
            'fa-solid fa-ship': ['water_transport_facility_or_service'],
        };
        const map = {};
        Object.entries(groups).forEach(([icon, categories]) => {
            categories.forEach((category) => { map[category] = icon; });
        });
        return map;
    })();

    // Mappa le categorie dei POI alle icone usate nella visualizzazione su mappa.
    function getIconClassForCategory(category) {
        const normalizedCategory = category ? category.toLowerCase() : '';

        if (POI_ICONS_BY_CATEGORY[normalizedCategory]) {
            return POI_ICONS_BY_CATEGORY[normalizedCategory];
        }

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

        if (normalizedCategory.includes('active_life') ||
            normalizedCategory.includes('sports_and_fitness_instruction') ||
            normalizedCategory.includes('sports_and_recreation_venue')) {
            return 'fa-regular fa-futbol';
        }

        if (normalizedCategory.includes('pets') ||
            normalizedCategory.includes('pet_services') ||
            normalizedCategory.includes('veterinarian')) {
            return 'fa-solid fa-paw';
        }

        if (normalizedCategory.includes('education') ||
            normalizedCategory.includes('college_university') ||
            normalizedCategory.includes('educational_services') ||
            normalizedCategory.includes('school')) {
            return 'fa-solid fa-school';
        }

        if (normalizedCategory.includes('financial_service') ||
            normalizedCategory.includes('atms')) {
            return 'fa-solid fa-dollar-sign';
        }

        if (normalizedCategory.includes('retail') ||
            normalizedCategory.includes('beverage_store') ||
            normalizedCategory.includes('drugstore') ||
            normalizedCategory.includes('food') ||
            normalizedCategory.includes('meat_shop') ||
            normalizedCategory.includes('pharmacy') ||
            normalizedCategory.includes('seafood_market') ||
            normalizedCategory.includes('shopping') ||
            normalizedCategory.includes('water_store')) {
            return 'fa-solid fa-bag-shopping';
        }

        if (normalizedCategory.includes('health_and_medical') ||
            normalizedCategory.includes('ambulance') ||
            normalizedCategory.includes('hospital') ||
            normalizedCategory.includes('dentist') ||
            normalizedCategory.includes('doctor') ||
            normalizedCategory.includes('emergency_room') ||
            normalizedCategory.includes('urgent_care')) {
            return 'fa-solid fa-hospital';
        }

        if (normalizedCategory.includes('public_service_and_government') ||
            normalizedCategory.includes('children_hall') ||
            normalizedCategory.includes('civic_center') ||
            normalizedCategory.includes('community_center') ||
            normalizedCategory.includes('community_services') ||
            normalizedCategory.includes('family_service_center') ||
            normalizedCategory.includes('library') ||
            normalizedCategory.includes('police_department') ||
            normalizedCategory.includes('post_office') ||
            normalizedCategory.includes('railway_service')) {
            return 'fa-solid fa-landmark';
        }

        if (normalizedCategory.includes('religious_organization') ||
            normalizedCategory.includes('buddhist_temple') ||
            normalizedCategory.includes('church_cathedral') ||
            normalizedCategory.includes('hindu_temple') ||
            normalizedCategory.includes('mosque') ||
            normalizedCategory.includes('shinto_shrines') ||
            normalizedCategory.includes('sikh_temple') ||
            normalizedCategory.includes('synagogue') ||
            normalizedCategory.includes('temple')) {
            return 'fa-solid fa-person-praying';
        }

        if (normalizedCategory.includes('travel') ||
            normalizedCategory.includes('transportation')) {
            return 'fa-solid fa-plane';
        }

        if (normalizedCategory.includes('professional_services') ||
            normalizedCategory.includes('bike_repair_maintenance') ||
            normalizedCategory.includes('child_care_and_day_care') ||
            normalizedCategory.includes('community_gardens') ||
            normalizedCategory.includes('emergency_service') ||
            normalizedCategory.includes('laundry_services') ||
            normalizedCategory.includes('mailbox_center') ||
            normalizedCategory.includes('package_locker')) {
            return 'fa-solid fa-user-tie';
        }

        if (normalizedCategory.includes('structure_and_geography') ||
            normalizedCategory.includes('public_plaza') ||
            normalizedCategory.includes('attractions_and_activities') ||
            normalizedCategory.includes('park') ||
            normalizedCategory.includes('plaza')) {
            return 'fa-solid fa-monument';
        }

        return 'fa-solid fa-location-dot';
    }

    root.getIconClassForCategory = getIconClassForCategory;
})(window);
