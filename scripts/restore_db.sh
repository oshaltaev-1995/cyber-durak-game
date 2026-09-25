#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 BACKUP_FILE NEW_DATABASE_NAME" >&2
  exit 2
fi

backup_file="$1"
target_database="$2"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${KIBA_COMPOSE_FILE:-$repo_root/docker-compose.yml}"

compose=(docker compose)
if [[ -n "${KIBA_COMPOSE_PROJECT_NAME:-}" ]]; then
  compose+=(--project-name "$KIBA_COMPOSE_PROJECT_NAME")
fi
if [[ -n "${KIBA_ENV_FILE:-}" ]]; then
  compose+=(--env-file "$KIBA_ENV_FILE")
fi
compose+=(-f "$compose_file")

if [[ ! -s "$backup_file" ]]; then
  echo "Backup does not exist or is empty: $backup_file" >&2
  exit 1
fi
if [[ ! "$target_database" =~ ^[a-zA-Z][a-zA-Z0-9_]*$ ]]; then
  echo "Target database name must be alphanumeric/underscore and start with a letter" >&2
  exit 2
fi

source_database="$("${compose[@]}" exec -T database sh -c 'printf %s "$POSTGRES_DB"')"
if [[ "$target_database" == "$source_database" ]]; then
  echo "Refusing to restore over the active Kiba database" >&2
  exit 1
fi

"${compose[@]}" exec -T database sh -c \
  'createdb --username="$POSTGRES_USER" "$1"' -- "$target_database"
"${compose[@]}" exec -T database sh -c \
  'pg_restore --exit-on-error --no-owner --no-acl --username="$POSTGRES_USER" --dbname="$1"' \
  -- "$target_database" <"$backup_file"

"${compose[@]}" exec -T database sh -c \
  'psql --username="$POSTGRES_USER" --dbname="$1" --tuples-only --command="SELECT version_num FROM alembic_version; SELECT count(*) FROM users; SELECT count(*) FROM completed_matches;"' \
  -- "$target_database"
echo "Restore completed into separate database: $target_database"
