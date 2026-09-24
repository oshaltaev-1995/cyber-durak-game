# Kiba lightweight processing record

Version 1.0 — 2026-09-25.

## Controller and scope

- Controller: **Oleg Shaltaev**
- Location: **Finland**
- Contact: **support@cyberdurak.com**
- Service: free browser-based Kiba EU/international public beta; guest or optional account;
  Human-vs-Bot and private PvP.
- Planned infrastructure: Netherlands/EEA. Production is not deployed.

## Processing

| Purpose | People | Personal-data categories | Recipients/categories | Retention |
| --- | --- | --- | --- | --- |
| Guest gameplay/private room | Guests and optional-account players | Temporary nickname, locale, game/connection/reconnect state | Controller; planned hosting processor | Process-local TTL/restart |
| Account and authentication | Registered users | UUID, email, display name, locale, password hash, session/token digests and timestamps | Controller; planned hosting and transactional-email processors | Account lifetime; security expiries |
| Saved history and progression | Registered users and PvP opponent snapshots | Match summaries, opponent snapshot/UUID, statistics source counters, XP, achievements, cosmetics | Controller; planned hosting processor | Account lifetime; opponent record anonymized on deletion |
| Security, abuse prevention and reliability | Visitors/users | Request IDs, routes/status/duration, rate-limit and infrastructure connection metadata | Controller; planned hosting/monitoring providers if approved | Logs target 30 days; in-memory windows shorter |
| Verification and recovery email | Registered users | Email, display name, locale, one-use URL, delivery metadata | Controller; planned transactional-email processor | Token TTL plus operational cleanup/provider retention |

Proposed legal bases and field-level details are in `PRIVACY_DATA_MAP.md`. Final legal-basis,
children, consumer-law, provider/DPA and international-transfer determinations remain on the legal
review checklist.

## Safeguards

Argon2id password hashing; opaque hashed server-side sessions/tokens; HTTP-only secure production
cookies; same-origin/Origin enforcement; least-information participant serialization; hidden hands
and draw order; input/rate limits; request correlation; generic production errors; non-root
containers; one-worker authoritative session model; PostgreSQL access separation; planned encrypted
backup/access controls and HTTPS edge.

No analytics, advertising, marketing pixels, payment processing, public profiles, matchmaking, or
rating processing exists. Active rooms/games are not stored in PostgreSQL.
