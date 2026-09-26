# Cyber Durak / Kiba

Cyber Durak is a browser-based shedding card game with a custom arithmetic ruleset. Its historical
gameplay codename is **Kiba**. The repository contains the complete two-player 36-card rules engine,
a deterministic baseline bot, an Alpha process-local REST game-session layer, optional persistent
account identity with completed-match history, statistics, XP, derived levels and achievements, and
persistent visual cosmetic rewards, plus a responsive playable Angular human-versus-bot table. The
Alpha 2 also provides process-local private two-player rooms with invite links, an Angular lobby,
authoritative WebSocket actions, and browser-session reconnect credentials.
Registration is never required to play. Completed authenticated bot and private-PvP matches persist
history and progression; guest results remain unsaved, and guests always use the classic appearance.
The single Angular application defaults new visitors to English and provides an instant `EN | RU`
switch without reloading or resetting active play. An explicitly saved guest or account language
continues to be respected.

## Repository structure

```text
.
├── backend/                 FastAPI application, Python tooling, and tests
├── docs/                    Authoritative gameplay, product, and architecture documents
├── frontend/                Angular application and unit tests
├── .github/workflows/ci.yml Push and pull-request checks
├── docker-compose.yml       Local development stack
└── AGENTS.md                Guidance for coding agents
```

## Prerequisites

- Node.js 24.15 or newer in the Node 24 release line, with npm
- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/) for Python dependency management
- Docker Desktop or Docker Engine with Docker Compose (optional)
- PostgreSQL 17-compatible database for account features (provided by Docker Compose)

## Run locally

The simplest complete setup is Docker Compose because it includes PostgreSQL and applies migrations:

```bash
docker compose up --build
```

Open <http://localhost:14200>, then choose **Играть с ботом / Play vs bot** or **Играть с другом /
Play with friend**. Guest play works immediately without an account. **Войти / Log in** in the
navigation provides optional registration, login, and profile identity.

To run the application services directly, first provide a PostgreSQL database URL and apply the
schema:

```bash
cd backend
uv sync
export KIBA_DATABASE_URL=postgresql+psycopg://kiba:password@localhost:5432/kiba
uv run alembic upgrade head
uv run uvicorn --app-dir src kiba_api.main:app --reload --port 18000
```

```bash
cd frontend
npm ci
npm start
```

Open the frontend at <http://localhost:14200>. The backend health check is available at
<http://localhost:18000/health> and returns:

```json
{"status":"ok"}
```

The product shell provides these routes:

- **Играть** (`/play`) creates or resumes the current in-memory browser session;
- **Играть с другом** (`/pvp`) creates an invite-only room; `/join/<code>` opens a shared invite;
- **Обучение** (`/tutorial`) is a short interactive introduction to Kiba's core mechanics;
- **Правила / Rules** (`/rules`) is the complete user-facing rulebook in both supported languages.
- **Войти** (`/login`) and **Создать аккаунт** (`/register`) provide optional identity;
- **Профиль** (`/profile`) allows an authenticated player to update their display name or log out.
- **История партий** (`/profile/history`) shows private completed-match summaries for an
  authenticated player.
- **Достижения** (`/profile/achievements`) shows the server-owned catalogue and private unlocks;
  the profile also shows ledger-derived XP and level progress.
- **Оформление** (`/profile/cosmetics`) shows unlocked card backs, table themes, and profile frames
  and lets an authenticated player equip them.
- **Privacy** (`/privacy`) and **Terms** (`/terms`) are public in English and Russian. An
  authenticated profile can download a versioned JSON copy of account data or permanently delete
  the account after password confirmation.

Click **Играть с ботом** to create a bot game, or **Играть с другом** to create a private room and
copy its current-origin invite link. The invited player may join with a guest nickname or their
account identity. Select cards by tapping or clicking them, and use the actions
offered below the hand. Rules and Tutorial remain available from the compact navigation during a
game; returning to Play preserves the current frontend session while the page remains open. The
Angular development server proxies `/api` to the local backend, so both services must be running.
The UI works from public server state only: bot cards and future draw-pile order remain hidden, and
the backend decides whether every submitted move is legal.

