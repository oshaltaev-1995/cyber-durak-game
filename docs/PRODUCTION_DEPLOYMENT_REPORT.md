# Phase 6B production deployment report

Date: 2026-09-25
Status: **DEPLOYMENT STOPPED SAFELY — SMTP EGRESS BLOCKED**

No credentials, tokens, private configuration values, database contents, or personal data are
included in this report.

## Release

- Production contract commit: `6a153b2e10f89a14d016ff9cc1bc53b7d4b9c490`
- Ingress-alias correction: `cdbd7563e8b85c91460970f0fd96df736765db7a`
- Server release archive: `/opt/kiba/app`
- Server release marker: `cdbd7563e8b85c91460970f0fd96df736765db7a`
- Secret environment: `/etc/kiba/production.env`, `root:root`, mode `0600`

The private Git repository was not accessible anonymously from the server. The exact reviewed Git
commit was therefore transferred as a local `git archive`; no GitHub credential or deploy key was
added to the VPS.

## Gates satisfied

- `support@cyberdurak.com` passed an external receipt test and is monitored.
- Apex DNS resolves to the intended VPS; `www` aliases the apex.
- Brevo sender/domain setup and server-local credential presence were user-confirmed.
- All required SMTP variable **names** were verified without displaying values. Existing SMTP
  entries were preserved while additional Kiba production configuration was appended atomically.
- Production Compose rendered with zero published Kiba ports, one backend worker, an internal
  database network, a Kiba-only PostgreSQL volume, bounded per-container logs, and the existing
  shared Caddy ingress network.
- Alembic upgraded a new production database to `20260829_0007`; `alembic check` reported no new
  operations.
- Database, backend, and frontend containers reached healthy state with zero restarts.
- Internal frontend, backend liveness, readiness, and same-origin frontend-to-API proxy checks
  passed before any Caddy change.
- Caddy configuration validation passed before reload. HTTPS certificate issuance, apex HTTP to
  HTTPS redirect, `www` canonical redirect, HSTS, SPA delivery, and private internal health paths
  were observed while the route was temporarily active.
- A complete guest Human-vs-Bot game finished through the public API (human win, 17 accepted human
  actions). A public WSS private-PvP smoke established both participant connections and PING/PONG.
- Invalid-Origin authentication was rejected with HTTP 403. Privacy and Terms returned HTTP 200.
- A disposable account passed registration, secure-cookie `/api/auth/me`, data export, transactional
  deletion, and post-deletion login rejection. Export headers/content were checked for expected
  categories and absence of credential/token fields.
- A protected PostgreSQL dump was created and validated with `pg_restore --list`. It was restored
  into a separate disposable database, inspected by the existing restore script, and dropped.

Local backup location: `/var/backups/kiba` (`root:root`, directory mode `0700`, dump mode `0600`).
The tested dump was non-empty. The installed timer targets daily execution with randomized delay
and approximately 30-day retention. It remains disabled while deployment is stopped.

Off-host disaster-recovery copy: **DEFERRED**. This is an explicitly accepted initial-beta risk;
total VPS/storage loss can also destroy the local backup.

## Issues found and corrections

The first Compose revision used the generic service key `frontend`. Docker automatically exposed
that service name as an alias on the shared ingress network, colliding with the existing Kennel
route's `frontend` name. A Kennel check returned HTTP 502. Only the new Kiba frontend was stopped;
Kennel recovered immediately without any Kennel or Caddy restart. The Kiba service was renamed
`kiba-frontend`, validated to expose only unique aliases, committed, pushed, and redeployed. Kennel
and Husky both returned HTTP 200 afterward.

The existing Caddyfile is a read-only single-file bind mount. An atomic host-path replacement does
not change the inode mounted by the running container. The candidate was therefore loaded through
Caddy's admin reload API after separate validation; Caddy was never restarted. The original host
and runtime configuration were restored by the same validated reload path when the SMTP gate
failed. Host and container Caddyfile checksums again match the pre-deployment checksum.

## Blocking SMTP result

Account HTTP operations do not roll back when transactional email delivery fails. During the
production smoke, verification delivery logged failures. A separate connection-only test from the
backend container established that:

- the configured SMTP hostname resolves successfully to IPv4;
- a TCP connection to the configured SMTP endpoint times out after 20 seconds.

No SMTP hostname, port, username, password, or message token was printed. No alternate port was
guessed, and no firewall/network change was attempted. The owner or provider must determine whether
the VPS provider blocks outbound SMTP or whether an approved Brevo endpoint/configuration change is
required. Successful verification and password-reset receipt must be demonstrated before public
exposure is restored.

## Safe rollback state

- The Kiba Caddy blocks were removed from both runtime and persistent configuration.
- The active Caddyfile checksum equals the pre-deployment checksum.
- Caddy remained running with restart count zero.
- Kennel Operations and Husky Tracking both returned HTTP 200 after rollback.
- Kiba database, backend, and frontend containers are stopped, not deleted.
- Kiba images, isolated networks, PostgreSQL volume, source archive, protected environment, and
  verified backup remain for a controlled resume.
- `kiba-backup.timer` is disabled/inactive while the Kiba database is stopped.
- Public listeners remain limited to the pre-existing SSH, HTTP, HTTPS, and Amnezia UDP ports; no
  PostgreSQL or application port was published.
- Docker, SSH, firewall, Amnezia, Kennel, and Husky configuration were not changed or restarted.

Final observed host headroom after rollback was approximately 1.7 GiB available RAM, 6 MiB swap in
use, and 46 GiB disk free. Existing workloads were running normally.

## Resume gate

Before resuming Phase 6B:

1. Resolve or formally approve the production SMTP egress path without exposing credentials.
2. Prove backend-container TCP connection to the approved endpoint.
3. Start the existing Kiba containers and re-run SMTP verification/reset receipt tests.
4. Re-enable and re-run the backup service, then enable its timer.
5. Re-validate and reload the saved Kiba Caddy addition.
6. Immediately regression-test Kennel and Husky, then repeat public HTTPS/API/WSS/account smoke.

Do not classify this deployment as public-beta ready until that gate passes.
