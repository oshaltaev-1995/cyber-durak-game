# Phase 6B production deployment report

Date: 2026-09-25
Status: **DEPLOYED — PUBLIC BETA READY**
Public URL: <https://cyberdurak.com>

No credentials, tokens, private configuration values, database contents, or personal data are
included in this report.

## Release and topology

- Production contract commit: `6a153b2e10f89a14d016ff9cc1bc53b7d4b9c490`
- Ingress-alias correction: `cdbd7563e8b85c91460970f0fd96df736765db7a`
- Server application release marker: `cdbd7563e8b85c91460970f0fd96df736765db7a`
- Server release path: `/opt/kiba/app`
- Secret environment: `/etc/kiba/production.env`, `root:root`, mode `0600`
- Compose project: `kiba-production`

The exact reviewed Git commit was transferred as a local `git archive`; no GitHub credential or
deploy key was added to the VPS. Kiba runs as three isolated containers: private PostgreSQL, exactly
one FastAPI worker, and the production nginx frontend. Kiba publishes no host ports. Existing Caddy
is the sole public ingress on ports 80/443 and reaches the uniquely named `kiba-frontend` alias on
the pre-existing ingress network. PostgreSQL and the backend remain private.

## Validation completed

- Production Compose rendered with zero published Kiba ports, one backend worker, isolated database
  networking and volume, and bounded per-container logs.
- Alembic upgraded the new database to `20260829_0007`; `alembic check` reported no pending schema
  operations.
- Database, backend, and frontend reached healthy state with zero restarts.
- Internal frontend, backend readiness, and same-origin frontend-to-API proxy checks passed before
  public routing was enabled.
- Caddy configuration validation passed before its admin reload. Caddy was not restarted.
- Let's Encrypt issued the apex and `www` certificates. Apex HTTP redirects to HTTPS, `www`
  redirects to the apex, HSTS and application security headers are present, and public `/health`
  and `/ready` return 404 while internal readiness returns 200.
- Kennel Operations and Husky Tracking returned HTTP 200 immediately after the route change and in
  final checks. Their containers, Compose files, networks, volumes, databases, and routes were not
  modified.
- A public guest Human-vs-Bot match completed as a draw after 27 accepted human actions. A public
  private-PvP WSS smoke authenticated both guest participants and passed PING/PONG.
- Browser smoke verified the English first-visit experience, runtime Russian switch, Privacy and
  Terms, and return to English.
- A disposable production account passed login, secure-cookie `/api/auth/me`, password-reset
  request, data export, transactional deletion, and post-deletion login rejection.
- The frontend, Privacy, Terms, Kennel, and Husky public URLs all returned HTTP 200 in the final
  verification. Ports 5432, 8000, and 8080 are not publicly reachable.

Repository release validation before deployment passed 537 backend tests and 146 frontend tests,
backend/frontend lint and formatting, frontend production build, Alembic checks, `pip-audit`, npm
high-severity audit, production image builds, production Compose validation, and nginx validation.

## SMTP and email delivery

VDSina blocks outbound TCP 465/587 by default. The approved Brevo alternative endpoint on TCP 2525
was tested from both the VPS host and the Kiba backend network context. The endpoint advertised
STARTTLS; TLS negotiation and SMTP authentication succeeded. Only these protected configuration
entries were changed:

- SMTP port: `2525`
- STARTTLS: enabled

Existing SMTP host, username, password, and sender values were preserved and never printed. A real
verification message with subject `Verify your email — KIBA` was received at the monitored support
mailbox, and its link used the `https://cyberdurak.com/` origin. The verification URL/token is not
recorded here.

Gmail placed this first production test in Spam. Delivery itself passed, so this is a non-blocking
post-deployment deliverability follow-up: review SPF, DKIM, DMARC, sender reputation, and message
content using provider and mailbox diagnostics. Do not weaken STARTTLS or authentication.

## Backup and restore

- Kiba backups are isolated under `/var/backups/kiba` (`root:root`, directory mode `0700`, dump mode
  `0600`).
- A real non-empty PostgreSQL dump passed `pg_restore --list`.
- The restore script restored the dump into a disposable database; the restored schema/data were
  inspected and the disposable database was dropped.
- `kiba-backup.timer` is enabled and active for daily execution with randomized delay and
  approximately 30-day retention.
- Backup failure is observable through systemd failed state and journal output.

Off-host disaster-recovery copy: **DEFERRED**. This is an explicitly accepted initial-beta risk.
Total VPS/storage loss could also destroy the local backups; an off-host copy remains a
post-launch follow-up.

