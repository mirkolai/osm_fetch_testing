import os

import psycopg2


def get_postgres_connection():
    """Create a PostgreSQL connection for routing queries."""
    postgres_url = os.getenv("POSTGRES_URL")
    if postgres_url:
        return psycopg2.connect(postgres_url)

    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "15minute"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=os.getenv("POSTGRES_PORT", "5432"),
    )
