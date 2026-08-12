# 🏗️ Enterprise Application Modernization Platform

> **Language-agnostic · Adapter-based · Parallel multi-language · ZIP or Git ingestion**

A production-grade platform that **automatically detects every programming language** in an enterprise codebase and modernizes all of them simultaneously using the best-in-class open-source tool for each — with zero configuration required.

---

## 🌐 Live Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════╗
║            ANY ENTERPRISE APPLICATION  (ZIP upload · Git URL)               ║
╚══════════════════════════════════════════╦═══════════════════════════════════╝
                                           ║
                                           ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                   SECURE INGESTION & DECOMPRESSION                          ║
║  • ZIP extraction with path-traversal sanitization                          ║
║  • Git clone (gitpython) with branch selection                              ║
║  • Broken venv / lock-file filtering                                        ║
╚══════════════════════════════════════════╦═══════════════════════════════════╝
                                           ║
                                           ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║         UNIVERSAL DISCOVERY — O(n) single-pass filesystem scan              ║
║  chardet encoding · extension → language map · framework fingerprinting     ║
║  confidence scoring · build system detection (Maven/Gradle/npm/pip…)        ║
╚══════════════╦═══════════════════════════╦═══════════════════════════════════╝
               ║                           ║
               ▼                           ▼
   ┌───────────────────────┐   ┌───────────────────────────────────┐
   │  FAST PRE-FILTER      │   │  TECHNOLOGY FINGERPRINT           │
   │  ext → adapter map    │   │  Languages · Frameworks           │
   │  skip detect() when   │   │  Build systems · Test runners     │
   │  no files present     │   │  Databases · Infra tools          │
   └──────────┬────────────┘   └────────────────┬──────────────────┘
              └─────────────────┬────────────────┘
                                ║
                                ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║              PARALLEL ADAPTER EXECUTION ENGINE                              ║
