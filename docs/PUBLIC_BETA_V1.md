# KIBA Public Beta v1 release freeze

Status: **First stable Public Beta / portfolio release accepted**

- Production URL: <https://cyberdurak.com>
- Accepted revision: `3b52855589aa8cdfb5c90bf8319cd60c9b294a7d`
- Acceptance date: 2026-09-26
- Git tag: `public-beta-v1`

The accepted production revision completed the focused first-release correction series:

- R1: Human-vs-Bot refresh recovery using an opaque session identifier and authoritative server
  state.
- R2: responsive game-table layout, presentation-only turn reminder, and accessibility fixes.
- R3: first-run onboarding, interactive Tutorial, and Rules clarity.
- Physical-table release: individual hidden opponent cards and presentation-only card motion.
- R5: final Public Beta interaction polish.
- R6: explicit PvP Exit lifecycle and bounded adaptive large-hand geometry.

Independent production audits found no remaining P0 or P1 findings. The confirmed P2 in which an
explicit PvP Exit could strand the opponent waiting for reconnect was corrected in R6. This release
is accepted as suitable for portfolio use and a small Public Beta.

## Frozen v1 scope

Public Beta v1 remains the authoritative two-player Kiba experience: Human-vs-Bot and private
two-participant PvP. The following are not part of this release:

- real three-player gameplay;
- real four-player gameplay;
- multiplayer rules expansion;
- matchmaking;
- bot-strength redesign.

Existing three-seat and four-seat frontend fixtures are presentation prototypes only. Any future
three-player or four-player implementation must begin with a separate multiplayer rules/canon
phase. It must not extend the current production engine ad hoc or invent multiplayer rules in UI or
transport code.

## Non-blocking post-release follow-ups

These operational and quality follow-ups do not block acceptance of Public Beta v1:

- monitor transactional-email deliverability and sender reputation;
- configure external uptime monitoring;
- add an off-host disaster-recovery backup copy;
- perform an optional deeper accessibility and screen-reader audit.

The accepted application revision remains deployed as-is. This release-freeze record does not
authorize a rebuild, deployment, database change, or production-service restart.
