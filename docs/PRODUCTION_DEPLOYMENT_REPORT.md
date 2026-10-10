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

## Russian TAKE grammar patch (2026-10-09)

Frontend-only application commit `a8f9230bca58a74e395f6e33b85bb0be3e697c94` corrected the
Russian TAKE result from nominative singular `1 карта` to contextual accusative singular `1 карту`
while retaining the existing Russian plural categories and unchanged English output. Production
now runs frontend image
`sha256:e8164581cc621cc391e41893517814ea45f67d323a542936cf4311f976332166`.

Only `kiba-production-kiba-frontend-1` was recreated. The Kiba backend remained on
`sha256:6fcafd173eae8e2edfc7ef984a95c1126d076d8d235b1fddde6ca13edcc09661`; its container identity
and start time, the PostgreSQL container, Caddy, Husky Tracking, Kennel Operations, Amnezia and the
Docker runtime were unchanged. No migration or backup was required for this static frontend patch,
and `KIBA_MULTIPLAYER_3_4_ENABLED` remained `true`.

Live acceptance rendered `Вы взяли 1 карту` in a two-player bot match and `You took 1 card` after
the runtime locale switch. The 2/3/4-player selector, bot play and private-PvP entry loaded without
browser-console warnings or errors. Kiba, Husky Tracking and Kennel Operations returned HTTP 200;
the built and live social metadata remained intact. Final host health showed approximately 2.0 GiB
available RAM, 134.6 MiB swap with idle swap I/O, zero current memory PSI, no OOM evidence, and no
failed systemd units.

## D5 staged deck-variant rollout (2026-10-10)

D5 deployed exact release-candidate application commit
`97763da0927bd987f70e8a19016e32b8bd73a9c5` over application revision
`a8f9230bca58a74e395f6e33b85bb0be3e697c94`. Local release validation used the repository's bundled
Node runtime and passed frontend lint, formatting, the production build, 355 frontend tests, backend
lint/formatting, 831 backend tests, and `git diff --check`. No migration was present or run.

Before replacement, `kiba-backup.service` created and verified
`/var/backups/kiba/kiba-20261010T131107Z.dump` (28,802 bytes, mode `0600`). The previous source,
protected environment, Compose inspection data, and prior backend/frontend images were retained for
rollback. The exact RC archive checksum was
`05d1610075293681a93105b819ad9e66d14b8c56e7769344d8df2edbc72233ce`.

The accepted production images are:

- backend: `sha256:350fcd6716edf725ac7e00e8e9e5c5e30a70338f94c8da3276dd9e095352eb75`;
- frontend: `sha256:f27f448ef5b1744053d46baee64a1265341aaa04bb71919257c9204c603f22b0`.

Stage A deployed the RC with `KIBA_MULTIPLAYER_3_4_ENABLED=true` and
`KIBA_DECK_VARIANTS_ENABLED=false`. Only the Kiba backend and frontend were recreated; the
PostgreSQL container identity and start time were unchanged. Public capabilities, UI and direct API
checks confirmed Classic ×1 remained the only available configuration and all three non-default
configurations were rejected with the established feature-unavailable response. Live acceptance
covered two-, three- and four-player bot/PvP starts, Hint Mode, bot transfer cascades, three-player
Pass, attack/defense, reconnect, a complete two-player PvP match, and accepted same-room rematch.
Deck controls remained hidden. Raw social metadata, the v2 preview image, and exact Russian TAKE
copy remained intact. Representative browser consoles contained no warning, error, or CSP entries.

After the Stage A gate passed, Stage B appended only
`KIBA_DECK_VARIANTS_ENABLED=true` to the root-owned mode-`0600` production environment. The
protected pre-Stage-B environment is retained. Only the backend was recreated to consume the flag;
its image did not change. The frontend and PostgreSQL container identities remained unchanged, and
the public capability reported both multiplayer and deck variants enabled.

Live Stage B acceptance covered all four configurations and initial card conservation totals:

