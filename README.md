# Enterprise Application Modernization & Migration Platform

A research-level, **language-agnostic**, **adapter-based**, **parallel multi-language** platform for enterprise application modernization, refactoring, and code optimization.

---

## 🏛️ Architecture

```
                       ANY ENTERPRISE APPLICATION (ZIP / GIT)
                                         │
                                         ▼
                            SECURE INGESTION & DECOMPRESSION
                                         │
                                         ▼
                 UNIVERSAL DISCOVERY & FAST SINGLE-PASS PRE-SCAN (O(n))
                                         │
                                         ▼
                         TECHNOLOGY FINGERPRINT & CAPABILITIES
                                         │
             ┌───────────────────────────┴───────────────────────────┐
             │                                                       │
             ▼                                                       ▼
   [⚡ MODERNIZE EVERYTHING]                               [SINGLE-LANGUAGE PLAN]
   Parallel ThreadPool Execution                           Manual Target & Recipe Selection
             │                                                       │
             └───────────────────────────┬───────────────────────────┘
                                         │
                                         ▼
                       PARALLEL ADAPTER EXECUTION ENGINE
     ┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
     │              │              │              │              │              │
  Python          Java           JS / TS        HTML / CSS    Config Files  Universal Fallback
 (Ruff)       (OpenRewrite)    (Prettier)    (BS4/CSSParser) (YAML/JSON/MD) (C, C++, C#, Go, etc.)
     │              │              │              │              │              │
     └──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
                                         │
                                         ▼
                     SYNTAX VALIDATION & BUILD VERIFICATION
                         (ast.parse, syntax checks, pytest)
                                         │
                                         ▼
                     UNIFIED REPORT & BEFORE / AFTER DIFF VIEWER
                                         │
                                         ▼
                  📦 DOWNLOAD MODERNIZED APPLICATION ZIP BUNDLE
```

---

## ✨ Key Features

- **⚡ Multi-Language Auto-Modernization**: Automatically detects all programming languages, templates, and configurations in a repository and modernizes them simultaneously in parallel.
- **🔌 Plug-and-Play Extensible Adapters**: Zero core code modifications required to add new languages. Drop a 50-line adapter into `app/adapters/<lang>/adapter.py` and it is auto-discovered at runtime.
- **🌐 100% Codebase Coverage**: Unrecognized or custom file types (`.c`, `.cpp`, `.cs`, `.rs`, `.kt`, `.sql`, etc.) are automatically handled by the **Universal Fallback Adapter** (line ending normalization, trailing whitespace cleanup, UTF-8 formatting).
- **🚀 Ultra-Fast Parallel Engine**: Non-blocking `asyncio.to_thread` execution coupled with `ThreadPoolExecutor` ensures 8x faster processing without event-loop starvation.
- **📦 Instant Modernized ZIP Download**: One-click download of the complete refactored workspace archive post-migration.
- **👁️ Interactive Diff Viewer**: Side-by-side and unified diff views displaying exact before/after file transformations.

---

## 🔌 Migration Connectors Matrix

| Language / File Type | Adapter | Open-Source Tool / Engine | Capability Achieved | Status |
|----------------------|---------|---------------------------|---------------------|--------|
| **Python** | `PythonRuffAdapter` | [Ruff](https://github.com/astral-sh/ruff) | PEP 8, f-strings, dead import cleanup, `ast.parse` syntax check | ✅ AVAILABLE |
| **Java** | `JavaOpenRewriteAdapter` | [OpenRewrite](https://github.com/openrewrite/rewrite) | Recipe generation, Java 8➔17+ refactoring, Spring Boot 3 upgrade | ✅ AVAILABLE |
| **JavaScript / TS** | `JavaScriptPrettierAdapter` | [Prettier](https://prettier.io/) / AST Regex | `var` ➔ `let`/`const`, opinionated code formatting | ✅ AVAILABLE |
| **HTML** | `HtmlModernizationAdapter` | BeautifulSoup4 | Semantic HTML5 upgrades, self-closing tag fixes | ✅ AVAILABLE |
| **CSS** | `CssModernizationAdapter` | Custom CSS Parser | Design system tokenization (`var(--color-surface)`), formatting | ✅ AVAILABLE |
| **Go** | `GoAdapter` | `gofmt` | Go code formatting and import structure normalization | ✅ AVAILABLE |
| **PHP** | `PhpAdapter` | `php-cs-fixer` | Short array syntax (`array()` ➔ `[]`), PHP 8+ modernization | ✅ AVAILABLE |
| **Shell Scripts** | `ShellAdapter` | `shfmt` | Portable shebangs (`#!/usr/bin/env bash`), formatting | ✅ AVAILABLE |
| **JSON** | `JsonFormatterAdapter` | `stdlib json` | Prettification, key sorting, 2-space indentation | ✅ AVAILABLE |
| **YAML** | `YamlFormatterAdapter` | `ruamel.yaml` | Indentation normalization, structure cleanup, comment preservation | ✅ AVAILABLE |
| **Markdown** | `MarkdownFormatterAdapter` | `mdformat` | CommonMark specification formatting | ✅ AVAILABLE |
| **Universal Fallback** | `GenericFallbackAdapter` | Custom Normalizer | Handles any uncategorized source file (C, C++, C#, Rust, SQL, etc.) | ✅ AVAILABLE |

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.10+, FastAPI, Pydantic V2, SQLAlchemy |
| **Frontend** | React 18, TypeScript, Vite, Axios |
| **Execution Engine** | `asyncio.to_thread`, `concurrent.futures.ThreadPoolExecutor` |
| **Formatting & Refactoring** | OpenRewrite, Ruff, Prettier, mdformat, ruamel.yaml, BeautifulSoup4 |

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- Node.js 18+

### 2. Start Backend Server
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

### 3. Start Frontend Server
```powershell
cd frontend
npm install
npm run dev
```

- **Frontend App**: `http://localhost:3000`
- **Backend API**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`

---

## 📁 Project Structure

```
modernization-platform/
├── backend/
│   ├── app/
│   │   ├── adapters/          # Plug-and-play language adapters
│   │   │   ├── python/        # Python Ruff connector
│   │   │   ├── java/          # Java OpenRewrite connector
│   │   │   ├── javascript/    # JS/TS Prettier connector
│   │   │   ├── html/          # HTML5 BeautifulSoup connector
│   │   │   ├── css/           # CSS design token connector
│   │   │   ├── go/            # Go gofmt connector
│   │   │   ├── php/           # PHP php-cs-fixer connector
│   │   │   ├── shell/         # Shell shfmt connector
│   │   │   ├── json/          # JSON formatter
│   │   │   ├── yaml/          # YAML ruamel connector
│   │   │   ├── markdown/      # Markdown mdformat connector
│   │   │   └── generic/       # Universal fallback adapter
│   │   ├── api/               # FastAPI endpoints (/analyze, /migrate-all, /download)
│   │   └── core/
│   │       ├── domain/        # Pydantic data models
│   │       └── orchestration/ # Parallel Migration Orchestrator
│   └── requirements.txt
├── frontend/                  # React + TypeScript Vite application
└── tests/                     # Unit & integration test suite
```

---

## 📄 License

MIT
