# Kiba production deployment

This runbook describes the single-host public-beta deployment at `cyberdurak.com`. It deliberately
keeps Kiba isolated from the existing Kennel Operations and Husky Tracking stacks.

## Production contract

- Application checkout: `/opt/kiba/app`
- Secret environment: `/etc/kiba/production.env`, owned by `root:root`, mode `0600`
- Compose project: `kiba-production`
- Shared ingress network: existing external network `huskytracking_proxy`
- Kiba-private networks: application network plus an internal database network
- Database storage: Kiba-only named PostgreSQL volume
- Public host ports: none; existing Caddy is the sole listener on ports 80/443
- Backend: exactly one Uvicorn application worker
- Backups: `/var/backups/kiba`, root-only, daily, approximately 30-day retention
- Off-host disaster-recovery copy: **DEFERRED**

The environment file is never generated from the example by blindly overwriting the production
file. Existing values, especially SMTP settings, must be preserved. Inspect variable names only;
never print the file or its values into logs.

## Initial release

From the exact reviewed Git revision:

```bash
docker compose --env-file /etc/kiba/production.env -f docker-compose.prod.yml build backend
docker compose --env-file /etc/kiba/production.env -f docker-compose.prod.yml build frontend
docker compose --env-file /etc/kiba/production.env -f docker-compose.prod.yml up -d database
docker compose --env-file /etc/kiba/production.env -f docker-compose.prod.yml run --rm --no-deps backend alembic upgrade head
docker compose --env-file /etc/kiba/production.env -f docker-compose.prod.yml up -d backend frontend
```

Before changing Caddy, verify database, backend, and frontend health from their Docker networks,
confirm that Kiba publishes no host ports, and test same-origin `/api` proxying from the frontend.
The Caddy addition should route the complete `cyberdurak.com` origin to `kiba-frontend:8080` and
redirect `www` to the canonical apex. Nginx retains SPA fallback and proxies `/api` and WebSocket
upgrades to the backend. Validate the candidate Caddy configuration before an in-place reload; do
not restart Caddy. Immediately regression-test the Kennel and Husky public sites after reload.

## Release updates

1. Verify a current Kiba backup and its `pg_restore --list` integrity check.
2. Fetch the intended revision and verify the working tree is clean.
3. Build images serially and inspect Compose output.
4. Run `alembic upgrade head` explicitly once.
5. Recreate only Kiba application services; never operate on another Compose project.
6. Verify internal health, public HTTPS, API, WebSocket, authentication, legal pages, and gameplay.
7. Check container logs, resource headroom, backup timer, and existing production sites.

Never use `docker compose down -v` in production. Active games and PvP rooms are process-local, so
backend replacement terminates unfinished games and must be announced as maintenance.

## Backups and restore drill

`kiba-backup.timer` invokes `scripts/run_production_backup.sh`. The wrapper creates a mode-0700
directory, writes with a restrictive umask, verifies every dump with `pg_restore --list`, and
removes matching Kiba dumps older than the configured retention horizon. A failed service remains
visible through systemd failed-unit state and the journal.

Periodically restore a selected dump into a uniquely named temporary database using
`scripts/restore_db.sh`, inspect the schema/data counts without modifying production, then drop only
that temporary database. A local dump protects against application/database mistakes but not total
loss of the VPS or its storage. Adding an off-host copy is a post-launch follow-up.

## Rollback

- Keep PostgreSQL and its volume running.
- Return the checkout to the previously recorded release revision and rebuild/recreate only Kiba
  frontend/backend containers.
- Restore the backed-up Caddyfile and validate it before reloading if ingress caused the incident.
- Do not routinely downgrade the database. A migration rollback is permitted only after reviewing
  its downgrade safety and the data written since deployment.
- Restore a database backup only as a last-resort recovery action, into a controlled maintenance
  window, after preserving the failed live database.

Rollback must never alter Kennel/Husky Compose files, networks, volumes, databases, or routes.

## Required checks

- `/` serves the Angular application over HTTPS and HTTP redirects to HTTPS.
- `/api/...` is same-origin; invalid Origins are rejected.
- Public WebSocket PvP connects through `/api/pvp/.../ws`.
- `/health` and `/ready` are used internally and need not be public.
- Secure session cookies, verification/reset SMTP, RU/EN, guest Bot play, private PvP, history,
  export, and deletion pass smoke tests.
- Public listeners remain 22/tcp, 80/tcp, 443/tcp, and the pre-existing Amnezia UDP listener only.
- Kennel Operations, Husky Tracking, Caddy, Amnezia, and Docker remain healthy.

## Secrets and operational limits

Production credentials stay server-local and out of Git. Do not print PostgreSQL or SMTP values.
Per-service Docker logs rotate at three 10 MiB files. The single-worker constraint remains until
active session state is moved out of process. External uptime monitoring and an off-host backup
destination are post-launch operational follow-ups; neither should be represented as already
configured.