Guest language choice and the minimal first-run Welcome flag are stored in browser `localStorage`.
The Welcome is optional, links to the nine-step tutorial or directly to guest play, and stores no
profile or game state. An authenticated account stores its
preferred language, restores it after login on another device, and uses it for verification and
password-reset email. API presentation catalogues use `Accept-Language`; game and protocol codes
remain language-neutral.

The Human-vs-Bot page stores only its opaque active-game ID in tab-scoped `sessionStorage`. Reloading
the page retrieves the same authoritative public state while that process-local server session
exists; no cards or complete game state are stored in the browser. A backend restart, expiry, or
deployment can still make an unfinished game unavailable by design.

Kiba is available as an EU/international portfolio public beta at <https://cyberdurak.com>, hosted
on Netherlands/EEA infrastructure. English is primary and Russian is an optional secondary
language. Guest play stays
registration-free. The public controller/contact shown in Privacy and Terms is Oleg Shaltaev,
Finland, `support@cyberdurak.com`; the mailbox is monitored and current production providers are
listed in `docs/PROCESSORS.md`. There are currently no analytics, advertising, or marketing
trackers.

Create and inspect an Alpha human-versus-bot game with:

```bash
curl -X POST http://localhost:18000/api/games
curl http://localhost:18000/api/games/<game_id>
```

Submit one of `INITIAL_ATTACK`, `DEFEND`, `TRANSFER`, `THROW_IN`, `TAKE`, or `BITO` to
`POST /api/games/<game_id>/actions`. Card actions use stable codes such as `6C`, `10H`, `QS`, `KD`,
and `AC`. Interactive OpenAPI documentation is available at <http://localhost:18000/docs>.

The Alpha 2 backend also exposes process-local private Human-vs-Human rooms:

```text
POST /api/pvp/rooms
POST /api/pvp/rooms/{invite_code}/join
GET  /api/pvp/rooms/{invite_code}
WS   /api/pvp/rooms/{invite_code}/ws
```

Guest create/join requests use `{"nickname":"Игрок"}`; an authenticated account instead supplies
its saved display name. Create and join return an opaque participant reconnect credential. A client
opens the room WebSocket, sends that credential in an initial `AUTH` JSON message, then exchanges
versioned `ACTION` messages and complete participant-specific `STATE` snapshots. Only the requesting
participant's hand is sent; the opponent is a public name plus hand count, and future draw-pile order
is never exposed. The development proxy supports both HTTP and WebSocket traffic on the same
`/api` origin, including the documented LAN frontend URL.

The Angular room client stores its reconnect credential in `sessionStorage`, never in the invite
URL, and reconnects to the participant-specific state after ordinary refresh/navigation. Invite
links are built from the browser's current origin, so a LAN visitor receives a LAN-usable link.
Unexpected socket loss uses bounded exponential retry; returning from a backgrounded page or an
offline period verifies/reconnects and replaces the UI with the latest authoritative state. A
confirmed explicit **Exit / Выйти** closes the active room neutrally for both participants, clears
that room's local resume credential, and neither reconnects nor records a competitive result.
Ordinary refresh and temporary network loss still preserve the participant's seat and room.
Private rooms, active games, connection state, and reconnect credentials are process-local and are
lost when the backend restarts. Completed authenticated PvP participant summaries, XP, achievements,
and cosmetics are persistent and appear in private history; guests remain registration-free and
unsaved. There is no matchmaking, rating, or chat.

Alpha sessions are held only in backend process memory and are lost when the backend restarts. The
API sends the human hand and public table state, but never sends bot cards or hidden draw-pile order.
User accounts, opaque auth sessions, and compact summaries of completed authenticated matches are
stored in PostgreSQL and survive backend restart. Exactly-once XP ledger entries and achievement
unlocks are also persistent; level is derived from total ledger XP. Active games are deliberately
not persisted.
Games started as a guest stay guest games even if the player signs in before completion; games
started while signed in retain that original account association through logout. Guest matches are
never retroactively claimed.

The auth API consists of:

```text
POST  /api/auth/register
POST  /api/auth/login
POST  /api/auth/logout
GET   /api/auth/me
PATCH /api/profile
GET   /api/stats
GET   /api/matches?limit=20&offset=0&opponent_type=PVP
GET   /api/progression
GET   /api/achievements
GET   /api/cosmetics
PATCH /api/profile/cosmetics
```

