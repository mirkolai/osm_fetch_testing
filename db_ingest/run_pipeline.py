"""Entry point unico per la pipeline di ingest dei database.

Fasi:
    phase1: scarica reti OSM e POI Overture
    phase2: popola MongoDB e calcola i dati derivati geografici
    phase3: popola PostgreSQL e genera le metriche precompute
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

PHASES = {
    "phase1": [
        "db_ingest/x1_recupera_rete_città_da_OSM.py",
        "db_ingest/x2_recupera_PoI_da_Overture.py",
    ],
    "phase2": [
        "db_ingest/mongo_ingest/x3_salva_città.py",
        "db_ingest/mongo_ingest/x4_salva_quartieri.py",
        "db_ingest/mongo_ingest/x5_salva_incroci.py",
        "db_ingest/mongo_ingest/x6_salva_PoIs.py",
        "db_ingest/mongo_ingest/x7_calcola_connectivity.py",
    ],
    "phase3": [
        "db_ingest/postgres_ingest/x8_ingest_network.py",
        "db_ingest/postgres_ingest/x9_map_pois_to_nodes.py",
        "db_ingest/postgres_ingest/x10_precompute_metrics_rows.py",
        "db_ingest/postgres_ingest/x11_precompute_metric_ranges.py",
        "db_ingest/postgres_ingest/x12_add_spatial_indexes.py",
    ],
}


def run_phase(name: str) -> None:
    child_env = os.environ.copy()
    project_path = str(ROOT)
    current_python_path = child_env.get("PYTHONPATH")
    child_env["PYTHONPATH"] = (
        f"{project_path}{os.pathsep}{current_python_path}"
        if current_python_path
        else project_path
    )

    # Il runner viene eseguito dall'host: i nomi Docker come "postgres"
    # sono risolvibili solo dentro la rete Docker Compose.
    child_env.pop("POSTGRES_URL", None)
    if child_env.get("POSTGRES_URL_LOCAL"):
        child_env["POSTGRES_URL"] = child_env["POSTGRES_URL_LOCAL"]
    child_env.pop("MONGO_URL", None)
    if child_env.get("MONGO_URL_LOCAL"):
        child_env["MONGO_URL"] = child_env["MONGO_URL_LOCAL"]

    for relative_path in PHASES[name]:
        script_path = ROOT / relative_path
        print(f"\n[pipeline] {name}: {relative_path}", flush=True)
        subprocess.run(
            [sys.executable, str(script_path)],
            cwd=ROOT,
            env=child_env,
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Esegue la pipeline di ingest in tre fasi")
    parser.add_argument(
        "phase",
        nargs="?",
        default="all",
        choices=["phase1", "phase2", "phase3", "all"],
        help="fase da eseguire; senza argomenti esegue tutte le fasi",
    )
    args = parser.parse_args()

    phases = list(PHASES) if args.phase == "all" else [args.phase]
    for phase in phases:
        run_phase(phase)


if __name__ == "__main__":
    main()