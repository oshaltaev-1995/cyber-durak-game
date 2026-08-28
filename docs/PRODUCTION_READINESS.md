# Kiba production-readiness contract

Phase 6A prepares, but does not deploy, Kiba for a small single-server public beta.

## Ready now

- Explicit `development`, `test`, and `production` environments. Production fails before startup
  for insecure cookies, local/wildcard URLs or hosts, development email mode, default database
  credentials, or incomplete SMTP configuration.
- Argon2id passwords and opaque server-side sessions. Only SHA-256 token digests are stored.
  Sessions have a 30-day absolute lifetime, 14-day idle lifetime, revocation, throttled last-seen
  writes, logout-all, and full revocation after password reset.
- One-use hashed email-verification (24 hours) and password-reset (30 minutes) tokens. Registration
  remains usable if delivery fails and verification never gates guest or account gameplay.
- Same-origin cookie-authenticated HTTP and WebSocket operation with explicit Origin policy,
  production trusted-host middleware, no broad CORS, request IDs, safe generic 500 responses,
  structured JSON production logging, and response security headers.
- `/health` is process liveness. `/ready` verifies PostgreSQL connectivity and returns 503 when the
  database cannot serve requests.
- Human-vs-Bot sessions and PvP rooms have configurable process-local inactivity cleanup.
- Locked non-root backend production image and Angular-to-unprivileged-nginx production image. The
  nginx contract includes SPA fallback, immutable hashed-asset caching, same-origin `/api` proxying,
  and WebSocket upgrade support.
- Named PostgreSQL production volume, standard `pg_dump`/`pg_restore` scripts, migration checks,
  dependency audits, and production image/config checks in CI.

## Mandatory one-worker constraint

Production must run **one backend process / one application worker**. The provided production image
pins Uvicorn to `--workers 1`. Active Human-vs-Bot games, PvP rooms, reconnect credentials, action
rate limits, and cleanup registries are process-local. Multiple workers are unsafe until a shared
active-session architecture exists. PostgreSQL stores accounts and completed progression only.

## Security model

- Browsers use an HTTP-only, SameSite=Lax cookie; production requires Secure cookies and HTTPS.
- State-changing browser requests and WebSocket upgrades require an allowed Origin in production.
- No permissive CORS middleware is enabled. Frontend, API, and WebSocket use one origin.
- The app uses the direct socket peer for rate-limit keys and does not trust arbitrary
  `X-Forwarded-For`. Phase 6B's reverse proxy must enforce IP limits at its trusted edge.
- HSTS belongs at the Phase 6B HTTPS reverse proxy and is intentionally absent from local HTTP.
- Logs never intentionally include passwords, hashes, cookies, raw tokens, reconnect credentials,
  hidden hands, or future draw order. Development email mode is the explicit exception that logs
  local token links; production validation forbids it.

## Email delivery

`EmailSender` isolates the application from vendors. Development uses a process-local outbox and
local link logging. Production uses generic SMTP configured by environment. A transient delivery
failure does not roll back registration; the user can retry from the profile.

## Backup and restore

```bash
./scripts/backup_db.sh
./scripts/restore_db.sh backups/kiba-YYYYMMDDTHHMMSSZ.dump kiba_restore_test
```

Restore requires a separate database name and refuses the active database. Remove a validated test
database explicitly with `dropdb`. Phase 6B must schedule daily backups, define retention, store
copies outside the running database volume/server where possible, and rehearse restores. Do not run
`docker compose down -v` in production unless permanent data destruction is intended.

## Safe release sequence

1. Back up PostgreSQL and verify the backup is non-empty.
2. Pull/build the new version.
3. Run `alembic upgrade head` once as an explicit release step.
4. Start/restart the single backend worker and frontend proxy.
5. Verify `/health` and `/ready`.
6. Smoke-test frontend, auth, a guest game, and private PvP.

Production startup does not run Alembic automatically. Destructive downgrade is never a production
release step.

## Phase 6B deployment requirements

- domain, DNS, TLS certificate, HTTPS reverse proxy, and HSTS;
- real SMTP credentials and a unique production database password;
- automated backup schedule/retention and off-host storage;
- log retention, uptime/readiness monitoring, and restart maintenance communication.

## Known public-beta limitations

- Backend restart loses unfinished games and rooms.
- Exactly one backend worker; no automated failover or multi-node scaling.
- Rate limits reset on restart and require reverse-proxy reinforcement.
- No active-game persistence, Redis/shared room store, matchmaking/rating, or anti-farming controls.
- No automatic offsite backup implementation in this repository.
- A minimal privacy, terms, and account-deletion review remains required before broad launch.
