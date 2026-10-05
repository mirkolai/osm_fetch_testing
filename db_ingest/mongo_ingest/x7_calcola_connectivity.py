import glob
import os
import re
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

import networkx as nx
import osmnx as ox
from pymongo import MongoClient, UpdateOne

from db_ingest import utils


"""
Calcola la connectivity come closeness centrality sui file GraphML OSM
(e.g. walk/bike) e salva i risultati in MongoDB.

Collezioni target:
- connectivity_walk
- connectivity_bike

Il calcolo viene eseguito SOLO se non esistono già risultati per
quel comune e quella modalità di trasporto.

Ogni documento contiene:

{
  "node_id": <int>,
  "city_code": <str>,
  "travel_mode": "walk" | "bike",
  "connectivity": {
        "closeness": <float>
  }
}
"""


def resolve_mode(file_path: str) -> Optional[str]:
    lower_name = os.path.basename(file_path).lower()

    if "bike" in lower_name:
        return "bike"

    if "walk" in lower_name:
        return "walk"

    return None


def extract_city_code(file_path: str) -> str:
    name = Path(file_path).name

    match = re.search(r"(\d{6})", name)

    if match:
        return match.group(1)

    stem = Path(file_path).stem

    return stem.split(" ")[0].split("_")[0]


def _file_priority(file_path: str) -> int:
    lower_name = os.path.basename(file_path).lower()

    if "extended" in lower_name:
        return 2

    return 1


def select_graphml_files(graphml_dir: str) -> Dict[Tuple[str, str], str]:

    candidates = sorted(
        glob.glob(
            os.path.join(
                graphml_dir,
                "*.graphml*"
            )
        )
    )

    selected: Dict[Tuple[str, str], str] = {}

    for path in candidates:

        mode = resolve_mode(path)

        if mode is None:
            continue

        city_code = extract_city_code(path)

        if not utils.should_process_city(city_code):
            continue

        key = (city_code, mode)

        if key not in selected:
            selected[key] = path
            continue

        old_path = selected[key]

        if _file_priority(path) > _file_priority(old_path):
            selected[key] = path

    return selected


def to_simple_weighted_graph(
    graph: nx.MultiDiGraph
) -> nx.Graph:

    base = (
        nx.DiGraph()
        if graph.is_directed()
        else nx.Graph()
    )

    # Mantiene per ogni arco il peso minimo
    # quando ci sono multi-archi.
    for u, v, data in graph.edges(data=True):

        weight = float(
            data.get("length", 1.0) or 1.0
        )

        if base.has_edge(u, v):

            if weight < float(
                base[u][v].get("weight", 1.0)
            ):
                base[u][v]["weight"] = weight

        else:

            base.add_edge(
                u,
                v,
                weight=weight
            )

    # Aggiunge anche eventuali nodi isolati.
    base.add_nodes_from(graph.nodes())

    return base


def iter_bulk_operations(
    city_code: str,
    mode: str,
    closeness_scores: Dict[int, float],
) -> Iterable[UpdateOne]:

    for node_id, score in closeness_scores.items():

        node_id_int = int(node_id)
        score_float = float(score)

        yield UpdateOne(
            {
                "city_code": city_code,
                "node_id": node_id_int,
            },
            {
                "$set": {
                    "node_id": node_id_int,
                    "city_code": city_code,
                    "travel_mode": mode,
                    "connectivity": {
                        "closeness": score_float,
                    },
                }
            },
            upsert=True,
        )


def connectivity_already_exists(
    collection,
    city_code: str,
    mode: str,
) -> bool:
    """
    Controlla se il calcolo della connectivity per
    quel comune e quella modalità è già presente.

    È sufficiente trovare un documento perché tutti
    i risultati di quel comune vengono scritti insieme
    al termine del calcolo.
    """

    return collection.find_one(
        {
            "city_code": city_code,
            "travel_mode": mode,
            "connectivity.closeness": {
                "$exists": True
            },
        },
        {
            "_id": 1
        }
    ) is not None


def main() -> None:

    graphml_dir = os.getenv(
        "GRAPHML_DIR",
        "db_ingest/graphml"
    )

    selected_files = select_graphml_files(
        graphml_dir
    )

    if not selected_files:

        print(
            f"Nessun GraphML trovato in {graphml_dir}"
        )

        return

    client = MongoClient(
        utils.CONNECTION_STRING
    )

    db = client[
        utils.MONGO_DB_NAME
    ]

    try:

        for (city_code, mode), path in sorted(
            selected_files.items()
        ):

            collection_name = (
                f"connectivity_{mode}"
            )

            collection = db[
                collection_name
            ]

            # Indice composto:
            # un nodo è unico all'interno del comune.
            collection.create_index(
                [
                    ("city_code", 1),
                    ("node_id", 1)
                ],
                unique=True
            )

            collection.create_index(
                "city_code"
            )

            # ---------------------------------------------------------
            # CONTROLLO: il calcolo esiste già?
            # ---------------------------------------------------------

            if connectivity_already_exists(
                collection,
                city_code,
                mode
            ):

                print(
                    f"[{city_code}][{mode}] "
                    f"Connectivity già presente -> SKIP"
                )

                continue

            # ---------------------------------------------------------
            # CALCOLO
            # ---------------------------------------------------------

            print(
                f"[{city_code}][{mode}] "
                f"Calcolo necessario."
            )

            print(
                f"[{city_code}][{mode}] "
                f"Carico grafo da {path}"
            )

            graph = ox.load_graphml(
                path
            )

            simple_graph = (
                to_simple_weighted_graph(
                    graph
                )
            )

            print(
                f"[{city_code}][{mode}] "
                f"Calcolo closeness centrality su "
                f"{simple_graph.number_of_nodes()} nodi"
            )

            # Closeness su grafi pesati:
            # distanza = somma dei pesi lungo
            # i cammini minimi.
            closeness_scores = (
                nx.closeness_centrality(
                    simple_graph,
                    distance="weight"
                )
            )

            # ---------------------------------------------------------
            # SALVATAGGIO
            # ---------------------------------------------------------

            operations = list(
                iter_bulk_operations(
                    city_code=city_code,
                    mode=mode,
                    closeness_scores=closeness_scores
                )
            )

            if operations:

                result = collection.bulk_write(
                    operations,
                    ordered=False
                )

                print(
                    f"[{city_code}][{mode}] "
                    f"salvataggio completato - "
                    f"matched={result.matched_count}, "
                    f"modified={result.modified_count}, "
                    f"upserted={len(result.upserted_ids)}"
                )

            else:

                print(
                    f"[{city_code}][{mode}] "
                    f"nessun nodo da salvare"
                )

        print(
            "Completato: connectivity calcolata "
            "e salvata su MongoDB."
        )

    finally:

        client.close()


if __name__ == "__main__":
    main()
