#!/usr/bin/env bash
# =============================================================================
# run_e2e_local.sh — Recette E2E PostgreSQL auto-portée (v6.1.1, audit P2-1)
# -----------------------------------------------------------------------------
# Édition Community. Lève PostgreSQL via le docker-compose du dépôt, bootstrappe
# le schéma Community, puis exécute tests/test_postgresql_community_e2e.py.
#
# Usage :
#   PGPASSWORD=corep_pwd ./scripts/run_e2e_local.sh
#   PGPASSWORD=corep_pwd KEEP_DB=1 ./scripts/run_e2e_local.sh
#
# Prérequis : docker + docker compose v2, et pip install -e ".[dev]" (pytest).
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${PGPASSWORD:?Définir PGPASSWORD (mot de passe PostgreSQL local), ex. export PGPASSWORD=corep_pwd}"
export PGUSER="${PGUSER:-corep_user}"
export PGDATABASE="${PGDATABASE:-corep_crr3}"
export PGPORT="${PGPORT:-5432}"
export PGHOST="${PGHOST:-localhost}"
export DATABASE_URL="postgresql://${PGUSER}:${PGPASSWORD}@${PGHOST}:${PGPORT}/${PGDATABASE}"
export RUN_POSTGRES_E2E="1"
export RUN_POSTGRES_E2E_RESET="${RUN_POSTGRES_E2E_RESET:-1}"

mkdir -p output

cleanup() {
  if [ "${KEEP_DB:-0}" != "1" ]; then
    echo "▶ Arrêt de la base de données (docker compose down)…"
    docker compose down -v >/dev/null 2>&1 || true
  else
    echo "▶ KEEP_DB=1 — la base reste active."
  fi
}
trap cleanup EXIT

echo "▶ Démarrage de PostgreSQL (service db)…"
docker compose up -d db

echo "▶ Attente de l'état healthy…"
for i in $(seq 1 30); do
  status="$(docker compose ps db --format '{{.Health}}' 2>/dev/null || echo '')"
  if [ "$status" = "healthy" ]; then echo "  base prête."; break; fi
  if [ "$i" = "30" ]; then echo "✗ Timeout : base non healthy." >&2; exit 1; fi
  sleep 2
done

echo "▶ Bootstrap du schéma Community…"
python -m corep_crr3.community_bootstrap 2>&1 | tee output/bootstrap.log

echo "▶ Exécution de la suite E2E PostgreSQL Community…"
python -m pytest -vv -s tests/test_postgresql_community_e2e.py 2>&1 | tee output/postgres_e2e.log

echo "✓ E2E PostgreSQL Community terminé. Journaux : output/bootstrap.log, output/postgres_e2e.log"