Only authenticated completed bot or PvP match perspectives grant persistent progression. Base
awards are 100 XP for a win, 50 XP for a draw, and 25 XP for a loss; achievement bonuses are added once when their
server-defined condition is first met. Level and achievement milestones may permanently unlock
optional card backs, table themes, and profile frames. Progression and cosmetics do not affect any
gameplay rule or bot behavior; there is no currency, shop, or purchase flow.

Authentication uses an HTTP-only same-site cookie. For local HTTP development `Secure` is disabled;
set `KIBA_AUTH_COOKIE_SECURE=true` behind production HTTPS. Copy `.env.example` only as a starting
point and never commit real credentials. Email verification and password reset are intentionally
deferred production-hardening work. Local HTTP auth accepts the documented frontend port on private
LAN IP addresses; production HTTPS requires explicitly configured trusted origins.

## Checks

Backend:

```bash
cd backend
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run alembic upgrade head
```

Frontend:

```bash
cd frontend
npm ci
npm run lint
npm run format:check
npm test -- --watch=false
npm run build
```

Use `npm run format` in `frontend/` and `uv run ruff format .` in `backend/` to apply formatting.

## Docker Compose

Build and start the PostgreSQL-backed development stack:

```bash
docker compose up --build
```

The frontend is exposed on host port `14200` and the backend on loopback-only host port `18000`.
PostgreSQL has no host port mapping and is reachable only by the Kiba backend over the Compose
network, avoiding conflicts with other local database projects.
Inside Compose, Angular and FastAPI continue to use ports `4200` and `8000`; the frontend proxy sends
relative `/api` requests directly to `backend:8000`. Source directories are mounted into the
containers, so both development servers reload when their source files change. Stop the stack with
`docker compose down`.

For an iPhone or another device on the same Wi-Fi, find the Mac's Wi-Fi address and open the frontend
through it:

```bash
ipconfig getifaddr en0
```

```text
http://<MAC_LAN_IP>:14200
```

Only the frontend URL is needed: its same-origin `/api` proxy reaches the backend. The development
server binds to all local interfaces for LAN access; no Mac address is hardcoded in the project.

For a physical-device private-PvP check:

1. open the LAN frontend URL on the first device and choose **Играть с другом**;
2. create a room and send its generated invite link to the second device;
3. join from the second browser, then briefly background/lock one device;
4. return to Kiba and confirm that it reconnects to the same seat and current table.

The backend host port remains loopback-only; phones need only the frontend URL because HTTP and
WebSocket `/api` traffic stays behind the Angular same-origin proxy. Active rooms cannot survive a
backend process restart.

The Compose database is stored in the `kiba-postgres-data` volume. The backend applies pending
Alembic migrations before starting. `docker compose down` preserves the volume; do not use `-v`
unless the local account database should also be deleted.

## Production-readiness preview

Phase 6A adds strict production configuration, email verification/password reset, request IDs,
security headers, `/ready`, non-root production images, and backup/restore tooling. It does **not**
deploy Kiba. See [`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md) and use
`.env.production.example` only as a placeholder checklist—never commit filled secrets.

The production contract requires **one backend process / one application worker** because active
Human-vs-Bot sessions and PvP rooms remain process-local. Production migrations are explicit:

```bash
cd backend && uv run alembic upgrade head
docker compose --env-file /secure/path/kiba.env -f docker-compose.prod.yml up --build -d
```

Development email links are available only in explicit development mode. Production refuses that
sender and requires generic SMTP configuration. Liveness is `/health`; database readiness is
`/ready`.

## Authoritative specifications

- [`docs/GAME_RULES.md`](docs/GAME_RULES.md) is the gameplay source of truth.
- [`docs/PRODUCT_BRIEF.md`](docs/PRODUCT_BRIEF.md) defines MVP and product scope.
- [`docs/IMPLEMENTATION_NOTES.md`](docs/IMPLEMENTATION_NOTES.md) defines the preferred technical
  direction.

Do not duplicate or silently reinterpret these specifications in implementation code. When they
conflict, follow the source-of-truth order above and document deliberate rule changes with the code
that implements them.
