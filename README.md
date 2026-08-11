# Enterprise Application Modernization & Migration Platform

A research-level, **language-independent**, **adapter-based**, **capability-driven** platform for enterprise application modernization and migration.

## Architecture

```
ANY APPLICATION
      ↓
ZIP / GIT URL
      ↓
SECURE INGESTION
      ↓
UNIVERSAL DISCOVERY
      ↓
TECHNOLOGY FINGERPRINT
      ↓
CAPABILITY REGISTRY
      ↓
MIGRATION ASSESSMENT
      ↓
TARGET RECOMMENDATION
      ↓
MIGRATION PLAN
      ↓
USER APPROVAL
      ↓
DRY RUN
      ↓
MIGRATION (deterministic — OpenRewrite / Ruff)
      ↓
BUILD / TEST / SECURITY VALIDATION
      ↓
BEFORE / AFTER DIFF
      ↓
CHANGED FILE EXPLORER
      ↓
MIGRATION REPORT
      ↓
DOWNLOAD MODERNIZED APPLICATION
```

## Technology Stack

| Layer     | Technology                     |
|-----------|-------------------------------|
| Backend   | Python 3.11, FastAPI, Pydantic |
| Frontend  | React 18, TypeScript           |
| Database  | PostgreSQL 15                  |
| Workers   | Redis + Celery                 |
| Execution | Docker (sandboxed workers)     |

## Migration Connectors

| Language | Tool        | Status        |
|----------|-------------|---------------|
| Java     | OpenRewrite | ✅ AVAILABLE  |
| Python   | Ruff        | ✅ AVAILABLE  |
| C/C++    | clang-tidy  | 🔲 NOT_AVAILABLE |
| C#/.NET  | Roslyn      | 🔲 NOT_AVAILABLE |
| JavaScript | jscodeshift | 🔲 NOT_AVAILABLE |
| TypeScript | ts-morph  | 🔲 NOT_AVAILABLE |
| Go       | go fix      | 🔲 NOT_AVAILABLE |
| PHP      | Rector      | 🔲 NOT_AVAILABLE |
| COBOL    | —           | 🔲 NOT_AVAILABLE |

## Quick Start

```bash
# Clone the repo
git clone https://github.com/Shankar373/modernization-platform.git
cd modernization-platform

# Copy environment config
cp .env.example .env

# Start full stack with Docker Compose
docker-compose up --build

# Backend available at: http://localhost:8000
# Frontend available at: http://localhost:3000
# API Docs at:          http://localhost:8000/docs
```

## Development (without Docker)

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Project Structure

```
modernization-platform/
├── backend/          # FastAPI application
├── frontend/         # React + TypeScript UI
├── workers/          # Celery task workers
├── docker/           # Docker configs
├── docs/             # Architecture, ADRs, research
├── tests/            # Unit, integration, e2e tests
└── .env.example      # Environment template
```

## Docs

- [Architecture](docs/architecture.md)
- [ADR-001: Adapter Pattern](docs/adr/ADR-001-adapter-pattern.md)
- [Language Support Matrix](docs/research/language-support-matrix.md)

## License

MIT
