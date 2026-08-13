# 🏗️ Enterprise Application Modernization Platform

> **SystemaOps Enterprise Platform · Language-agnostic · 12-Step Pipeline · Adapter-based · Live Version Detection · Git Checkpoint**

A production-grade Enterprise Application Modernization Platform built under the guidance of **SystemaOps**. It automatically ingests multi-language enterprise codebases (via ZIP upload or Git URL), detects technology stacks, analyzes dependency version upgrades against live package registries, recommends modernization recipes, and commits pre-migration git checkpoints.

---

## 🌐 12-Step Migration Pipeline Architecture

```text
Dashboard
  ↓
New Migration (Upload ZIP / Git Repository URL)
  ↓
1. Application Discovery (Language, Framework & Build Detection)
  ↓
2. Project Profile Fingerprint
  ↓
3. Dependency Detection (requirements.txt, package.json, pom.xml)
  ↓
4. Live Version Detection (PyPI, npm, Maven Central lookup with caching)
  ↓
5. Dependency Update Review (Interactive package selection)
  ↓
6. Apply Dependency Updates & Syntax Validation
  ↓
7. AI Recommendation Layer (Context-aware recipe suggestions)
  ↓
8. Recipe Selection (Grouped by ecosystem with Select All / Deselect All)
  ↓
9. Recipe Dependency Analysis (Topological sort & phase ordering)
  ↓
10. Conflict Resolution Manager (Rule-based conflict detection)
  ↓
11. Migration Plan Generation
  ↓
12. Git Checkpoint Commit & Structure-Preserved ZIP Download (<project-name>-modernized.zip)
```

---

## ✨ Key Features

| Feature | Detail |
|---------|--------|
| 🎨 **SystemaOps Brand Theme** | SystemaOps logo integration (`SystemaOps-logo.webp`), primary teal (`#1d7f8a`), warning gold (`#f2bd22`), and Odoo purple header styling. |
| ✋ **Manual Step Execution** | Every pipeline stage requires explicit user action (`Proceed to Next Step →`), giving enterprise engineers total visibility. |
| ⚡ **Parallel Version Registry Lookup** | Concurrent HTTP pool with 25 workers and process-level caching for sub-second package resolution. |
| 📦 **Smart ZIP Naming** | Reads uploaded project/repo name and generates downloads named `<project-name>-modernized.zip`. |
| 🎯 **Automated Git Checkpoint** | Initializes Git if needed, stages updated files, and creates an atomic commit before any transformation. |
| 🛡️ **Lockfile Protection** | `pnpm-lock.yaml`, `package-lock.json`, `Pipfile.lock` are parsed and reported but **never modified**. |
| 🪟 **Windows Native** | All process runners handle Windows CMD wrappers and paths seamlessly with zero `[WinError 2]` issues. |

---

## 🛠️ Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **ASGI Server**: Uvicorn with WatchFiles hot-reloading
- **Database**: SQLAlchemy ORM + async SQLite (`aiosqlite`)
- **Version Control**: GitPython
- **HTTP Client**: HTTPX & urllib

### Frontend
- **Framework**: React 19 + TypeScript
- **Build Tool**: Vite 8.x
- **Theme**: SystemaOps Enterprise Design System
- **Routing**: React Router DOM v7
- **HTTP Client**: Axios (`/api/v1`)

---

## 🚀 Quick Start

### 1. Backend Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # On Windows
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your browser to run the platform!
