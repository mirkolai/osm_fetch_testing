export class ApiService {
    static async fetchPlaces(query) {
        const response = await fetch('/api/reverse_geocoding', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: query })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    }

    static async getPoisForNode(nodeId) {
        const response = await fetch('/api/test_get_data_pois_near_node', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ node_id: nodeId })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    }

    static async fetchIsochroneData(coordinates, minutes, velocity, categories = []) {
        console.log('Fetching isochrone with params:', {
            coordinates,
            minutes,
            velocity,
            categories
        });

        try {
            const response = await fetch('/api/get_isochrone', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    coords: {
                        lat: coordinates[0],
                        lon: coordinates[1]
                    },
                    min: minutes,
                    vel: velocity,
                    categories: categories
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Server response:', errorText);
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Isochrone data received:', data);
            return data;
        } catch (error) {
            console.error('Error in fetchIsochroneData:', error);
            throw error;
        }
    }

    static async getPoisInIsochrone(coordinates, minutes, velocity) {
        try {
            const response = await fetch('/api/get_pois_isochrone', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    coords: {
                        lat: coordinates[0],
                        lon: coordinates[1]
                    },
                    min: minutes,
                    vel: velocity
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error fetching POIs:', error);
            throw error;
        }
    }
}