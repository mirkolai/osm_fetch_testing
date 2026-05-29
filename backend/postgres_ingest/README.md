# PostgreSQL Routing Ingest

Questa cartella contiene script di ingest per popolare PostgreSQL/PostGIS+pgRouting
con rete stradale e mapping POI->nodo, senza dipendere da `borgesan`.

## Prerequisiti

- PostgreSQL con estensioni `postgis` e `pgrouting` abilitate.
- Collezione MongoDB `pois` valorizzata (campo `pois_id` e `location`).
- File GraphML disponibili in una directory, con nomi che contengono `walk` o `bike`.

## Variabili ambiente

- `POSTGRES_URL` (es. `postgresql://postgres:postgres@localhost:5432/15minute`)
- `MONGO_URL` (es. `mongodb://user:pass@localhost:27017`)
- `MONGO_DB` (default: `15minute`)
- `GRAPHML_DIR` (default: `postgres_init/graphml`)

## Esecuzione

1. Ingest rete (nodi+archi):

```bash
python backend/postgres_ingest/ingest_network.py
```

2. Mapping POI al nodo piu vicino (per walk e bike):

```bash
python backend/postgres_ingest/map_pois_to_nodes.py
```
