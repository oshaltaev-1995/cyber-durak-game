# Cyber Durak / Kiba

Cyber Durak is a browser-based shedding card game with a custom arithmetic ruleset. Its historical
gameplay codename is **Kiba**. The repository contains the complete two-player 36-card rules engine,
a deterministic baseline bot, an Alpha process-local REST game-session layer, optional persistent
account identity with completed-match history, statistics, XP, derived levels and achievements, and
a responsive playable Angular human-versus-bot table. Registration is never required to play;
guest results and progression are not persisted.

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

Open <http://localhost:14200>, then click **Играть**. Guest play works immediately without an
account. **Войти** in the navigation provides optional registration, login, and profile identity.

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
- **Обучение** (`/tutorial`) is a short interactive introduction to Kiba's core mechanics;
- **Правила** (`/rules`) is the complete user-facing Russian rulebook.
- **Войти** (`/login`) and **Создать аккаунт** (`/register`) provide optional identity;
- **Профиль** (`/profile`) allows an authenticated player to update their display name or log out.
- **История партий** (`/profile/history`) shows private completed-match summaries for an
  authenticated player.
- **Достижения** (`/profile/achievements`) shows the server-owned catalogue and private unlocks;
  the profile also shows ledger-derived XP and level progress.

Click **Играть** to create a new game, select cards by tapping or clicking them, and use the actions
offered below the hand. Rules and Tutorial remain available from the compact navigation during a
game; returning to Play preserves the current frontend session while the page remains open. The
Angular development server proxies `/api` to the local backend, so both services must be running.
The UI works from public server state only: bot cards and future draw-pile order remain hidden, and
the backend decides whether every submitted move is legal.

Create and inspect an Alpha human-versus-bot game with:

```bash
curl -X POST http://localhost:18000/api/games
curl http://localhost:18000/api/games/<game_id>
```

Submit one of `INITIAL_ATTACK`, `DEFEND`, `TRANSFER`, `THROW_IN`, `TAKE`, or `BITO` to
`POST /api/games/<game_id>/actions`. Card actions use stable codes such as `6C`, `10H`, `QS`, `KD`,
and `AC`. Interactive OpenAPI documentation is available at <http://localhost:18000/docs>.

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
GET   /api/matches?limit=20&offset=0
GET   /api/progression
GET   /api/achievements
```

Only authenticated completed matches grant persistent progression. Base awards are 100 XP for a
win, 50 XP for a draw, and 25 XP for a loss; achievement bonuses are added once when their
server-defined condition is first met. XP, levels, and achievements do not affect any gameplay
rule or bot behavior.

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

The Compose database is stored in the `kiba-postgres-data` volume. The backend applies pending
Alembic migrations before starting. `docker compose down` preserves the volume; do not use `-v`
unless the local account database should also be deleted.

## Authoritative specifications

- [`docs/GAME_RULES.md`](docs/GAME_RULES.md) is the gameplay source of truth.
- [`docs/PRODUCT_BRIEF.md`](docs/PRODUCT_BRIEF.md) defines MVP and product scope.
- [`docs/IMPLEMENTATION_NOTES.md`](docs/IMPLEMENTATION_NOTES.md) defines the preferred technical
  direction.

Do not duplicate or silently reinterpret these specifications in implementation code. When they
conflict, follow the source-of-truth order above and document deliberate rule changes with the code
that implements them.
