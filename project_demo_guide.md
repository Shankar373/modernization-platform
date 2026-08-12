# 🚀 Enterprise Application Modernization Platform — Project Demo Guide

This document provides a comprehensive walkthrough for demonstrating the Modernization Platform, its underlying technology stack, architectural details, and key features.

---

## 📺 Demo walkthrough: How It Works

This platform modernizes repositories using a **two-step safety gate**: **Ingestion & Scan** ➔ **Dry Run & Preview** ➔ **Approval & Execution**.

### Scenario A: Full-Application Modernization (Multi-Language Pipeline)
Use this flow to demonstrate parallel multi-language modernization (e.g., Python + Java + JS + Config files all at once).

1. **Step 1: Upload / Ingest**
   * Open the web app at `http://localhost:5173`.
   * Click **New Migration**.
   * Choose **Upload ZIP** or paste a **Git Repository URL** (e.g., `https://github.com/joakim666/spring-boot-spring-loaded-java8-example`).
   * Enter a project name and click **Ingest**.

2. **Step 2: Technology Fingerprint Review**
   * The platform performs an $O(n)$ single-pass filesystem walk.
   * View the **Technology Fingerprint** card: it displays the detected languages (Java, Markdown, YAML, etc.), version numbers, and confidence metrics.
   * Review the **Available Modernization Adapters** list to see which adapters are activated.

3. **Step 3: Preview Changes (Dry Run)**
   * Select a **Migration Profile** (Conservative, Standard, or Aggressive).
   * Click **🔬 Preview Changes (Dry Run) →**.
   * The platform executes a simulated run across all matching adapters in parallel.
   * View the summary banner displaying the total number of files that *would* change, accompanied by a detailed per-language breakdown.

4. **Step 4: Accept & Execute**
   * Review the list of proposed changes.
   * Click **✅ Accept & Execute Modernization →** to confirm.
   * The execution engine runs all refactoring scripts in parallel.

5. **Step 5: View Results & Diff Viewer**
   * Once complete, you are redirected to the **Results** page.
   * Explore the interactive **Code Changes** section.
   * Select files to view line-by-line diffs in either **Unified Diff** or **Side by Side** modes.
   * Click **Download Modernized ZIP** to retrieve the refactored project with its original folder structure intact.

---

## 🛠️ Technology Stack & Optimization Engines

The platform integrates custom-built AST transformers with industry-standard, production-grade optimization tools.

### 1. Ingestion, Orchestration & Backend
* **FastAPI (0.111.0)**: High-performance, fully typed Python ASGI framework.
* **Uvicorn (0.30.1)**: Lightning-fast ASGI web server implementation.
* **ThreadPoolExecutor & asyncio.to_thread**: Offloads heavy CPU-bound refactoring tasks to dedicated threads, avoiding event-loop starvation and socket resets on Windows.
* **GitPython & chardet**: Secure repository cloning and automated character encoding normalization.

### 2. Frontend User Interface
* **React 19 & TypeScript**: Responsive UI design with robust static typing.
* **Vite 8**: Next-generation, lightning-fast frontend tooling and hot-module replacement.
* **Vanilla CSS Layout**: Responsive dark-themed interface built on custom CSS properties and glassmorphism.

### 3. Language & File Optimization Engines

| Technology / File Type | Adapter Class | Core Optimization Engine | Purpose & Capability |
| :--- | :--- | :--- | :--- |
| **Python** | `PythonRuffAdapter` | [Ruff](https://github.com/astral-sh/ruff) | PEP 8 compliance, dead import cleaning, syntax checking, unused variable removal |
| **Java** | `JavaOpenRewriteAdapter` | [OpenRewrite](https://github.com/openrewrite/rewrite) + Maven | Version upgrades (Java 8➔17➔21), Spring Boot 3 Jakarta EE recipe migrations |
| **TypeScript** | `TypeScriptAdapter` | AST regex + Prettier | Modernizes `var` ➔ `let/const`, converts CommonJS `require()` ➔ ES Modules `import`, validates syntax via `tsc --noEmit` |
| **JavaScript** | `JavaScriptPrettierAdapter` | [Prettier](https://prettier.io/) | Auto-formats JS/JSX structures, enforces layout rules |
| **HTML** | `HtmlModernizationAdapter` | BeautifulSoup4 | Normalizes DOCTYPEs, semantic HTML5 tags, self-closing tags |
| **CSS / SCSS** | `CssModernizationAdapter` | Custom CSS Parser | Extracts design tokens into CSS variables, vendor-prefix cleaning |
| **Go** | `GoAdapter` | `gofmt` | Enforces standard Go formatting and import ordering |
| **PHP** | `PhpAdapter` | `php-cs-fixer` | Upgrades array syntax (`array()` ➔ `[]`), PSR-12 coding standard |
| **Shell Scripts** | `ShellAdapter` | `shfmt` | Normalizes shebangs and command indentations |
| **YAML / YML** | `YamlFormatterAdapter` | `ruamel.yaml` | Indentation normalization while preserving comments |
| **JSON** | `JsonFormatterAdapter` | `stdlib json` | Sorts keys, formats spacing with 2-space indentation |
| **Markdown** | `MarkdownFormatterAdapter` | `mdformat` | Formats Markdown according to CommonMark specifications |

---

## 💎 Key Platform Features Highlight

### ⚡ Parallel Adapter Engine
Using `concurrent.futures`, multiple adapters run simultaneously. While Maven runs recipe transformations on Java source files, Ruff cleans up Python scripts, and Prettier formats TypeScript files in parallel, yielding up to **8x faster processing speeds**.

### 🛡️ Windows-Native Compatibility
* Runs Maven wrapper commands natively on Windows using `.mvnw.cmd` with `shell=True` subprocesses.
* Intentionally skips Unix shell scripts (`mvnw` without extension) on Windows to prevent execution errors (`[WinError 2]`).
* Gracefully falls back to generating the `rewrite.yml` recipe and displays helpful, non-blocking instruction warnings if execution environments are missing.

### 🔒 Lockfile and Configuration Safety
* Automatically excludes complex package manager lockfiles (`pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`) from formatting and styling engines to avoid file corruption.
* Generates temporary, isolated configuration directories for linting tools (e.g., Ruff). The platform **never injects boilerplate configurations** (such as `pyproject.toml`) into the user's workspace directory.
