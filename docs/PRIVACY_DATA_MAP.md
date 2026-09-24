# Kiba privacy data map

Status: Phase 6A.6 pre-launch audit, 2026-09-25. This is a technical processing inventory for an
EU/international public beta, not a legal opinion. The controller is **Oleg Shaltaev, Finland,
support@cyberdurak.com**.

## Persistent account data

| Category | Actual fields/examples | Source and purpose | Storage / recipients | Retention and deletion | Export | Proposed GDPR basis |
| --- | --- | --- | --- | --- | --- | --- |
| Account/profile | user UUID; email and normalized email; display name; `ru`/`en` preference; email-verification timestamp; active flag; created, updated, and last-login timestamps | Registration and profile actions; identity, login, recovery, localization | PostgreSQL; controller and reviewed hosting operator | Until account deletion; hard-deleted from live DB | Yes | Service/account performance; **LEGAL REVIEW REQUIRED** for final Art. 6 wording |
| Authentication | Argon2id password hash; opaque auth-session SHA-256 digest; created/last-seen/expiry/revocation times | Password authentication and revocable login sessions | PostgreSQL; never returned by export/API | Session absolute lifetime 30 days and idle lifetime 14 days; deleted with account; expired/revoked-row cleanup target within 7 days after Phase 6B operations are configured | No | Service security and controller's legitimate interests |
| Account tokens | Email-verification or password-reset token digest; type; creation, expiry and consumed time | One-use verification/recovery | PostgreSQL; raw token exists only in the delivered link | Verification TTL 24 hours; reset TTL 30 minutes; consumed/expired-row cleanup target within 7 days; deleted with account | No | Service/account performance and security legitimate interests |
| Match summaries | BOT/PVP; user seat; outcome; timestamps/duration; final hand counts; accepted-action, transfer, take, throw-in, max-transfer and arithmetic-mean counters; shared PvP match ID; opponent user UUID where applicable; opponent display-name snapshot | Authoritative completed authenticated matches; history/statistics/progression | PostgreSQL; user receives only their perspective | Until account deletion. Another user's retained PvP row is anonymized when this user deletes | Yes, excluding opponent UUID | Requested account history/service; **LEGAL REVIEW REQUIRED** for opponent-name snapshot basis |
| Progression | XP ledger reason/amount/match reference/time; achievement code/unlock time; cosmetic unlock code/time; cosmetic loadout | Account progression and visual customization | PostgreSQL | Until account deletion | Yes | Requested account feature/service performance |

Passwords, password hashes, session/token digests, raw tokens, cookies, reconnect credentials, hidden
hands, future draw order, database credentials, and other users' private identity data are never
included in self-service export.

## Process-local and temporary play data

| Category | Actual data | Purpose / location | Retention / deletion | Export | Proposed basis |
| --- | --- | --- | --- | --- | --- |
| Bot game sessions | Immutable active `GameState`, hidden bot hand/draw order, user UUID association, accepted-action summary and completion presentation | Backend memory; play against bot | Six-hour active inactivity TTL; 30-minute completed TTL; backend restart clears all; deletion detaches account and makes the active session effectively guest | No | Requested game service |
| Private PvP rooms | Active `GameState`, invite code, participant ID, seat, nickname/display name, optional captured user UUID, locale, reconnect credential digest/value in server memory, connection and accepted-action state | Backend memory; authoritative private room/reconnect | 30-minute waiting TTL; 15-minute completed TTL; two-hour disconnected active TTL; backend restart clears all. Account deletion detaches that user's identity | No | Requested game service and security legitimate interests |
| Guest identity | Guest nickname and locale in a private room | Temporary participant presentation | Room lifetime only | No | Requested game service |

Signing in or out after room join does not reassign captured participant identity. A deleted user's
association is explicitly detached so later completion cannot persist against a missing account.

## Email and delivery

The application uses the account email, display name, preferred locale, message purpose, and a
one-use verification/reset URL to deliver **verification and password-recovery only**. There is no
newsletter or marketing email. Development delivery is a process-local outbox plus local logs and
must never run in production. Production SMTP is provider-neutral and not configured yet. A final
processor/DPA/data-location review is a deployment gate.

## Request, abuse-prevention, and operational metadata

- Application logs contain request ID, method, route template/path, response status, and duration.
  They are designed not to contain credentials, cookies, raw account/reconnect tokens, hidden cards,
  or future draw order.
- Process-local rate limits use direct network-peer information and operation/account keys. The
  counters reset on restart and are not account history.
- The application does not deliberately log client IP addresses. Hosting/reverse-proxy logs may
  contain IP address, timestamp, requested route, status, and user-agent/network metadata; Phase 6B
  must configure the exact log format and 30-day target retention.
- Request IDs support diagnostics and incident correlation. Proposed basis: security/reliability
  legitimate interests.

## Browser storage

| Item | Contents | Lifetime / deletion | Purpose |
| --- | --- | --- | --- |
| `kiba_session` (configurable name) | Opaque auth token; `HttpOnly`, `SameSite=Lax`, `Secure` in production | Browser cookie backed by server session; logout/deletion clears it | Necessary authenticated session |
| `kiba.preferred-locale` localStorage | `en` or `ru` | Until user changes it or clears site data | Functional language preference |
| `kiba:pvp:<invite-code>` sessionStorage | Participant ID, seat, reconnect credential | Browser-tab session or explicit cleanup/site-data clearing | Functional private-room reconnect |

No analytics, advertising, behavioural-tracking, or marketing scripts/cookies were found in the
Phase 6A.6 audit. Reassess consent requirements before adding any non-essential tracking.

## Backups, providers, and transfers

Database backups contain the persistent tables above and must be encrypted/access-restricted. The
initial target retention is 30 days. Live deletion does not rewrite historical backup archives;
deleted data may remain until normal rotation and may be used only for disaster recovery. Restoring
a backup requires applying subsequent deletion obligations operationally where applicable —
**LEGAL/OPERATIONS REVIEW REQUIRED**.

The intended production region is the Netherlands/EEA. No production provider is active yet.
Hosting, SMTP, DNS and any monitoring provider must be entered in `PROCESSORS.md`, reviewed for DPA
and transfer safeguards, and reflected in the public policy before launch.

## Data-subject rights handling

The product offers authenticated JSON export, profile-name/language correction, and password-
confirmed account deletion. Restriction, objection, exceptional correction, or inaccessible-account
requests use the manual process in `DATA_RIGHTS_RUNBOOK.md`. Whether a specific right applies depends
on context and legal basis; unresolved cases are marked **LEGAL REVIEW REQUIRED**, not guessed.
