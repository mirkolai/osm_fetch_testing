#!/usr/bin/env python3
"""
Script per aggiungere indici spaziali mancanti al database PostgreSQL.
Migliora le performance di query spaziali e query su nodes/edges.
"""

import os
import psycopg2
from pathlib import Path


def get_postgres_connection():
    """Crea una connessione PostgreSQL."""
    # Leggi le variabili d'ambiente
    postgres_url = (
        os.getenv("POSTGRES_URL_LOCAL") or 
        os.getenv("POSTGRES_URL") or 
        os.getenv("POSTGRES_URL_DOCKER")
    )
    
    if postgres_url:
        print(f"[DEBUG] Using PostgreSQL URL from env")
        return psycopg2.connect(postgres_url)
    
    print(f"[DEBUG] Using PostgreSQL connection parameters")
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "15minute"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
    )


def load_env():
    """Carica variabili d'ambiente da .env"""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def index_exists(cursor, index_name: str) -> bool:
    """Verifica se un indice esiste nel database."""
    cursor.execute(
        "SELECT 1 FROM pg_indexes WHERE indexname = %s",
        (index_name,)
    )
    return cursor.fetchone() is not None


def check_and_add_indexes():
    """Verifica gli indici e ne aggiunge di mancanti."""
    load_env()
    conn = get_postgres_connection()
    
    try:
        with conn.cursor() as cursor:
            print("\n=== Verifica e aggiunta indici spaziali ===\n")
            
            # Indici da creare
            indexes = [
                # Indice spaziale GIST su nodes.geom (per operatore <->)
                {
                    "name": "idx_nodes_geom",
                    "query": "CREATE INDEX idx_nodes_geom ON nodes USING GIST (geom);",
                    "description": "Indice GIST su nodes.geom per query spaziale (operatore <->)"
                },
                # Indice su nodes.network_mode (filtro comune)
                {
                    "name": "idx_nodes_network_mode",
                    "query": "CREATE INDEX idx_nodes_network_mode ON nodes (network_mode);",
                    "description": "Indice B-tree su nodes.network_mode per filtri"
                },
                # Indice su nodes.id + network_mode (compound per join)
                {
                    "name": "idx_nodes_id_network_mode",
                    "query": "CREATE INDEX idx_nodes_id_network_mode ON nodes (id, network_mode);",
                    "description": "Indice composto nodes(id, network_mode) per join efficienti"
                },
                # Indice su edges.source + network_mode (per pgr_drivingDistance)
                {
                    "name": "idx_edges_source_network_mode",
                    "query": "CREATE INDEX idx_edges_source_network_mode ON edges (source, network_mode);",
                    "description": "Indice composto edges(source, network_mode) per graph routing"
                },
                # Indice su edges.target + network_mode (per pgr_drivingDistance inverso)
                {
                    "name": "idx_edges_target_network_mode",
                    "query": "CREATE INDEX idx_edges_target_network_mode ON edges (target, network_mode);",
                    "description": "Indice composto edges(target, network_mode) per graph routing"
                },
                # Indice su edges.network_mode (filtro sulla rete)
                {
                    "name": "idx_edges_network_mode",
                    "query": "CREATE INDEX idx_edges_network_mode ON edges (network_mode);",
                    "description": "Indice B-tree su edges.network_mode per filtri sulla rete"
                },
            ]
            
            for idx_info in indexes:
                idx_name = idx_info["name"]
                idx_query = idx_info["query"]
                description = idx_info["description"]
                
                if index_exists(cursor, idx_name):
                    print(f"✓ ESISTE: {idx_name}")
                    print(f"  {description}")
                else:
                    try:
                        print(f"⏳ CREAZIONE: {idx_name}")
                        print(f"  {description}")
                        cursor.execute(idx_query)
                        conn.commit()
                        print(f"✓ CREATO: {idx_name}\n")
                    except psycopg2.Error as e:
                        conn.rollback()
                        print(f"✗ ERRORE nella creazione di {idx_name}:")
                        print(f"  {str(e)}\n")
            
            # Verifica indexes su tabelle critiche
            print("\n=== Riepilogo indici per tabella ===\n")
            
            for table in ["nodes", "edges"]:
                cursor.execute(
                    "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = %s ORDER BY indexname",
                    (table,)
                )
                rows = cursor.fetchall()
                print(f"Tabella '{table}': {len(rows)} indici")
                for idx_name, idx_def in rows:
                    print(f"  - {idx_name}")
                print()
            
            # Analisi veloce delle tabelle
            print("=== Analisi tabelle (ANALYZE) ===\n")
            for table in ["nodes", "edges"]:
                try:
                    print(f"⏳ ANALYZE su {table}...")
                    cursor.execute(f"ANALYZE {table};")
                    conn.commit()
                    print(f"✓ ANALYZE completato su {table}\n")
                except psycopg2.Error as e:
                    conn.rollback()
                    print(f"✗ Errore ANALYZE {table}: {str(e)}\n")
            
            print("=== Completato ===")
            
    finally:
        conn.close()


if __name__ == "__main__":
    check_and_add_indexes()
