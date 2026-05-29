#!/bin/bash
set -e

DUMP_FILE="/docker-entrypoint-initdb.d/backup/15minute_data.sql"

if [ ! -f "$DUMP_FILE" ]; then
    echo "[postgres-init] Nessun dump trovato in $DUMP_FILE, skip restore"
    exit 0
fi

echo "[postgres-init] Import dump PostgreSQL da $DUMP_FILE"
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$DUMP_FILE"
echo "[postgres-init] Restore completato"
