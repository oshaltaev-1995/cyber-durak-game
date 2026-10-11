#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$repo_root/docker-compose.prod.yml"

required_env=(
  KIBA_POSTGRES_DB=kiba
  KIBA_POSTGRES_USER=kiba
  KIBA_POSTGRES_PASSWORD=ci-safe-password
  KIBA_DATABASE_URL=postgresql+psycopg://kiba:ci-safe-password@database:5432/kiba
  KIBA_PUBLIC_BASE_URL=https://kiba.example.test
  KIBA_TRUSTED_HOSTS=kiba.example.test
  KIBA_CSRF_TRUSTED_ORIGINS=https://kiba.example.test
  KIBA_SMTP_HOST=smtp.example.test
  KIBA_SMTP_USERNAME=ci
  KIBA_SMTP_PASSWORD=ci-safe-password
  KIBA_SMTP_FROM=no-reply@example.test
  KIBA_MULTIPLAYER_3_4_ENABLED=true
  KIBA_DECK_VARIANTS_ENABLED=true
)

validate_rendered_flags() {
  local state="$1"
  local expected="$2"
  local -a mixed_env=(-u KIBA_MIXED_ROOMS_ENABLED)

  if [[ "$state" != absent ]]; then
    mixed_env=("KIBA_MIXED_ROOMS_ENABLED=$state")
  fi

  env "${mixed_env[@]}" "${required_env[@]}" \
    docker compose -f "$compose_file" config --format json |
    python3 -c '
import json
import sys

config = json.load(sys.stdin)
environment = config["services"]["backend"]["environment"]
expected = sys.argv[1]

assert environment["KIBA_MIXED_ROOMS_ENABLED"] == expected
assert environment["KIBA_MULTIPLAYER_3_4_ENABLED"] == "true"
assert environment["KIBA_DECK_VARIANTS_ENABLED"] == "true"
' "$expected"

  printf 'mixed=%s -> %s; multiplayer=true; deck_variants=true\n' "$state" "$expected"
}

mapping_count="$(grep -c '^[[:space:]]*KIBA_MIXED_ROOMS_ENABLED:' "$compose_file")"
if [[ "$mapping_count" -ne 1 ]]; then
  printf 'Expected exactly one backend mixed-room mapping, found %s\n' "$mapping_count" >&2
  exit 1
fi

validate_rendered_flags absent false
validate_rendered_flags false false
validate_rendered_flags true true
