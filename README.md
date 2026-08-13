# 🏗️ SystemaOps Enterprise Application Modernization Platform

> **Language-Agnostic · 11-Stage Async Pipeline · PostgreSQL Persistent Source of Truth · Celery & Redis Task Engine · Sandboxed Execution · Automated Git Checkpoints & Rollback**

A production-grade Enterprise Application Modernization and Migration Platform. It ingests legacy enterprise codebases, runs multi-language static discovery, computes deterministic recipe suitability scores, orders recipe execution plans via topological graph sorting, processes multi-stage modernization tasks asynchronously using Celery & Redis, sandboxes OS subprocesses against security threats, validates compilation and unit tests, and maintains automated Git checkpoints for 100% safe rollback capabilities.

---

## 🌐 11-Stage Migration Pipeline Architecture

```text
User / Ingestion (Upload ZIP / Git Repository)
   ↓
FastAPI Ingestion Endpoint
   ↓
PostgreSQL Database (Source of Truth)
   ↓
Redis Message Broker ➔ Celery Worker Fleet
   ↓
1. DISCOVERY          (Workspace Directory Scan & File Manifest Parsing)
   ↓
2. PROFILE            (Language, Framework, Library & Build System Fingerprinting)
   ↓
3. RECOMMENDATION     (Deterministic Rule/Scoring Engine Recipe Evaluation)
   ↓
4. PLAN               (Migration Plan Construction & Execution Target Ordering)
   ↓
5. RECIPE_VALIDATION  (Topological Graph Resolution & Cycle/Conflict Detection)
   ↓
6. TRANSFORMATION     (Pre-Migration Git Checkpoint Commit + OpenRewrite / Adapter Execution)
   ↓
7. COMPILE            (Build Compilation Validation & Syntax Verification)
   ↓
8. TEST               (Unit Test Runner Execution & Pass/Fail Metrics Verification)
   ↓
9. QUALITY            (Skipped / Not Implemented in Current Capability Profile)
   ↓
10. SECURITY          (Skipped / Not Implemented in Current Capability Profile)
   ↓
11. FINALIZE          (Persist Results, Test Outputs & Migration Verification Report)
```

---

## ✨ Key Technical Capabilities

| Feature | Technical Detail |
|---------|------------------|
| 🐘 **PostgreSQL Source of Truth** | Production-ready persistent storage powered by **SQLAlchemy 2.0**, **asyncpg**, and **Alembic** schema migrations. Maintains full execution history across runs, stages, results, and reports. |
| ⚡ **Async Worker Architecture** | Offloads long-running modernization operations out of FastAPI handlers to **Celery Workers** backed by a **Redis** message broker. |
| 🛡️ **Git Checkpoint & Safe Rollback** | Creates pre-transformation commit checkpoints. Detects dirty workspace state before starting and verifies post-checkpoint integrity. Automatically executes `git reset --hard` to restore the repository if transformation, compilation, or unit tests fail. |
| 🔒 **Secured Host Subprocess Sandbox** | Wraps command execution (`run_secured_command`): enforces workspace boundary path isolation, blocks symlink escapes, strips host environment secrets via `SAFE_ENV_ALLOWLIST`, executes with `shell=False`, and enforces a 300s timeout. |
| 🎯 **Deterministic Recipe Intelligence** | Rule and scoring-based recipe engine. Uses **NetworkX** directed graphs for topological sorting, transitive dependency resolution, version compatibility checks, and dependency cycle detection (`RECIPE_DEPENDENCY_CYCLE`). |
| 📊 **Database-Driven Verification Reporting** | Exposes `/api/v1/migration/result/{run_id}/report` compiling stage metrics, stage durations, recipe execution status, compilation stdout/stderr, test pass/fail counts, git checkpoint commit SHAs, and security error classifications. |
| 🪟 **Windows & Linux Native** | Cross-platform process handlers seamlessly managing Windows paths, line endings, and CMD executable resolution. |

---

## 🛠️ Technology Stack

### Backend & Async Infrastructure
- **API Framework**: FastAPI (Python 3.10+) & Uvicorn
- **Database Layer**: PostgreSQL 16 (or SQLite fallback) with SQLAlchemy 2.0 & Alembic
- **Async Drivers**: `asyncpg` / `pg8000` & `aiosqlite`
- **Task Worker**: Celery 5.4 with Redis 5.0 Broker & Result Backend
- **Graph & Math Logic**: NetworkX (Topological Sorting & Dependency Graphs)
- **Version Control**: GitPython & Native Git CLI
- **Language Adapters & Engines**: OpenRewrite (Java), Ruff & AST (Python), ESLint/NPM (Node.js)

### Frontend
- **Framework**: React 19 + TypeScript
- **Build Tool**: Vite 8.x
- **UI & Theme**: SystemaOps Enterprise Design System (Primary Teal `#1d7f8a`, Warning Gold `#f2bd22`)
- **Routing**: React Router DOM v7
- **HTTP Client**: Axios (`/api/v1`)

---

## 🚀 Developer Quick Start

### 1. Start Infrastructure Services (Docker)
```bash
# Start PostgreSQL and Redis containers
docker compose up -d db redis
```

### 2. Backend Setup & Database Migrations
```bash
cd backend

# Create & activate virtual environment
python -m venv .venv
.venv\Scripts\activate      # On Windows (or source .venv/bin/activate on Linux)

# Install dependencies
pip install -r requirements.txt

# Run PostgreSQL database migrations
alembic upgrade head

# Start FastAPI server (with 1GB upload limit)
$env:MAX_UPLOAD_SIZE_MB="1024"; uvicorn app.main:app --port 8000 --reload
```


### 3. Start Celery Background Worker
In a new terminal:
```bash
cd backend
.venv\Scripts\activate
celery -A app.workers.celery_app worker --loglevel=info --pool=solo

```

### 4. Frontend Setup
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your browser to access the platform UI!

---

## 🧪 Running Unit & Integration Tests

```bash
cd modernization-platform

# Run all unit tests including Git safety, sandbox isolation, and reporting
$env:PYTHONPATH=".;backend"
backend\.venv\Scripts\python -m pytest tests/unit/test_git_safety.py -vv

# Run PostgreSQL integration test
backend\.venv\Scripts\python -m pytest tests/unit/test_postgres_integration.py -vv
```