- Extended ×1 exposed ranks 2–5, human-readable Red/Black Joker cards, two-player Hint output, and
  normal bot/PvP play. A real private match reached terminal state, reconnected, and accepted a
  rematch in the same room with the same seats/configuration, fresh cards, no `completion_pending`,
  and no false disconnect flash.
- Classic ×2 started a three-player bot game with two independently selectable visual `6♣`
  instances; selecting one left the other unselected. Bot transfer/cascade behavior remained live,
  and the three-player Hint control stayed absent.
- A real four-player Extended ×2 108-card bot match completed end-to-end twice. It exercised named
  bots, ranks 2–5, Pass, bot transfers/cascades, finished seats, ranked 4→3→2 completion, and no
  progression claim. `Play again` preserved player count, names, seats, profile and deck count while
  starting a fresh deal; `Change players` returned to configuration.
- A three-player Classic ×2 private room displayed immutable configuration to joiners, started only
  at exact capacity, preserved hidden hands, accepted attack/defense and non-cycling Pass, and
  recovered through reconnect with configuration unchanged. Three- and four-player variant games
  exposed no Hint control.

The live Joker smoke rendered accessible `Red Joker, value 25` and `Black Joker, value 25` labels,
showed both colors in double-deck play, and exposed no physical IDs as user content. An ordinary
black top with an opposite-color Red Joker confirmed the latter remained 25. A naturally occurring
trump-Joker value 50 or exposed-Joker trump family was not encountered live; those cases remain
covered by the deterministic D2/D3/D4 suite. A suitable five-rank starting hand did not occur during
reasonable live testing, so initial-Street acceptance was not tested live and remains covered by
the deterministic RC integration suite.

An authenticated two-player Extended ×1 bot match completed in production. Before/after profile
comparison showed unchanged XP, aggregate statistics, achievements, cosmetics and history count;
no progression/history/statistics mutation was added. Classic ×1 persistence remained covered by
the passing persistence integration suite and a non-mutating live regression smoke, avoiding an
unnecessary extra production-statistics mutation.

Public Rules covered 36/54/72/108 cards, values 2–5, Joker 25/50, color trump relationships, Joker
after Ace, non-wrapping initial/post-response Streets, duplicate physical cards, double decks, and
the defender cap. The core tutorial remained nine steps and now teaches both arithmetic and initial
Street legality; the multiplayer guide remained six steps; the five-step deck/Joker guide worked in
English and Russian. Fresh-context non-default onboarding appeared once, linked to the deck guide,
dismissed successfully, and did not reappear on the next non-default game. Russian totals rendered
as `36 карт`, `54 карты`, `72 карты`, and `108 карт`; live TAKE copy rendered
`Вы взяли 1 карту`.

Responsive 108-card production smoke passed at 1440×900, 1366×768, 1280×800, 390×844, and
430×932 with no page-level horizontal overflow, three opponent seats present, the local hand usable,
and the action control visible. A completed mobile-width game retained a usable 30-card post-TAKE
hand. Keyboard operation selected both the Extended profile and two-deck count; selected states,
Joker accessible names, duplicate-card independence, card roles, guide navigation, and textual
recommendation passed accessibility smoke.

Final production health showed the exact RC revision, both capabilities enabled, healthy backend,
frontend and PostgreSQL containers with zero restarts and `OOMKilled=false`, approximately 2.0 GiB
`MemAvailable`, 138 MiB resident swap with `si=0`/`so=0`, zero current memory PSI, and no kernel OOM
evidence. Kiba, Husky Tracking and Kennel Operations returned HTTP 200. Docker, Caddy and Amnezia
remained active; backup and both monitor timers remained active; monitor services reported success;
no systemd units were failed. PostgreSQL, Caddy, Husky, Kennel, Amnezia, Docker, firewall, SSH and OS
packages were not restarted, rebuilt, reconfigured, or upgraded. No release tag was created or
moved.

## Post-audit P1 frontend correction

