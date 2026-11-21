#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p backups
STAMP=$(date +%Y%m%d_%H%M%S)

if docker ps --format '{{.Names}}' | grep -q '^empire-postgres$'; then
  docker exec empire-postgres pg_dump -U "${POSTGRES_USER:-empire_admin}" "${POSTGRES_DB:-autonomous_empire}" > "backups/postgres_${STAMP}.sql"
  echo "[OK] Dump PostgreSQL guardado em backups/postgres_${STAMP}.sql"
fi

if [ -f "empire_state.db" ]; then
  cp empire_state.db "backups/sqlite_${STAMP}.db"
  echo "[OK] Snapshot SQLite guardado em backups/sqlite_${STAMP}.db"
fi

zip -rq "backups/deployments_${STAMP}.zip" deployments/ 2>/dev/null || true
echo "[OK] Artefactos da Fábrica arquivados em backups/deployments_${STAMP}.zip"
