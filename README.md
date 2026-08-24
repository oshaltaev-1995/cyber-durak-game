# Cyber Durak / Kiba

Cyber Durak is a planned browser-based shedding card game with a custom arithmetic ruleset. Its
historical gameplay codename is **Kiba**. Phase 0 is complete: the repository contains the Angular
frontend and FastAPI backend foundations, automated checks, and a local Docker Compose setup. It is
still a pre-gameplay build; the rules engine, bot, and multiplayer features are not implemented.

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
uv run uvicorn kiba_api.main:app --reload
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

No database or environment file is required in this bootstrap phase.

## Authoritative specifications

- [`docs/GAME_RULES.md`](docs/GAME_RULES.md) is the gameplay source of truth.
- [`docs/PRODUCT_BRIEF.md`](docs/PRODUCT_BRIEF.md) defines MVP and product scope.
- [`docs/IMPLEMENTATION_NOTES.md`](docs/IMPLEMENTATION_NOTES.md) defines the preferred technical
  direction.

Do not duplicate or silently reinterpret these specifications in implementation code. When they
conflict, follow the source-of-truth order above and document deliberate rule changes with the code
that implements them.
