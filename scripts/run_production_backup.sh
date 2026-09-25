#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backup_dir="${KIBA_BACKUP_DIR:-/var/backups/kiba}"
retention_days="${KIBA_BACKUP_RETENTION_DAYS:-30}"

if [[ ! "$retention_days" =~ ^[0-9]+$ ]] || ((retention_days < 1)); then
  echo "KIBA_BACKUP_RETENTION_DAYS must be a positive integer" >&2
  exit 2
fi

umask 077
install -d -m 700 "$backup_dir"

backup="$($repo_root/scripts/backup_db.sh)"
test -s "$backup"

compose=(docker compose)
if [[ -n "${KIBA_COMPOSE_PROJECT_NAME:-}" ]]; then
  compose+=(--project-name "$KIBA_COMPOSE_PROJECT_NAME")
fi
if [[ -n "${KIBA_ENV_FILE:-}" ]]; then
  compose+=(--env-file "$KIBA_ENV_FILE")
fi
compose+=(-f "${KIBA_COMPOSE_FILE:-$repo_root/docker-compose.prod.yml}")

"${compose[@]}" exec -T database pg_restore --list <"$backup" >/dev/null
find "$backup_dir" -maxdepth 1 -type f -name 'kiba-*.dump' -mtime "+$retention_days" -delete

printf 'Kiba backup completed and verified: %s\n' "$backup"
