// api-service.js
export class ApiService {
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
                    categories: categories  // Ora categories è già un array di stringhe
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Server response:', errorText);
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error in fetchIsochroneData:', error);
            throw error;
        }
    }

    static async getPoisInIsochrone(coordinates, minutes, velocity, categories = []) {
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
                    vel: velocity,
                    categories: categories
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