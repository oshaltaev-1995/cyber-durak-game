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
Verification and reset copy is selected from the persisted RU/EN account preference and passes
through the same generic SMTP adapter. Deployment needs only the single Angular artifact—runtime
catalogues provide both languages, so no separate locale build or locale-specific deployment is
required.

## Backup and restore

```bash
./scripts/backup_db.sh
./scripts/restore_db.sh backups/kiba-YYYYMMDDTHHMMSSZ.dump kiba_restore_test
```

Restore requires a separate database name and refuses the active database. Remove a validated test
database explicitly with `dropdb`. Phase 6B must schedule daily local backups, define retention,
and rehearse restores. Off-host disaster-recovery storage is explicitly deferred for the initial
portfolio beta: this accepted risk means total VPS/storage loss may also destroy local backups. Do
not run `docker compose down -v` in production unless permanent data destruction is intended.

## Safe release sequence

1. Back up PostgreSQL and verify the backup is non-empty.
2. Pull/build the new version.
3. Run `alembic upgrade head` once as an explicit release step.
4. Start/restart the single backend worker and frontend proxy.
5. Verify `/health` and `/ready`.
6. Smoke-test frontend, auth, a guest game, and private PvP.

Production startup does not run Alembic automatically. Destructive downgrade is never a production
release step.

## Phase 6A.6 privacy and legal gate

Before public deployment:

- the public EN/RU Privacy and Terms pages must be reviewed and current;
- authenticated JSON export and password-confirmed transactional deletion must pass production
  smoke tests, including retained PvP-history anonymization;
- `support@cyberdurak.com` must receive mail and be monitored;
- the processor register and public provider wording must be finalized after Phase 6B provider
  selection, including DPA/location/transfer review;
- 30-day targets for application/security logs and database backups, plus short expired-token/session
  cleanup, must be configured and monitored;
- backup restore/rotation and deletion-after-restore handling must be rehearsed;
- the owner must review `LEGAL_REVIEW_CHECKLIST.md`, including the possible Finnish
  geographical/business-address obligation, without publishing a private home address by default;
- no analytics, advertising, marketing pixels, or other non-essential tracking may be enabled
  without renewed cookie/privacy assessment.

The controller is Oleg Shaltaev, Finland, `support@cyberdurak.com`. This is compliance readiness,
not formal certification. Active games/rooms remain process-local and unfinished sessions are not
part of account export or persistent deletion.

## Phase 6A.8 host-maintenance status

Controlled VPS maintenance completed on 2026-09-25. Reviewed OS/security packages and kernel
`6.8.0-142-generic` were installed, exactly one reboot completed, and Docker, Caddy, Kennel
Operations, Husky Tracking, Amnezia, public HTTPS endpoints, swap, listeners, and firewall exposure
were validated afterward. The previous `6.8.0-90-generic` kernel remains available as a recovery
fallback.

Docker Engine/containerd/runc upgrades were intentionally deferred to a dedicated runtime window;
the installed runtime remains unchanged. This maintenance does not deploy Kiba or close the Phase
6B domain, email, privacy-provider, backup, secret, ingress, and monitoring prerequisites. See
`VPS_MAINTENANCE_REPORT.md` for the sanitized record.

## Phase 6A.9 SSH-hardening status

Lockout-safe SSH authentication hardening completed on 2026-09-25. Password and
keyboard-interactive SSH authentication are disabled; root remains available through the existing
authorized public key on unchanged port 22. Configuration syntax and effective values were checked
before reload, and a new independent key-only root login succeeded afterward. SSH was reloaded
without a restart or reboot, and Docker, Caddy, Kennel Operations, Husky Tracking, Amnezia, public
HTTPS endpoints, and the listener surface remained healthy. See `VPS_SSH_HARDENING_REPORT.md` for
the sanitized record. This focused change is not a claim that the entire host is fully hardened.

## Phase 6B deployment requirements

- domain, DNS, TLS certificate, HTTPS reverse proxy, and HSTS;
- real SMTP credentials and a unique production database password;
- automated local backup schedule/retention and a demonstrated restore drill;
- log retention, uptime/readiness monitoring, and restart maintenance communication.

Off-host disaster-recovery copy: **DEFERRED**. It is a post-launch follow-up rather than a blocker
for this intentionally small public beta. Local Kiba backups must remain isolated under
`/var/backups/kiba`, protected, verified, and rotated at approximately 30 days.

### Phase 6B deployment status (2026-09-25)

**DEPLOYED — PUBLIC BETA READY.** The reviewed production release is live at
<https://cyberdurak.com> with private PostgreSQL, exactly one backend worker, no Kiba host ports and
the existing Caddy as sole HTTPS ingress. Database migrations, internal health, HTTPS/TLS,
same-origin API and WSS, guest gameplay, account/data-rights flows, RU/EN presentation, and
Kennel/Husky regressions passed. The generic shared-network alias found during the first ingress
check was corrected to the unique `kiba-frontend` service name without restarting existing services.

Production SMTP uses Brevo TCP 2525 with STARTTLS because the provider blocks 465/587. Host and
backend-container connectivity, TLS, authentication, and actual verification-message receipt
passed. Gmail placed the first test message in Spam; deliverability is a post-deployment follow-up.

Daily protected local PostgreSQL backups are enabled with approximately 30-day retention, and a
real restore drill into a disposable database passed. Off-host disaster recovery remains the
explicitly accepted deferred limitation. External uptime monitoring is also a post-launch action.
See `PRODUCTION_DEPLOYMENT_REPORT.md` for the sanitized deployment record.

## Known public-beta limitations

- Backend restart loses unfinished games and rooms.
- Exactly one backend worker; no automated failover or multi-node scaling.
- Rate limits reset on restart and require reverse-proxy reinforcement.
- No active-game persistence, Redis/shared room store, matchmaking/rating, or anti-farming controls.
- No off-host disaster-recovery copy; local backups share the VPS failure domain.
- Final human legal review and provider-specific policy details remain an owner follow-up.
- Verification/reset email deliverability needs monitoring; the first Gmail test landed in Spam.
- External public uptime/readiness monitoring is not yet configured.
