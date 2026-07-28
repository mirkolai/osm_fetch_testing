-- Script per aggiungere indici spaziali mancanti al database PostgreSQL
-- Migliora le performance di query spaziali e routing

-- Indice GIST su nodes.geom per operatore <-> (distanza)
CREATE INDEX IF NOT EXISTS idx_nodes_geom ON nodes USING GIST (geom);

-- Indice B-tree su nodes.network_mode (filtro comune)
CREATE INDEX IF NOT EXISTS idx_nodes_network_mode ON nodes (network_mode);

-- Indice composto nodes(id, network_mode) per join efficienti
CREATE INDEX IF NOT EXISTS idx_nodes_id_network_mode ON nodes (id, network_mode);

-- Indice composto edges(source, network_mode) per pgr_drivingDistance
CREATE INDEX IF NOT EXISTS idx_edges_source_network_mode ON edges (source, network_mode);

-- Indice composto edges(target, network_mode) per graph routing inverso
CREATE INDEX IF NOT EXISTS idx_edges_target_network_mode ON edges (target, network_mode);

-- Indice B-tree su edges.network_mode (filtro sulla rete)
CREATE INDEX IF NOT EXISTS idx_edges_network_mode ON edges (network_mode);

-- Analizza le tabelle per aggiornare le statistiche del query planner
ANALYZE nodes;
ANALYZE edges;

-- Mostra gli indici creati
\echo ''
\echo '=== Indici su nodes ==='
SELECT indexname FROM pg_indexes WHERE tablename='nodes' ORDER BY indexname;

\echo ''
\echo '=== Indici su edges ==='
SELECT indexname FROM pg_indexes WHERE tablename='edges' ORDER BY indexname;
