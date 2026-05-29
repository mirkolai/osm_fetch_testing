CREATE TABLE IF NOT EXISTS nodes (
    id BIGINT NOT NULL,
    network_mode TEXT NOT NULL DEFAULT 'walk',
    x DOUBLE PRECISION,
    y DOUBLE PRECISION,
    geom geometry(POINT, 4326),
    PRIMARY KEY (network_mode, id)
);

CREATE TABLE IF NOT EXISTS edges (
    id BIGSERIAL PRIMARY KEY,
    network_mode TEXT NOT NULL DEFAULT 'walk',
    source BIGINT NOT NULL,
    target BIGINT NOT NULL,
    cost DOUBLE PRECISION NOT NULL,
    geom geometry(LINESTRING, 4326)
);

CREATE TABLE IF NOT EXISTS node_poi (
    id BIGSERIAL PRIMARY KEY,
    network_mode TEXT NOT NULL DEFAULT 'walk',
    node_id BIGINT NOT NULL,
    poi_id TEXT NOT NULL,
    distance_m DOUBLE PRECISION,
    UNIQUE (network_mode, node_id, poi_id)
);

ALTER TABLE nodes ADD COLUMN IF NOT EXISTS network_mode TEXT NOT NULL DEFAULT 'walk';
ALTER TABLE edges ADD COLUMN IF NOT EXISTS network_mode TEXT NOT NULL DEFAULT 'walk';
ALTER TABLE node_poi ADD COLUMN IF NOT EXISTS network_mode TEXT NOT NULL DEFAULT 'walk';

CREATE INDEX IF NOT EXISTS idx_nodes_mode_id ON nodes(network_mode, id);
CREATE INDEX IF NOT EXISTS idx_nodes_geom ON nodes USING GIST(geom);

CREATE INDEX IF NOT EXISTS idx_edges_mode_source ON edges(network_mode, source);
CREATE INDEX IF NOT EXISTS idx_edges_mode_target ON edges(network_mode, target);

CREATE INDEX IF NOT EXISTS idx_node_poi_mode_node ON node_poi(network_mode, node_id);
CREATE INDEX IF NOT EXISTS idx_node_poi_poi ON node_poi(poi_id);