## Deployment issue corrected

The first Compose revision used the generic service key `frontend`. Docker automatically added that
name as an alias on the shared ingress network, colliding with Kennel's existing route and briefly
causing an HTTP 502. Only the new Kiba frontend was stopped; Kennel recovered immediately without a
Kennel or Caddy restart. The service was renamed `kiba-frontend`, its network aliases were verified
as unique, and both existing public sites remained healthy after redeployment.

The existing Caddyfile is a read-only single-file bind mount. Replacing the host path does not
change the inode seen by the running container. The validated candidate was therefore loaded through
Caddy's admin reload path while the persistent host file was updated for the next container start.
Caddy stayed on the same container instance with restart count zero.

## Final host state

- Kiba database, backend and frontend: healthy, zero restarts.
- Caddy: running, zero restarts; public HTTPS and redirects healthy.
- Kennel Operations, Husky Tracking and Amnezia: running; existing public services healthy.
- Public listeners remain SSH, HTTP, HTTPS and the existing Amnezia UDP port only.
- Final snapshot: approximately 1.5 GiB available RAM, 6 MiB swap used, 46 GiB disk free, and load
  averages below 0.2.
- Docker, firewall, SSH and Amnezia configuration were not changed or restarted for this deployment.

## Accepted limitations and follow-up

- Off-host disaster-recovery copy is deferred.
- Configure an external uptime check for the public frontend and backend readiness path without
  exposing the internal health endpoints.
- Investigate Gmail spam placement and monitor verification/reset delivery.
- Complete the owner/legal review of finalized processor terms, DPAs, locations and transfer
  safeguards.
- Active bot games and PvP rooms remain process-local; exactly one backend worker is required.

These limitations do not change the deployment verdict for the intentionally small portfolio
public beta.

## M6 combined staged multiplayer rollout (2026-10-09)

M6 deployed application commit `4666f3cc933c8feae5036ee174491834d0405a17` over the prior
production revision `0ca70c8613f24ea8e1acde5397d9a6617185f1f2`. The deployment used a
two-stage gate. Stage A recreated only the Kiba backend and frontend with
`KIBA_MULTIPLAYER_3_4_ENABLED=false`; public two-player bot/PvP, hints, reconnect, rematch,
navigation, social metadata and persistence-facing pages passed acceptance before Stage B. Stage B
changed only that root-owned production-environment Boolean to `true` and recreated only the
backend process that consumes it. PostgreSQL, Caddy, Husky Tracking, Kennel Operations, Amnezia,
Docker and host networking were not restarted or reconfigured.

The accepted production images are:

- backend: `sha256:6fcafd173eae8e2edfc7ef984a95c1126d076d8d235b1fddde6ca13edcc09661`;
- frontend: `sha256:a873399b13f08a98da98d2a5d0f65e25d3ac8606d1f6c905964556f982fec5c6`.

The Stage A application recreation completed at approximately 2026-10-09 19:45 UTC. Stage B's
backend-only environment reload completed at approximately 19:53 UTC. The public capability then
reported multiplayer enabled. Controlled production checks covered exact-capacity three- and
four-player private rooms, stable relative seats, hidden hands, Pass, defense, transfer,
disconnect/reconnect and neutral Exit. Three- and four-player bot matches completed to ranked
finish groups; same-session replay retained bot names/seats and cleared the prior result. An
authenticated 3/4-player bot completion left profile-history count unchanged. The nine-step core
tutorial, separate six-step multiplayer guide, one-time onboarding, EN/RU surfaces, keyboard radio
selection, and the requested desktop/mobile viewports passed smoke checks. A pre-existing minor
Russian singular-card grammar issue in last-bout copy remains a non-blocking localization
follow-up; no production hotfix was made.

Immediately before replacement, `kiba-backup.service` created and verified
`/var/backups/kiba/kiba-20261009T194245Z.dump` (28,801 bytes, mode `0600`). No migration was added or
run; the database remains at Alembic head `20260829_0007`. Final health showed approximately
1.9 GiB `MemAvailable`, 135 MiB resident swap, idle swap I/O, zero memory PSI, no OOM evidence,
44 GiB free disk, and zero Kiba container restarts/OOMKilled states. Kiba, Husky Tracking and Kennel
Operations returned HTTP 200, both host monitors returned success, and the Kiba backup timer
remained active.

Rollback remains available from the retained old backend/frontend image digests, the preserved
old source checkout, production revision `0ca70c8613f24ea8e1acde5397d9a6617185f1f2`, and the protected
pre-Stage-B environment copy. No old usable image was pruned and no database rollback is required.