P1 deployed exact application commit `cbd8f1b80680de71ec689ce08526f05fbed661a8` over D5 application
revision `97763da0927bd987f70e8a19016e32b8bd73a9c5`. The patch makes the public PvP creator wait for
authoritative capabilities before enabling room creation, preserves independently gated player and
deck selectors, adds an explicit fresh `/play` loading state, defers first-use bot-session creation
until deck and multiplayer onboarding have both completed, adds a localized client-visible Not Found
route with `noindex,follow`, and updates the narrow Privacy product-scope sentence to private rooms
for 2–4 players. The static SPA fallback intentionally continues to return HTTP 200 for unknown
document routes; no brittle nginx or Caddy route whitelist was introduced.

Local release validation passed frontend lint and formatting, the production build, 363 frontend
tests in 39 files, social-preview source/built checks, backend lint/formatting, 831 backend tests, and
`git diff --check`. Real local UI/WebSocket acceptance covered default two-player Classic, a terminal
two-player Extended match and rematch, a terminal three-player match and unanimous rematch,
three-player Classic double-deck reconnect, four-player Extended double-deck active play/reconnect,
five required responsive viewports, selector accessibility, fresh `/play`, first-use onboarding,
Not Found, and Privacy in English and Russian.

Immediately before deployment, `kiba-backup.service` created and internally verified
`/var/backups/kiba/kiba-20261010T150933Z.dump` (28,801 bytes, mode `0600`). The exact application
archive SHA-256 was `f43e82f0ef7cefd149e8923ade0abd9199459bb7879d8e30ead08105d68216c1`.
The complete prior source tree and the prior frontend image
`sha256:f27f448ef5b1744053d46baee64a1265341aaa04bb71919257c9204c603f22b0` remain retained for
rollback. Only `kiba-frontend` was rebuilt and recreated. The accepted frontend image is
`sha256:ba46672aa4b9d4f3691fdd93fa1b0e7708c5b4b321ec246caec81a29e00c07e0`; backend image
`sha256:350fcd6716edf725ac7e00e8e9e5c5e30a70338f94c8da3276dd9e095352eb75` and PostgreSQL were
unchanged. Both capability flags remained `true`; no migration was added or run.

Live public acceptance used the normal `/pvp` creator. A two-player Extended room reached terminal
state and rematched in place without `completion_pending` or a false disconnect. A three-player
Classic room started only at 3/3, exercised attacker phases, Pass and finished-seat behavior,
reached a ranked terminal result, then required 1/3, 2/3 and 3/3 rematch consent before a fresh
same-room game. A four-player Extended double-deck room showed 1/4 through 4/4 waiting/start states,
hidden remote hands, attack, defense, clockwise Pass/handoff, and stable-seat reconnect. A clean
incognito first-use four-player Extended double-deck bot flow showed deck onboarding, then
multiplayer onboarding, before any game was created; the 108-card game began only after both were
acknowledged. Two fresh `/play` tabs showed neutral capability loading followed by setup with no
false error. Hint output, the default two-player Classic room, Tutorial, Rules, both guides, social
metadata, exact Russian `Вы взяли 1 карту`, client-visible Not Found, and EN/RU Privacy also passed.

Final health showed approximately 2.0 GiB `MemAvailable`, 138.4 MiB resident swap, `si=0`/`so=0`,
zero current memory PSI, and no kernel OOM evidence. Swap grew by only about 0.3 MiB during the image
build and then remained stable. Kiba, Husky Tracking and Kennel Operations returned HTTP 200; Kiba
containers were healthy with zero restarts and `OOMKilled=false`; Docker, Caddy and Amnezia remained
running; backup and both monitor timers remained active; and both monitor services most recently
exited successfully. Backend, PostgreSQL, Caddy, Husky, Kennel, Amnezia, Docker runtime, firewall,
SSH and OS packages were not restarted, rebuilt, reconfigured, or upgraded. No release tag was
created or moved.
