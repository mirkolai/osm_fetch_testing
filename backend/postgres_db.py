import os
from pathlib import Path
from typing import List, Optional

import psycopg2
from pydantic import BaseModel, Field


def _load_env_file():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


class PostgresPrecomputedMetricsRow(BaseModel):
    """Rappresenta una riga della tabella con metriche precompute per nodo/tempo/mode."""

    city_code: str
    neighbourhood_id: Optional[str] = None
    network_mode: str
    node_id: int
    travel_time: int
    category_primary_counts: List[int] = Field(default_factory=list)
    category_secondary_counts: List[int] = Field(default_factory=list)
    isochrone_area_km2: float = 0.0
    total_pois: int = 0
    proximity_value: Optional[float] = None


def get_postgres_connection():
    """Create a PostgreSQL connection for routing queries."""
    postgres_url = os.getenv("POSTGRES_URL") or os.getenv("POSTGRES_URL_DOCKER") or os.getenv("POSTGRES_URL_LOCAL")
    print(f"Using PostgreSQL URL: {postgres_url}")
    try:
        if postgres_url:
            return psycopg2.connect(postgres_url)

        return psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "15minute"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=os.getenv("POSTGRES_PORT", "5432"),
        )
    except psycopg2.Error as exc:
        print(f"Primary PostgreSQL connection failed: {exc}")
        print("Trying local PostgreSQL fallback at 127.0.0.1...")
        return psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "15minute"),
            user=os.getenv("POSTGRES_USER_LOCAL", os.getenv("POSTGRES_USER", "postgres")),
            password=os.getenv("POSTGRES_PASSWORD_LOCAL", os.getenv("POSTGRES_PASSWORD", "postgres")),
            host="127.0.0.1",
            port=os.getenv("POSTGRES_PORT_LOCAL", os.getenv("POSTGRES_PORT", "5432")),
        )
