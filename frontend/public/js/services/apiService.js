export class ApiService {
    static async fetchPlaces(query) {
        try {
            const response = await fetch('/api/reverse_geocoding', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: query })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching places:', error);
            throw error;
        }
    }

    static async fetchIsochroneData(coordinates, minutes, velocity, categories = []) {
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
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
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

    static async getIsochroneParameters(coordinates, minutes, velocity, categories = []) {
        try {
            console.log('Fetching isochrone parameters with:', {
                coordinates,
                minutes,
                velocity,
                categories
            });

            const response = await fetch('/api/get_isochrone_parameters', {
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
                console.error('Server response for parameters:', errorText);
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Isochrone parameters response:', data);
            return data;
        } catch (error) {
            console.error('Error fetching isochrone parameters:', error);
            return {
                proximity_score: 0.2,
                density_score: 0.2,
                entropy_score: 0.2,
                poi_accessibility: 0.2
            };
        }
    }

    static async runSearch(coordinates, minutes, velocity, categories) {
        try {
            const isochroneData = await this.fetchIsochroneData(coordinates, minutes, velocity, categories);
            const poisData = await this.getPoisInIsochrone(coordinates, minutes, velocity, categories);
            const parametersData = await this.getIsochroneParameters(coordinates, minutes, velocity, categories);

            return {
                isochrone: isochroneData,
                pois: poisData,
                parameters: parametersData
            };
        } catch (error) {
            console.error('Error in search operation:', error);
            throw error;
        }
    }

    static async fetchAllNeighbourhoods(cityName = null) {
        try {
            let url = '/api/get_all_neighbourhoods';
            if (cityName) {
                url += `?city=${encodeURIComponent(cityName)}`;
            }
            
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error fetching neighbourhoods:', error);
            throw error;
        }
    }

    static async fetchNeighbourhoodsByCoordinates(coordinates) {
        try {
            const response = await fetch('/api/get_neighbourhoods_by_coordinates', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    lat: coordinates[0],
                    lon: coordinates[1]
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error fetching neighbourhoods by coordinates:', error);
            throw error;
        }
    }
}