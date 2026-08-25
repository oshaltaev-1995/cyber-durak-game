# Cyber Durak / Kiba

Cyber Durak is a browser-based shedding card game with a custom arithmetic ruleset. Its historical
gameplay codename is **Kiba**. The repository contains the complete two-player 36-card rules engine,
a deterministic baseline bot, an Alpha process-local REST session layer, and a responsive playable
Angular human-versus-bot table.

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

## Run locally

Start the services in separate terminals:

```bash
cd backend
uv sync
uv run uvicorn --app-dir src kiba_api.main:app --reload
```

```bash
cd frontend
npm ci
npm start
```

Open the frontend at <http://localhost:4200>. The backend health check is available at
<http://localhost:8000/health> and returns:

```json
{"status":"ok"}
```

Click **Играть** to create a new game, select cards by tapping or clicking them, and use the actions
offered below the hand. The Angular development server proxies `/api` to the local backend, so both
services must be running. The UI works from public server state only: bot cards and future draw-pile
order remain hidden, and the backend decides whether every submitted move is legal.

Create and inspect an Alpha human-versus-bot game with:

```bash
curl -X POST http://localhost:8000/api/games
curl http://localhost:8000/api/games/<game_id>
```

Submit one of `INITIAL_ATTACK`, `DEFEND`, `TRANSFER`, `THROW_IN`, `TAKE`, or `BITO` to
`POST /api/games/<game_id>/actions`. Card actions use stable codes such as `6C`, `10H`, `QS`, `KD`,
and `AC`. Interactive OpenAPI documentation is available at <http://localhost:8000/docs>.

Alpha sessions are held only in backend process memory and are lost when the backend restarts. The
API sends the human hand and public table state, but never sends bot cards or hidden draw-pile order.

## Checks

Backend:

```bash
cd backend
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
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

Build and start both development services:

```bash
docker compose up --build
```

The frontend is exposed on port 4200 and the backend on port 8000. Source directories are mounted
into the containers, so both development servers reload when their source files change. Stop the
stack with `docker compose down`.

No database or environment file is required for the process-local Alpha session layer.

## Authoritative specifications

- [`docs/GAME_RULES.md`](docs/GAME_RULES.md) is the gameplay source of truth.
- [`docs/PRODUCT_BRIEF.md`](docs/PRODUCT_BRIEF.md) defines MVP and product scope.
- [`docs/IMPLEMENTATION_NOTES.md`](docs/IMPLEMENTATION_NOTES.md) defines the preferred technical
  direction.

Do not duplicate or silently reinterpret these specifications in implementation code. When they
conflict, follow the source-of-truth order above and document deliberate rule changes with the code
that implements them.
