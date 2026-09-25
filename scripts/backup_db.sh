#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${KIBA_COMPOSE_FILE:-$repo_root/docker-compose.yml}"
backup_dir="${KIBA_BACKUP_DIR:-$repo_root/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
output="${1:-$backup_dir/kiba-$timestamp.dump}"

if [[ -e "$output" ]]; then
  echo "Refusing to overwrite existing backup: $output" >&2
  exit 1
fi

mkdir -p "$(dirname "$output")"
temporary="$output.partial"
trap 'rm -f "$temporary"' EXIT

compose=(docker compose)
if [[ -n "${KIBA_COMPOSE_PROJECT_NAME:-}" ]]; then
  compose+=(--project-name "$KIBA_COMPOSE_PROJECT_NAME")
fi
if [[ -n "${KIBA_ENV_FILE:-}" ]]; then
  compose+=(--env-file "$KIBA_ENV_FILE")
fi
compose+=(-f "$compose_file")

"${compose[@]}" exec -T database sh -c \
  'pg_dump --format=custom --no-owner --no-acl --username="$POSTGRES_USER" "$POSTGRES_DB"' \
  >"$temporary"
test -s "$temporary"
mv "$temporary" "$output"
trap - EXIT
echo "$output"