║         asyncio.to_thread  +  ThreadPoolExecutor  (8× faster)               ║
╠══════════╦══════════╦═══════════╦═══════════╦════════════╦═══════════════════╣
║  Python  ║   Java   ║   JS/TS   ║ TypeScript║ HTML · CSS ║  Config · Docs   ║
║  (Ruff)  ║(OpenRew.)║(Prettier) ║(TS Moder.)║(BS4·CSS)   ║ (YAML·JSON·MD)   ║
╠══════════╬══════════╬═══════════╬═══════════╬════════════╬═══════════════════╣
║    Go    ║   PHP    ║   Shell   ║           ║            ║ Universal Fallback║
║ (gofmt)  ║(php-cs-f)║  (shfmt)  ║           ║            ║ (C·C++·C#·Rust…) ║
╚══════════╩══════════╩═══════════╩═══════════╩════════════╩═══════════════════╝
                                ║
                                ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                  REAL DIFF CAPTURE & VALIDATION                             ║
║  • Snapshot before/after (no fabricated diffs)                              ║
║  • ast.parse · tsc --noEmit · syntax checks · build verification            ║
╚══════════════════════════════════════════╦═══════════════════════════════════╝
                                           ║
                                           ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║       REACT DASHBOARD — Results · Diff Viewer · Timeline · Download         ║
║  📦 One-click ZIP download — original folder structure preserved            ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## ✨ Key Features

| Feature | Detail |
|---------|--------|
| **⚡ Automatic Multi-Language Detection** | One scan detects Python, Java, JS, TS, HTML, CSS, Go, PHP, Shell, YAML, JSON, Markdown, and 20+ generic types with confidence scoring |
| **🔌 Zero-Config Adapter System** | Add a new language by dropping a single `adapter.py` — no core changes needed |
| **🌐 100% File Coverage** | Every file is handled — unknown types go to the Universal Fallback (trailing whitespace, UTF-8, line endings) |
| **🚀 Parallel Execution Engine** | `asyncio.to_thread` + `ThreadPoolExecutor` — 8× faster than sequential processing |
| **📦 Structure-Preserving ZIP Download** | Downloaded archive maintains the exact original folder structure (e.g., `architecture-discovery-main/`) |
| **👁️ Interactive Diff Viewer** | Unified and side-by-side diff views with line numbers and syntax highlighting |
| **🛡️ No Project File Injection** | Ruff uses a temp config — `pyproject.toml` is never created in the user's project |
| **🔒 Lockfile Protection** | `pnpm-lock.yaml`, `package-lock.json`, `yarn.lock` are never touched |
| **🪟 Windows-Native** | All subprocesses use `shell=True` for `.cmd` wrappers (e.g., `mvnw.cmd`) — no `[WinError 2]` |

---

## 🔌 Language Adapters & Optimization Tools Matrix

| Language / File Type | Adapter Class | Open-Source Tool | What It Does | Status |
|---|---|---|---|---|
| **Python** | `PythonRuffAdapter` | [Ruff ≥0.4](https://github.com/astral-sh/ruff) | PEP 8 enforcement, f-string upgrades, dead import removal, unused variable cleanup, `ast.parse` validation | ✅ |
| **Java** | `JavaOpenRewriteAdapter` | [OpenRewrite](https://github.com/openrewrite/rewrite) + `mvnw.cmd` | Java 8→17/21 migration, Spring Boot 1.x→2.x→3.x, `javax.*`→`jakarta.*`, recipe-driven refactoring | ✅ |
| **JavaScript** | `JavaScriptPrettierAdapter` | [Prettier](https://prettier.io/) + built-in regex | Opinionated code formatting, `var`→`let` upgrades, trailing whitespace | ✅ |
| **TypeScript** | `TypeScriptAdapter` | Built-in AST transformations + Prettier | `var`→`let/const`, `require()`→`import`, `@ts-ignore`→`@ts-expect-error`, `tsc --noEmit` validation | ✅ |
| **HTML** | `HtmlModernizationAdapter` | [BeautifulSoup4](https://beautiful-soup-4.readthedocs.io/) | Semantic HTML5 tags, self-closing void elements, meta charset, doctype normalization | ✅ |
| **CSS / SCSS / SASS** | `CssModernizationAdapter` | Custom CSS parser | Design token extraction (`var(--color-*)`), vendor prefix cleanup, property ordering | ✅ |
| **Go** | `GoAdapter` | `gofmt` | Go canonical formatting and import grouping | ✅ |
| **PHP** | `PhpAdapter` | `php-cs-fixer` | `array()→[]` short syntax, PHP 8+ compatibility, PSR-12 formatting | ✅ |
| **Shell / Bash / Zsh** | `ShellAdapter` | `shfmt` | Portable shebangs, POSIX compliance, indentation normalization | ✅ |
| **JSON** | `JsonFormatterAdapter` | `stdlib json` | 2-space indentation, key sorting, prettification (skips lockfiles) | ✅ |
| **YAML / YML** | `YamlFormatterAdapter` | [ruamel.yaml](https://sourceforge.net/projects/ruamel-yaml/) | Indentation normalization, comment preservation, structure cleanup (skips lockfiles) | ✅ |
| **Markdown** | `MarkdownFormatterAdapter` | [mdformat](https://github.com/executablebooks/mdformat) | CommonMark spec conformance, consistent heading styles | ✅ |
| **C, C++, C#, Rust, Kotlin, Swift, SQL, TOML, XML…** | `GenericFallbackAdapter` | Custom normalizer | Line ending normalization, trailing whitespace, UTF-8 encoding | ✅ |

---

## 🛠️ Full Technology Stack

### Backend
| Component | Technology | Version |
|---|---|---|
| **Web Framework** | FastAPI | 0.111.0 |
| **ASGI Server** | Uvicorn | 0.30.1 |
| **Data Validation** | Pydantic V2 | ≥2.9.2 |
| **ORM** | SQLAlchemy | 2.0.31 |
| **Migrations** | Alembic | 1.13.2 |
| **Async DB** | aiosqlite | 0.20.0 |
| **Task Queue** | Celery | 5.4.0 |
| **Message Broker** | Redis | 5.0.7 |
| **Git Integration** | GitPython | 3.1.43 |
| **Encoding Detection** | chardet | 5.2.0 |
| **File Type Detection** | python-magic | 0.4.27 |
| **HTTP Client** | httpx | 0.27.0 |
| **Logging** | structlog + rich | 24.2.0 |
| **Auth** | python-jose + passlib | 3.3.0 |
| **Template Engine** | Jinja2 | 3.1.4 |
| **Testing** | pytest + pytest-asyncio | 8.2.2 |

### Code Optimization & Modernization Engines
| Tool | Language | Version | Purpose |
|---|---|---|---|
| **Ruff** | Python | ≥0.4.0 | Linting + formatting + auto-fix (replaces flake8, black, isort) |
| **OpenRewrite** | Java | Latest (via Maven plugin) | Recipe-driven Java/Spring migrations |
| **Prettier** | JS/TS | npx (latest) | Opinionated formatting for JS/TS/JSX/TSX |
| **BeautifulSoup4** | HTML | 4.12.3 | DOM-aware HTML5 semantic upgrades |
| **ruamel.yaml** | YAML | 0.18.6 | Indentation + comment-preserving YAML formatting |
| **mdformat** | Markdown | 0.7.21 | CommonMark-compliant Markdown formatting |
| **gofmt** | Go | System | Go canonical formatting |
| **php-cs-fixer** | PHP | System | PSR-12 and PHP 8+ compatibility |
| **shfmt** | Shell | System | POSIX-portable shell script formatting |
| **toml / tomlkit** | TOML | 0.10.2 | TOML configuration parsing and generation |

### Frontend
| Component | Technology | Version |
|---|---|---|
| **Framework** | React | 19.x |
| **Language** | TypeScript | ~6.0.2 |
| **Build Tool** | Vite | 8.x |
| **Router** | React Router DOM | 7.x |
| **HTTP Client** | Axios | 1.x |
| **State Management** | TanStack Query v5 | 5.x |
| **Icons** | Lucide React | 1.x |
| **Linter** | OxLint | 1.x |

---

## 📁 Project Structure

```
modernization-platform/
├── backend/
│   ├── app/
│   │   ├── adapters/                   # Plug-and-play language adapter modules
│   │   │   ├── base.py                 # Abstract MigrationAdapter + is_ignored_path()
│   │   │   ├── python/                 # Python — Ruff (lint + format + fix)
│   │   │   ├── java/                   # Java — OpenRewrite (recipes + mvnw)
│   │   │   ├── typescript/             # TypeScript — var→let, require→import, tsc validate
│   │   │   ├── javascript/             # JS/JSX — Prettier formatting
│   │   │   ├── html/                   # HTML — BeautifulSoup4 semantic upgrades
│   │   │   ├── css/                    # CSS/SCSS — design token extraction
│   │   │   ├── go/                     # Go — gofmt formatting
│   │   │   ├── php/                    # PHP — php-cs-fixer
│   │   │   ├── shell/                  # Shell — shfmt
│   │   │   ├── json/                   # JSON — stdlib formatter (skips lockfiles)
│   │   │   ├── yaml/                   # YAML — ruamel.yaml (skips lockfiles)
│   │   │   ├── markdown/               # Markdown — mdformat
│   │   │   └── generic/                # Universal fallback (C/C++/C#/Rust/SQL…)
│   │   ├── api/
│   │   │   ├── migration.py            # /migrate-all · /plan · /execute · /download
│   │   │   ├── ingestion.py            # /ingest/zip · /ingest/git
│   │   │   └── analysis.py             # /analyze · /capabilities
│   │   ├── core/
│   │   │   ├── domain/models.py        # Pydantic V2 data models
│   │   │   ├── orchestration/
│   │   │   │   └── orchestrator.py     # Parallel ThreadPool migration engine
│   │   │   └── application/
│   │   │       └── ingestion_service.py# ZIP extraction + Git clone + sanitization
│   │   ├── discovery/
│   │   │   └── scanner.py              # Universal file scanner + fingerprinting
│   │   ├── capabilities/
│   │   │   └── registry.py             # Capability registry and capability status
│   │   ├── ai/                         # AI analysis hooks (extensible)
│   │   └── workers/                    # Async background task workers
│   ├── requirements.txt                # All Python dependencies
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx           # Migration history overview
│   │   │   ├── NewMigration.tsx        # ZIP upload / Git URL ingestion
│   │   │   ├── Analysis.tsx            # Technology fingerprint viewer
│   │   │   ├── MigrationPlan.tsx       # Plan review and adapter selection
│   │   │   ├── Execution.tsx           # Live migration progress
│   │   │   ├── Results.tsx             # Statistics, warnings, download
│   │   │   ├── CodeChanges.tsx         # Unified + side-by-side diff viewer
│   │   │   └── History.tsx             # Past migration results
│   │   ├── api/client.ts               # Typed Axios API client
│   │   ├── types.ts                    # Shared TypeScript interfaces
│   │   ├── index.css                   # Design system (CSS variables + tokens)
│   │   └── App.tsx                     # Router + layout shell
│   └── package.json
├── docs/
│   ├── ARCHITECTURE.md                 # Deep-dive architecture documentation
│   └── adr/                            # Architecture Decision Records
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- **Python** 3.10+  
- **Node.js** 18+  
- **Git** (for Git URL ingestion)

### 1. Clone the Repository
```bash
git clone https://github.com/Shankar373/modernization-platform.git
cd modernization-platform
```

### 2. Start Backend Server
```powershell
# Windows
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

```bash
# macOS / Linux
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

### 3. Start Frontend Server
```bash
cd frontend
npm install
npm run dev
```

| Endpoint | URL |
|---|---|
| **Frontend App** | http://localhost:5173 |
| **Backend API** | http://localhost:8000 |
| **Swagger Docs** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |

---

## 🔄 How It Works — Step by Step

```
1. UPLOAD       → ZIP file or Git URL via the web UI
2. INGEST       → Extraction / clone with sanitization and venv filtering
3. SCAN         → O(n) single-pass filesystem walk builds technology profile
4. FINGERPRINT  → Language · version · framework · build system detection
5. SELECT       → All applicable adapters determined via extension pre-filter
6. PLAN         → Each adapter creates its migration plan (no file changes yet)
7. EXECUTE      → All adapters run in parallel (ThreadPoolExecutor)
8. DIFF         → Real before/after snapshot comparison (no fabricated diffs)
9. VALIDATE     → tsc --noEmit · ast.parse · syntax checks per language
10. REPORT       → Statistics, changed files, warnings, timeline
11. DOWNLOAD     → Modernized ZIP preserving original project folder structure
```

---

## 🧩 Adding a New Language Adapter

1. Create `backend/app/adapters/<language>/adapter.py`
2. Subclass `MigrationAdapter` from `app.adapters.base`
3. Implement 7 methods: `language`, `provider`, `detect()`, `analyze()`, `get_capabilities()`, `migrate()`, `validate()`
4. Register in `app/core/orchestration/orchestrator.py` → `_ADAPTERS` list
5. Add extension → language mapping to `_EXT_TO_LANG`

That's it. **Zero changes to core orchestration logic.**

---

## 🐛 Known Platform Behaviors

| Behavior | Detail |
|---|---|
| **No Maven/mvn** | Java adapter gracefully generates `rewrite.yml` recipe file — still useful |
| **No Prettier/npx** | JS adapter falls back to built-in `var→let` normalization |
| **No gofmt/shfmt** | Go/Shell adapters report `PARTIALLY_AVAILABLE` capability status |
| **Large files** | Files >512 KB skipped by JS/TS/Generic adapters (minified bundles) |
| **Lockfiles** | `pnpm-lock.yaml`, `yarn.lock`, `package-lock.json` are never modified |
| **pyproject.toml** | Never created in the user's project — Ruff uses an isolated temp config |

---

## 📄 License

MIT © 2026 — Built with ❤️ using FastAPI, React, OpenRewrite, Ruff, and Prettier
