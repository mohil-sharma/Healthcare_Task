#!/usr/bin/env bash
# db.sh — manage the local PostgreSQL database (no Docker required)
# Usage:
#   ./db.sh start    — start the Postgres service (auto-starts on login too)
#   ./db.sh stop     — stop the Postgres service
#   ./db.sh setup    — create the 'healthcare' database and user (run once)
#   ./db.sh reset    — drop + recreate the database (destructive!)
#   ./db.sh status   — show whether Postgres is running
#   ./db.sh psql     — open an interactive psql session

set -euo pipefail

PG_VERSION="16"
PG_BIN="$(brew --prefix postgresql@${PG_VERSION})/bin"
DB_NAME="healthcare"
DB_USER="postgres"
DB_PASS="password"

# Ensure pg binaries are on PATH for this script
export PATH="${PG_BIN}:${PATH}"

cmd="${1:-help}"

case "$cmd" in
  start)
    echo "▶  Starting postgresql@${PG_VERSION}…"
    brew services start "postgresql@${PG_VERSION}"
    echo "✅  PostgreSQL is running on port 5432"
    ;;

  stop)
    echo "■  Stopping postgresql@${PG_VERSION}…"
    brew services stop "postgresql@${PG_VERSION}"
    ;;

  status)
    brew services info "postgresql@${PG_VERSION}"
    ;;

  setup)
    echo "🔧  Running first-time setup…"

    # Create the postgres superuser role if it doesn't exist
    psql postgres -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" \
      | grep -q 1 \
      || psql postgres -c "CREATE ROLE ${DB_USER} WITH SUPERUSER LOGIN PASSWORD '${DB_PASS}';"

    # Create the database if it doesn't exist
    psql postgres -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" \
      | grep -q 1 \
      || psql postgres -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

    echo "✅  Database '${DB_NAME}' ready."
    echo "    DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"
    ;;

  reset)
    read -r -p "⚠️  This will DROP and recreate '${DB_NAME}'. Continue? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }
    psql postgres -c "DROP DATABASE IF EXISTS ${DB_NAME};"
    psql postgres -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
    echo "✅  Database '${DB_NAME}' reset."
    ;;

  psql)
    psql -U "${DB_USER}" "${DB_NAME}"
    ;;

  help|*)
    echo "Usage: ./db.sh {start|stop|setup|reset|status|psql}"
    ;;
esac
