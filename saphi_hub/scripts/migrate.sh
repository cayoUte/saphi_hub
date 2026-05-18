#!/usr/bin/env bash
# Corre dentro del contenedor: docker compose exec api bash scripts/migrate.sh
set -euo pipefail
alembic upgrade head
echo "✓ Migraciones aplicadas"
