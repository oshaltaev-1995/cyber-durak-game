# Kiba existing-VPS deployment preflight

Audit date: 2026-09-25. Target: a future EU/international public beta at
`cyberdurak.com` on the existing Netherlands VPS. This document is a read-only preflight, not a
deployment record.

## Executive decision

**Verdict: GO WITH CONDITIONS.** The existing 2-vCPU / 4-GB host has enough measured CPU, memory,
disk and inode headroom for a small, one-worker Kiba beta. Kiba must remain isolated, must not
publish its frontend, backend or PostgreSQL directly, and must not be horizontally scaled while
active games remain process-local.

The public beta is blocked until the conditions in [Deployment blockers](#deployment-blockers) are
closed. In particular, the host needs a controlled OS/security maintenance window, Kiba's current
production Compose contract needs a no-host-port ingress overlay, DNS/email/support and off-host
backup arrangements are not yet complete, and the existing public SSH configuration should be
hardened in a separate lockout-safe maintenance task.

No Kiba files, directories, images, containers, networks or volumes were created on the VPS during
this audit. Existing containers, Caddy, firewall, Docker, SSH and scheduled jobs were not changed or
restarted.

## Live host snapshot

| Item | Read-only observation |
| --- | --- |
| Host | `89.124.87.216`; Ubuntu 24.04.3 LTS; kernel `6.8.0-90-generic` |
| Uptime/load | 80 days; load averages `0.13 / 0.11 / 0.09` |
| CPU | 2 vCPU |
| RAM | 3.8 GiB total; 1.9 GiB used; **1.9 GiB available** |
| Swap | 2.0 GiB `/swapfile`; 88.7 MiB used; `vm.swappiness=10` |
| Swap persistence | `/swapfile` exists with mode 600, is active, and is present in `/etc/fstab` |
| Root filesystem | 79 GiB total; 28 GiB used; **48 GiB free** (37% used) |
| Inodes | 13% used |
| Public IPv6 | No global IPv6 address or default IPv6 route observed; do not create an AAAA record |
| Host time | `Europe/Moscow`; NTP synchronized. Timers should specify `Europe/Helsinki` explicitly |

The earlier estimate of roughly 2.4 GiB available RAM and 57 GB free disk is no longer current, but
the measured 1.9 GiB and 48 GiB still provide reasonable small-beta headroom.

### Existing production services

The host runs more than the initially listed Kennel workload:

| Workload | Containers and measured memory |
| --- | --- |
| Kennel Operations | frontend 2 MiB; backend 593 MiB; portrait worker 546 MiB; PostgreSQL 93 MiB |
| Husky Tracking | frontend 4 MiB; backend 90 MiB; PostgreSQL 26 MiB |
| Shared edge | Caddy 18 MiB |
| VPN | Amnezia/WireGuard 20 MiB |

All nine running containers reported zero Docker restart-count increments. Containers with health
checks were healthy. `https://app.kennelops.fi/` and `https://huskytracking.com/` both returned HTTP
200 at the start/end verification. Kennel's health endpoint returned 200. Kennel's frontend,
backend and Caddy do not define Docker health checks, so their `Up` status plus HTTP checks were used.

The largest steady consumers are the Kennel backend and portrait worker (about 1.14 GiB combined).
There was no CPU pressure at audit time.

## Docker, storage and logs

- Docker Engine/CLI: `28.2.2`, API 1.50, overlay2, systemd cgroups.
- Inventory: 12 containers, 9 running, 92 image records, five named volumes.
- Active named volumes use about 238 MiB in total; Kennel PostgreSQL is about 115 MiB and Husky's
  production PostgreSQL about 66 MiB.
- Docker images use 12.14 GB; Docker reports 9.77 GB as reclaimable. Build cache is 3.35 GB and fully
  reclaimable. This is not an immediate disk concern.
- **Do not run a blind prune.** Many images are explicitly tagged for rollback. A later cleanup may
  remove reviewed dangling/build-cache entries only after confirming which rollback images must be
  kept.
- The Docker default is `json-file`. Husky services use `max-size=10m,max-file=3`; Kennel and Caddy
  have no per-container rotation options. Their current JSON logs are small (largest about 2.8 MB),
  but journald uses about 3.5 GB.
- The Caddyfile has no access-log directive. Caddy operational output is in its Docker JSON log;
  certificates/configuration are held in persistent named volumes.

Phase 6B should give each Kiba service an explicit `json-file` limit (initially
`max-size=10m,max-file=3`) and verify that the resulting retention fits the 30-day privacy target.
Do not change Docker's global logging driver just for Kiba. Review journald and existing unbounded
containers separately; do not truncate their logs during deployment.

## Network and firewall snapshot

Observed host listeners:

- `22/tcp` on IPv4/IPv6: SSH;
- `80/tcp` and `443/tcp` on IPv4/IPv6: Docker-published Caddy;
- `40970/udp` on IPv4/IPv6: Docker-published Amnezia/WireGuard;
- loopback-only system DNS and containerd sockets.

No PostgreSQL, Kennel application, or Husky application port is publicly bound. Kiba must not add a
new public port.

UFW is installed but inactive. The effective public policy is a custom nftables/iptables ruleset:
`HT_HOST_INPUT` permits established traffic, TCP 22/80/443, UDP 40970 and ICMP, then drops other
public-interface input. `HT_DOCKER_INGRESS` also constrains Docker-origin destination ports to
80/443/40970. Docker still installs its own NAT/forward chains, so every Phase 6B verification must
inspect both `ss -lntup` and the effective nftables/DOCKER-USER rules. No firewall change is needed
for the proposed topology.

### SSH/security surface

SSH listens on port 22. The effective configuration permits public-key authentication **and**
password authentication, and allows root login; one root authorized-key line is present. Fail2ban
is not installed. Access for this audit used the existing root key.

Before public beta, schedule a separate, recovery-aware hardening task: verify provider console or a
tested non-root sudo/key path first, then disable password authentication and password-based root
login (for example, key-only `PermitRootLogin prohibit-password`). Do not combine an untested SSH
rewrite with the Kiba release or risk lockout. Fail2ban is optional once access is key-only and edge
controls are reviewed.

## Pending host maintenance

`apt list --upgradable` showed 125 packages from the host's cached package metadata. That metadata
was 156 days old, so the number is indicative rather than authoritative. The list includes security
or operationally important updates for the kernel (`6.8.0-110` offered), OpenSSH, OpenSSL, systemd,
Docker (`29.1.3` offered), containerd and core libraries. Docker 28.2.2 is functioning, but it is
behind the cached Ubuntu candidate. Caddy is `2.8.4`; its current support/security status should be
reviewed before launch rather than changed incidentally during Kiba deployment.

Plan a controlled maintenance window **before Kiba deployment**: verify current Kennel/Husky
backups, refresh package metadata, review the exact transaction, apply approved security updates,
reboot if the kernel requires it, and smoke-test every existing service. This audit did not run
`apt update`, install packages, restart Docker, or reboot.

## Existing Caddy architecture

Caddy is the `kenneloperations-caddy` container (`caddy:2.8-alpine`). It publishes only 80/443 and
has:

- a read-only bind mount from `/opt/kenneloperations/Caddyfile`;
- persistent `kenneloperations_caddy_data` and `kenneloperations_caddy_config` volumes;
- the Kennel default network and the shared `huskytracking_proxy` ingress network;
- automatic HTTPS/ACME for `app.kennelops.fi` and `huskytracking.com`;
- automatic HTTP-to-HTTPS behavior from Caddy's HTTPS site blocks;
- direct hostname-based reverse proxies to the relevant frontend containers.

Caddy currently reaches Kennel through `kenneloperations_default` and Husky through the external
`huskytracking_proxy` network (`172.30.50.0/24`). Husky attaches only its frontend to that network
under the unique alias `huskytracking-frontend`; a timer reconciles Caddy's ingress attachment.
Caddy `reverse_proxy` supports WebSocket upgrades, and Kiba's frontend nginx already forwards
WebSocket upgrade headers for `/api/`.

## Kiba production contract and topology

The repository supplies:

- PostgreSQL 17 Alpine with a persistent named volume and no published port;
- a non-root FastAPI image pinned to **exactly one Uvicorn worker**;
- an unprivileged nginx frontend on container port 8080;
- same-origin nginx proxying for `/api/`, including WebSocket upgrades;
- backend `/health` and PostgreSQL-aware `/ready` checks;
- explicit Alembic migration and backup/restore scripts.

The current `docker-compose.prod.yml` publishes `${KIBA_PUBLIC_PORT:-14200}:8080`. That is suitable
for a standalone host but is a deployment-contract gap on this shared VPS. Phase 6B must add a
reviewed production/ingress overlay (or focused Compose change) that removes the host port and joins
only the Kiba frontend to the existing ingress network. This preflight intentionally does not make
that configuration change.

### Chosen routing model

Use model **A: Caddy proxies the whole Kiba origin to Kiba's frontend nginx; nginx retains the
existing same-origin `/api` and WebSocket proxy to the backend.** This keeps the backend off the
shared edge network and reuses a contract already tested by Kiba.

```text
Internet :80/:443
        |
existing Caddy
        |  shared ingress network, unique alias kiba-frontend
Kiba frontend nginx :8080
        |  Kiba app network
Kiba backend :8000, exactly one worker
        |  Kiba data network
Kiba PostgreSQL :5432, private named volume
```

Phase 6B must verify the forwarded scheme/host chain through Caddy -> nginx -> Uvicorn. The current
nginx sets `X-Forwarded-Proto` from its own HTTP hop; if backend behavior or logging needs the
original HTTPS scheme, preserve the trusted Caddy header safely rather than trusting arbitrary
client forwarding headers. Edge request/IP rate limiting also belongs at Caddy because the backend
intentionally treats its direct socket peer as authoritative.

### Docker isolation

Use Compose project name `kiba-production`; do not set global `container_name` values. Plan:

- project-scoped `kiba_app` network for frontend/backend;
- project-scoped `kiba_data` network for backend/database, with the database isolated from the
  frontend and without host ports;
- backend retains controlled outbound connectivity needed for SMTP;
- only frontend joins existing external `huskytracking_proxy` with alias `kiba-frontend`;
- dedicated Kiba PostgreSQL volume; never mount or connect Kennel/Husky database volumes;
- no frontend/backend/database host-port publication.

Reusing the already established shared ingress avoids changing Kennel's Compose networks or
attaching a new network to its Caddy container. Unique aliases prevent collisions with the generic
Kennel `frontend` name and Husky alias.

### PostgreSQL

Run Kiba's PostgreSQL only inside `kiba_data`, with its own named volume and long random credentials
from the server-local environment file. Only the Kiba backend joins that network. Run migrations
once as an explicit release action; never run them automatically in every app start. Do not share
Kennel/Husky databases or publish 5432.

## Server filesystem and secrets plan

Follow the existing `/opt/<application>` convention without touching `/opt/kenneloperations` or
`/opt/huskytracking`:

```text
/opt/kiba/app/                 reviewed deployment checkout and Compose files
/opt/kiba/ops/                 Kiba-only operational wrappers/unit sources
/etc/kiba/production.env      root:root, mode 600, never in Git
/var/backups/kiba/            root-only local backup staging
```

Use `docker compose --project-name kiba-production --env-file /etc/kiba/production.env ...`.
Do not put a filled `.env` inside the checkout or Docker image. Do not introduce Vault/Kubernetes
for this single-host beta.

Required configuration includes:

- `APP_ENV=production`, `KIBA_PUBLIC_BASE_URL=https://cyberdurak.com`;
- reviewed `KIBA_TRUSTED_HOSTS` and `KIBA_CSRF_TRUSTED_ORIGINS` for the canonical origin (and `www`
  only where routing requires it);
- Secure auth cookies and reviewed auth/token/session/rate-limit values;
- PostgreSQL database/user/password and URL-encoded `KIBA_DATABASE_URL`;
- generic SMTP host, port, username, password, from-address, STARTTLS and timeout;
- email verification/password-reset TTLs;
- bot/PvP TTLs, PvP action limits/message size, and JSON logging.

Generate production credentials only during Phase 6B and never print them into shell history,
deployment logs, this document or Git.

## Caddy change preview (do not apply in this phase)

After DNS resolves and `kiba-frontend:8080` is reachable from Caddy, the conceptual addition is:

```caddyfile
www.cyberdurak.com {
	redir https://cyberdurak.com{uri} permanent
}

cyberdurak.com {
	header Strict-Transport-Security "max-age=31536000"
	encode zstd gzip

	@internal_health path /health /ready
	respond @internal_health 404

	reverse_proxy kiba-frontend:8080
}
```

Caddy automatically handles WebSocket upgrade transport to nginx; nginx forwards
`/api/pvp/.../ws` to the one backend. Exact syntax must be validated against a candidate copy with
the deployed Caddy version before atomically updating the host file. Back up the existing
Caddyfile, validate before reload, use a graceful **reload rather than restart**, and immediately
recheck both existing sites. Keep backend `/health` and `/ready` internal; monitor public `/` and
run readiness through Docker/internal networking. Do not expose operational details unnecessarily.

## DNS and email assumptions

No A, AAAA or authoritative DNS answer for `cyberdurak.com`/`www.cyberdurak.com` was observed at
audit time. Phase 6B requires:

- `A cyberdurak.com -> 89.124.87.216`;
- either `CNAME www -> cyberdurak.com` or the same A record, followed by the Caddy canonical redirect;
- no AAAA record until the VPS has a tested global IPv6 address and IPv6 firewall path.

No DNS/domain change was made. The VPS hostname suggests VDSina infrastructure, but the provider's
legal identity, Netherlands region, DPA, subprocessors and contract must be confirmed before the
processor register marks hosting ACTIVE.

The generic Kiba SMTP adapter requires the `KIBA_SMTP_*` variables listed above. Select and review a
transactional provider, then test verification and password recovery without logging raw tokens.
`support@cyberdurak.com` must be able to receive mail and be monitored before launch; this remains a
hard blocker and is separate from the SMTP sender.

## Resource budget and thresholds

Expected light-beta runtime ranges (planning estimates, not guarantees):

| Component | Expected RAM | Disk considerations |
| --- | ---: | --- |
| nginx frontend | 10-40 MiB | production image approximately 50-150 MB |
| one-worker FastAPI backend | 120-300 MiB | image/layers approximately 300-700 MB |
| PostgreSQL | 100-350 MiB | image plus initially small DB volume |
| incremental Caddy cost | under 20 MiB | shared existing image/certificate volume |
| **Typical Kiba total** | **250-700 MiB** | **roughly 1-2 GB images initially** |

Reserve 0.75-1.0 GiB RAM for Kiba and transient peaks. A Node production build can temporarily use
substantially more memory than the final nginx container; build serially during a quiet window or
build trusted immutable images off-host. Budget at least 5-10 GB free disk for images, temporary
build layers, database growth, logs and 30 days of local backups. Current 1.9 GiB available RAM,
48 GiB free disk, 87% free inodes, low load and 1.9 GiB unused swap are sufficient for the initial
beta, but not for unconstrained growth.

Trigger a capacity review or VPS upgrade if any of these persist:

- available RAM below 750 MiB, rising/sustained swap use above about 512 MiB, or any OOM kill;
- one-minute load consistently above 2 on the 2-vCPU host or readiness latency under normal traffic;
- disk below 15 GB free (or 20%) or inode use above 80%;
- repeated container restarts, database latency, backup overlap/failure, or excessive log growth;
- concurrent PvP/active-session load approaching the one-worker latency limit.

Do not add backend workers to solve capacity: process-local rooms make that unsafe. Upgrade vertical
capacity first, then design shared active-session state as a separate architecture project.

## Backups and retention

Existing scheduled jobs:

- Kennel backup: 03:30 Europe/Helsinki plus up to 10 minutes randomized delay; last result success;
- Husky backup: 04:40 Europe/Helsinki plus up to 5 minutes randomized delay; last result success.

Kennel backups use about 1.4 GB under `/var/backups/kenneloperations`; Husky uses about 2.2 MB under
`/var/backups/huskytracking`. A separate manual Kennel backup tree also exists. Do not read, reuse or
alter these files.

For Kiba, create a root-only systemd oneshot/timer in Phase 6B, tentatively 05:30
`Europe/Helsinki` with randomized delay, `Nice=10` and low I/O priority. It should call the reviewed
`scripts/backup_db.sh` with explicit production Compose and `/var/backups/kiba` paths, verify a
non-empty custom-format dump, rotate after 30 days, record success/failure, and periodically rehearse
`restore_db.sh` into a separate test database. Never restore over the active database by default.

A copy on this VPS is only local recovery staging. Before public launch, define and test an
encrypted off-host copy destination with retention and failure alerting. Do not place backups only
inside the PostgreSQL volume. Backup restoration is a last-resort rollback; migrations should be
backward-compatible wherever practical.

## Monitoring baseline

Do not install a monitoring stack for the initial beta. Phase 6B needs:

- external HTTPS uptime check for `https://cyberdurak.com/`;
- internal `/ready` check and Docker health/restart-state alerting;
- disk, available RAM, swap and load observation against the thresholds above;
- daily backup result/age/size check and off-host-copy failure alert;
- certificate-expiry observation (Caddy renews automatically);
- a simple release smoke checklist for auth, email, bot game and PvP/WebSocket.

## Phase 6B release procedure

1. Close the legal/provider/support/email/DNS blockers below and schedule a low-traffic maintenance
   window distinct from the OS-update window.
2. Snapshot `docker ps`, resource use, listeners and existing public URLs; confirm Kennel and Husky
   backups succeeded and Caddy/Amnezia are healthy.
3. Place the reviewed Kiba revision under `/opt/kiba/app`; record the immutable Git commit or image
   digests. Put secrets only in `/etc/kiba/production.env` (root:root 600).
4. Apply the reviewed no-host-port Compose ingress overlay. Validate `docker compose config`; confirm
   database/backend are absent from the external ingress and no Kiba port is published.
5. Build/pull Kiba images serially. Tag/digest them for rollback; do not prune existing projects.
6. Start only Kiba PostgreSQL and wait for its private health check. Do not connect to Kennel/Husky
   databases or volumes.
7. Run `alembic upgrade head` once as an explicit Kiba one-shot release command. Record the Alembic
   revision and output without secrets.
8. Start the exactly-one-worker backend and frontend. Verify backend `/health` and `/ready`
   internally; verify frontend-to-backend `/api` and WebSocket upgrade internally.
9. Confirm `ss -lntup` still exposes only 22, 80, 443 and 40970; inspect effective Docker/firewall
   rules. Kiba frontend/backend/PostgreSQL must have no host bindings.
10. Ensure apex/www DNS resolves to the VPS. Back up the live Caddyfile, prepare only the new Kiba
    blocks, validate with the deployed Caddy version, atomically install the candidate, and gracefully
    reload Caddy—never restart it for a normal config change.
11. Verify Caddy certificate/HTTPS, apex canonicalization, HSTS, SPA navigation, `/api`, and
    `/api/pvp/.../ws`. Confirm public `/health` and `/ready` are not exposed.
12. Immediately verify `app.kennelops.fi` (including its API), `huskytracking.com`, every existing
    container, and Amnezia status. Roll back the Caddyfile if any existing service regresses.
13. Configure/test production SMTP and the monitored support mailbox. Smoke-test registration,
    localized verification, password reset and cookie/origin/trusted-host behavior.
14. Smoke-test guest Human-vs-Bot, authenticated history/progression, two-browser private PvP and
    reconnect, EN/RU switching, Privacy/Terms, JSON export and test-account deletion/anonymization.
15. Install/enable the Kiba-only backup timer, create an initial backup, copy it off-host, rehearse a
    separate-database restore, and verify retention/alerts.
16. Enable the minimal monitoring checks, capture final resource/listener/container snapshots, and
    monitor Kennel/Husky/Kiba through the release window.

## Rollback procedure

1. Stop new Kiba traffic: restore the backed-up Caddyfile, validate it, gracefully reload Caddy, and
   confirm Kennel/Husky remain healthy. DNS rollback is secondary to the immediate route removal.
2. Stop only Kiba frontend/backend containers. Leave Kiba PostgreSQL and its volume intact; never use
   `docker compose down -v`.
3. If application rollback is enough, start the previously recorded Kiba image digests with the
   same database and verify internal health before restoring routing.
4. Treat schema compatibility as a release gate. Do not routinely run Alembic downgrade: an older
   application may not understand a newer schema, and destructive downgrades may lose data. Prefer
   forward fixes or a known backward-compatible app image.
5. Restore PostgreSQL only for confirmed data corruption or an explicitly approved incompatible
   migration failure. Preserve the failed database/dump, stop Kiba writers, follow the rehearsed
   restore procedure, and verify data/Alembic revision before reopening traffic.
6. Never change, stop, restore or roll back Kennel/Husky databases as part of a Kiba rollback.

## Kennel Operations protection plan

- Never edit Kennel Compose/environment/database/volumes or use its networks for Kiba data traffic.
- Reuse only the established shared **frontend ingress** network with a unique Kiba alias; leave
  Kennel's default network untouched.
- Never publish Kiba ports that could displace 80/443/22/40970 or another host service.
- Back up the Caddyfile before adding one independent Kiba site block; validate before graceful
  reload. Do not restart the Caddy container.
- Record existing container IDs/start times/restart counts and monitor them during deployment.
- Smoke-test Kennel root and API plus Husky root immediately before and after Caddy reload.
- On any regression, restore the previous Caddyfile and reload it first; stop only Kiba services.
- Never restart Docker, reboot, prune networks/images/volumes, or combine unrelated host changes
  with the Kiba release.

## Privacy and operational gates

Phase 6A.6 correctly records all providers as PLANNED/NOT USED. Before Kiba processes production
users:

- identify the VPS provider's legal entity, Netherlands/EEA region, subprocessors, DPA, retention
  and transfer terms; update `PROCESSORS.md` and Privacy wording;
- select/review the transactional SMTP provider and processing region;
- identify/review the domain/DNS provider;
- choose and review an encrypted off-host backup destination;
- make `support@cyberdurak.com` operational and monitored;
- configure/verify 30-day backup and log retention plus expired-row cleanup;
- have the owner complete the required-before-beta items in `LEGAL_REVIEW_CHECKLIST.md`.

No analytics/ads/marketing trackers are part of this plan. Any future addition requires a new
privacy/cookie assessment.

## Deployment blockers

Required before Phase 6B can expose public traffic:

- [ ] Plan and complete controlled host security updates/reboot, then re-verify existing services.
- [ ] Perform lockout-safe SSH review/hardening (key/recovery path proven first).
- [ ] Add/review Kiba's no-host-port ingress/network/logging production overlay and forwarded-HTTPS
      behavior; validate the complete Compose contract.
- [ ] Confirm/purchase/control `cyberdurak.com`; configure apex/www DNS only during Phase 6B.
- [ ] Confirm hosting and DNS processor details and legal review.
- [ ] Select/configure/review the SMTP provider; use no real credentials until deployment.
- [ ] Make `support@cyberdurak.com` receive mail and establish monitoring.
- [ ] Generate/store production database and SMTP secrets in `/etc/kiba/production.env`.
- [ ] Select/test off-host backup storage and the daily backup/30-day retention workflow.
- [ ] Complete the owner legal-review checklist and provider-specific Privacy/Terms review.
- [ ] Define simple uptime/readiness/resource/backup alerts and an on-call contact path.

Once those conditions are met, the measured host capacity supports a cautious small public beta.
This conclusion does not authorize Phase 6B or any server change.
