
document.getElementById("fetchData").addEventListener("click", async () => {
    try {
        const response = await fetch("/api/osm_data");
        if (!response.ok) {
            throw new Error("Errore nel recupero dei dati!");
        }
        const data = await response.json();
        console.log(data);

        data.elements.forEach((element) => {
            if (element.type === "node") {
                L.marker([element.lat, element.lon]).addTo(map);
            }
        });
    } catch (error) {
        console.error("Errore:", error);
    }
});
