from typing import Union, Tuple

from pydantic import BaseModel

from backend.postgres_db import get_postgres_connection
import logging
logging.basicConfig(
    #level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class Coordinates(BaseModel):
    lat: float
    lon: float


def _resolve_network_mode(travel_mode: str) -> str:
    normalized_mode = (travel_mode or "walking").strip().lower()
    if normalized_mode in {"bike", "bicycle", "cycling"}:
        return "bike"
    return "walk"


def get_id_node_by_coordinates(coordinates: Coordinates, travel_mode: str = "walking") -> Tuple[int, str, Union[int, None]]:
    """Restituisce il node_id più vicino sulla rete corretta per la modalità richiesta."""
    try:
        logging.info("get_id_node_by_coordinates 0")
        logging.info(coordinates)

        network_mode = _resolve_network_mode(travel_mode)
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM nodes
                    WHERE network_mode = %s
                    ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                    LIMIT 1
                    """,
                    (network_mode, coordinates.lon, coordinates.lat),
                )
                row = cursor.fetchone()
        finally:
            conn.close()

        logging.info(row)

        if row:
            return 200, "OK", int(row[0])

        logging.info("Nodo non trovato!")
        return 404, "Nodo non trovato", None
    except Exception as e:
        print(e)
        return 500, f"Errore del server: {str(e)}", None
