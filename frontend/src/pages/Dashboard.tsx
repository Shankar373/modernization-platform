import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCapabilities } from "../api/client";

const INITIAL_CONNECTORS = [
  { lang: "C# / .NET",   tool: "Roslyn AST Engine",      status: "AVAILABLE", icon: "🔷", color: "#a855f7", desc: "C# 10/11/12 syntax modernization, file-scoped namespaces & .NET 8 TargetFramework upgrade.", target: ".NET 8.0 / C# 12", apiLang: "csharp" },
  { lang: "Java",        tool: "OpenRewrite + Maven",    status: "AVAILABLE", icon: "☕", color: "#f97316", desc: "Enterprise Spring Boot, Jakarta EE migration, and automated recipe transformations.", target: "Java 17/21 & Spring 3+", apiLang: "java" },
  { lang: "Python",      tool: "Ruff AST + Pytest",      status: "AVAILABLE", icon: "🐍", color: "#3b82f6", desc: "AST-level syntax upgrades, type annotations, deprecated API elimination & pytest verification.", target: "Python 3.12+", apiLang: "python" },
  { lang: "TypeScript",  tool: "Vite + AST Parser",      status: "AVAILABLE", icon: "🔷", color: "#3b82f6", desc: "ESNext syntax upgrades, package.json modernization, and type-safe module alignment.", target: "TS 5.4+ / ES2024", apiLang: "typescript" },
  { lang: "HTML",        tool: "BeautifulSoup4 DOM",     status: "AVAILABLE", icon: "🌐", color: "#10b981", desc: "HTML5 semantic modernization, deprecated attribute cleanups, and accessibility enhancements.", target: "HTML5 Standard", apiLang: "html" },
  { lang: "CSS",         tool: "Custom CSS Modernizer",  status: "AVAILABLE", icon: "🎨", color: "#06b6d4", desc: "CSS Variables, Flexbox/Grid migrations, vendor prefix cleanup & modern color spaces.", target: "CSS3 / Modern CSS", apiLang: "css" },
  { lang: "JavaScript",  tool: "jscodeshift Engine",     status: "PARTIAL",   icon: "🟨", color: "#eab308", desc: "CommonJS to ESM transformations, async/await conversions, and package updates.", target: "ESNext / Node 20", apiLang: "javascript" },
  { lang: "Go",          tool: "go fix + AST Codemod",   status: "PARTIAL",   icon: "🐹", color: "#22d3ee", desc: "Go modules modernization, standard library upgrades, and dependency tree auditing.", target: "Go 1.22+", apiLang: "go" },
  { lang: "PHP",         tool: "Rector AST Framework",   status: "PARTIAL",   icon: "🐘", color: "#8b5cf6", desc: "Automated refactoring from PHP 7.x to PHP 8.x modern type-hinted syntax.", target: "PHP 8.3+", apiLang: "php" },
  { lang: "COBOL",       tool: "Inventory Analyzer",     status: "ASSESSMENT_ONLY", icon: "🏛️", color: "#94a3b8", desc: "Legacy mainframe dependency mapping, syntax inventory & structural assessment.", target: "Discovery Only", apiLang: "cobol" },
];

const PIPELINE_STEPS = [
  { num: "01", title: "Universal Discovery", icon: "🔍", desc: "Multi-stack fingerprinting" },
  { num: "02", title: "Dependencies Audit", icon: "📦", desc: "Outdated & security lookup" },
  { num: "03", title: "AI Recommendations", icon: "🤖", desc: "Groq LLM recipe ranking" },
  { num: "04", title: "AST Modernization", icon: "⚙️", desc: "Non-destructive syntax rewrites" },
  { num: "05", title: "Code Optimization", icon: "✨", desc: "Formatting & dead code cleanup" },
  { num: "06", title: "Differential Build", icon: "🧪", desc: "Host compiler zero-regression check" },
];

interface DashStats {
  total: number;
  successful: number;
  partial: number;
  filesModified: number;
  recentRuns: { resultId: string; projectName: string; language: string; status: string; filesModified: number; completedAt: string; }[];
}

function loadStats(): DashStats {
  const runs: any[] = [];
  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    if (!key?.startsWith("run_")) continue;
    try { runs.push(JSON.parse(sessionStorage.getItem(key) || "{}")); } catch { /* skip */ }
  }
  runs.sort((a, b) => new Date(b.completedAt).getTime() - new Date(a.completedAt).getTime());
  return {
    total: runs.length,
    successful: runs.filter(r => r.status === "SUCCESS").length,
    partial: runs.filter(r => r.status === "PARTIALLY_SUCCESSFUL").length,
    filesModified: runs.reduce((s, r) => s + (r.filesModified ?? 0), 0),
    recentRuns: runs.slice(0, 5)
  };
}

const STATUS_BADGE: Record<string, string> = {
  SUCCESS: "badge-available",
  PARTIALLY_SUCCESSFUL: "badge-partial",
  FAILED: "badge-danger",
  ASSESSMENT_ONLY: "badge-assessment",
};

const LANG_ICON: Record<string, string> = {
  python: "🐍", java: "☕", html: "🌐", css: "🎨", javascript: "🟨", typescript: "🔷", csharp: "🔷", go: "🐹", php: "🐘"
};

function useCountUp(target: number, duration = 900) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (target === 0) { setCount(0); return; }
    let start = 0;
    const inc = target / (duration / 16);
    const t = setInterval(() => {
      start += inc;
      if (start >= target) { setCount(target); clearInterval(t); }
      else setCount(Math.floor(start));
    }, 16);
    return () => clearInterval(t);
  }, [target, duration]);
  return count;
}

function StatCard({ icon, label, value, color, subtitle, onClick }: { icon: string; label: string; value: number; color: string; subtitle?: string; onClick?: () => void; }) {
  const count = useCountUp(value);
  return (
    <div
      className="card"
      style={{
        padding: "20px 22px",
        cursor: onClick ? "pointer" : "default",
        transition: "all 0.2s ease",
        display: "flex",
        alignItems: "center",
        gap: 16
      }}
      onClick={onClick}
    >
      <div style={{
        width: 48, height: 48, borderRadius: 12,
        background: `${color}18`,
        border: `1px solid ${color}33`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 22, flexShrink: 0
      }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: 24, fontWeight: 800, color, lineHeight: 1.1 }}>{count}</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text)", marginTop: 2 }}>{label}</div>
        {subtitle && <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 1 }}>{subtitle}</div>}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashStats>(loadStats());
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [hoveredConnector, setHoveredConnector] = useState<string | null>(null);
  const [connectors, setConnectors] = useState(INITIAL_CONNECTORS);
  const [activeMigration, setActiveMigration] = useState<any>(null);

  useEffect(() => {
    const loadActive = () => {
      try {
        const raw = localStorage.getItem('active_migration');
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed && parsed.projectId && parsed.workspacePath) {
            setActiveMigration(parsed);
            return;
          }
        }
      } catch {}
      setActiveMigration(null);
    };
    loadActive();

    const handleUpdate = () => loadActive();
    window.addEventListener('active_migration_updated', handleUpdate);
    window.addEventListener('storage', handleUpdate);

    getCapabilities()
      .then((res) => {
        setBackendUp(true);
        const caps = res.data?.capabilities || [];
        const updated = INITIAL_CONNECTORS.map(conn => {
          const matchingCaps = caps.filter((c: any) => c.language.toLowerCase() === conn.apiLang.toLowerCase());
          if (matchingCaps.length > 0) {
            const hasAvailable = matchingCaps.some((c: any) => c.status === "available" || c.status === "AVAILABLE");
            const hasPartial = matchingCaps.some((c: any) => c.status === "partial" || c.status === "PARTIAL");
            if (hasAvailable) return { ...conn, status: "AVAILABLE" };
            if (hasPartial) return { ...conn, status: "PARTIAL" };
          }
          return conn;
        });
        setConnectors(updated);
      })
      .catch(() => setBackendUp(false));

    setStats(loadStats());
    return () => {
      window.removeEventListener('active_migration_updated', handleUpdate);
      window.removeEventListener('storage', handleUpdate);
    };
  }, []);

  const available = connectors.filter(c => c.status === "AVAILABLE" || c.status === "PARTIAL").length;

  return (
    <div className="animate-fade-up" style={{ maxWidth: 1320, margin: "0 auto", paddingBottom: 48 }}>
      {/* Top Banner Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28, flexWrap: "wrap", gap: 16 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 800, marginBottom: 4 }}>
            <span className="text-gradient">Modernization Dashboard</span>
          </h1>
          <p className="text-muted" style={{ fontSize: 14, margin: 0 }}>
            Enterprise Multi-Stack Architecture Modernization &amp; Migration Platform
          </p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          {backendUp !== null && (
            <div className={`top-bar-status ${backendUp ? "online" : "offline"}`} style={{ padding: "6px 14px", borderRadius: 99, fontSize: 12 }}>
              <span className="status-dot" />{backendUp ? "Engine Online" : "Engine Offline"}
            </div>
          )}
          {activeMigration && (
            <button
              className="btn btn-primary"
              onClick={() => navigate(`/pipeline/${activeMigration.projectId}?wp=${encodeURIComponent(activeMigration.workspacePath)}&stage=${activeMigration.stage}`)}
              style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 18px", fontSize: 13, fontWeight: 700 }}
            >
              ▶ Resume Pipeline (Step {activeMigration.stepNumber}/17)
            </button>
          )}
          <button className="btn btn-systema" onClick={() => navigate("/new")} style={{ padding: "9px 20px", fontSize: 13, fontWeight: 700 }}>
            ＋ New Migration
          </button>
        </div>
      </div>

      {/* Metrics Row: Full width 5-Card Responsive Grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
        gap: 16,
        marginBottom: 28
      }}>
        <StatCard icon="🚀" label="Total Migrations" value={stats.total} color="var(--color-accent-2)" subtitle="All runs recorded" onClick={() => navigate("/history")} />
        <StatCard icon="✅" label="Successful" value={stats.successful} color="var(--color-success)" subtitle="Zero-regression builds" onClick={() => navigate("/history")} />
        <StatCard icon="⚡" label="Partially Converted" value={stats.partial} color="var(--color-warning)" subtitle="With review notices" />
        <StatCard icon="📄" label="Files Modernized" value={stats.filesModified} color="var(--color-accent)" subtitle="AST transformations" />
        <StatCard icon="🔌" label="Engines Ready" value={available} color="#8b5cf6" subtitle={`${connectors.length} total ecosystems`} />
      </div>

      {/* Central Hero Section */}
      {activeMigration ? (
        <div className="card" style={{
          marginBottom: 28,
          padding: "26px 30px",
          background: "linear-gradient(135deg, rgba(29, 127, 138, 0.12), rgba(99, 102, 241, 0.08))",
          border: "1px solid rgba(29, 127, 138, 0.35)",
          borderRadius: 14,
          boxShadow: "0 8px 32px rgba(0,0,0,0.12)"
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18, flexWrap: "wrap", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div style={{
                width: 48, height: 48, borderRadius: 12,
                background: "rgba(29, 127, 138, 0.2)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 24
              }}>
                {activeMigration.stepIcon || "⚡"}
              </div>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981", display: "inline-block", animation: "pulse-dot 2s infinite" }} />
                  <span style={{ fontSize: 12, fontWeight: 700, color: "var(--color-accent)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    Active Migration in Progress
                  </span>
                </div>
                <h2 style={{ fontSize: 20, fontWeight: 700, margin: "4px 0 0 0" }}>
                  📁 {activeMigration.projectName || (activeMigration.workspacePath ? activeMigration.workspacePath.split(/[\\/]/).filter(Boolean).pop()?.replace(/^systema_[a-f0-9]+_/, "") : "") || "Active Project"}
                </h2>
              </div>
            </div>
            <span style={{
              padding: "5px 14px",
              borderRadius: 99,
              fontSize: 12,
              fontWeight: 700,
              background: "rgba(29, 127, 138, 0.15)",
              color: "var(--color-accent)",
              border: "1px solid rgba(29, 127, 138, 0.3)"
            }}>
              Step {activeMigration.stepNumber} of 17
            </span>
          </div>

          <div style={{ marginBottom: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 8 }}>
              <span style={{ fontWeight: 600, color: "var(--color-text)" }}>
                Current Stage: {activeMigration.stepTitle}
              </span>
              <span style={{ color: "var(--color-text-muted)", fontWeight: 600 }}>
                {Math.round((Math.min(activeMigration.stepNumber, 17) / 17) * 100)}% Completed
              </span>
            </div>
            <div className="progress-bar" style={{ height: 8 }}>
              <div className="progress-fill" style={{ width: `${(Math.min(activeMigration.stepNumber, 17) / 17) * 100}%` }} />
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
            <p style={{ fontSize: 13, color: "var(--color-text-muted)", margin: 0 }}>
              All progress, approved recipes, and diffs are safely preserved in memory. Click resume to continue right where you left off.
            </p>
            <div style={{ display: "flex", gap: 12, flexShrink: 0 }}>
              <button className="btn btn-ghost" onClick={() => navigate("/new")} style={{ fontSize: 13 }}>
                ＋ Start New Migration
              </button>
              <button
                className="btn btn-primary"
                onClick={() => navigate(`/pipeline/${activeMigration.projectId}?wp=${encodeURIComponent(activeMigration.workspacePath)}&stage=${activeMigration.stage}`)}
                style={{ padding: "10px 24px", fontSize: 14, fontWeight: 700, display: "flex", alignItems: "center", gap: 8 }}
              >
                ▶ Resume Migration (Step {activeMigration.stepNumber}) ➔
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* Empty / Quick-Start Launchpad Card */
        <div className="card" style={{
          marginBottom: 28,
          padding: "32px 36px",
          background: "linear-gradient(135deg, var(--color-surface) 0%, rgba(29, 127, 138, 0.05) 100%)",
          border: "1px solid var(--color-border)"
        }}>
          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) minmax(0, 1fr)", gap: 32, alignItems: "center" }}>
            <div>
              <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 12px", borderRadius: 99, background: "rgba(29, 127, 138, 0.1)", border: "1px solid rgba(29, 127, 138, 0.25)", marginBottom: 12 }}>
                <span style={{ fontSize: 12 }}>✨</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: "var(--color-accent)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Zero-Regression Architecture</span>
              </div>
              <h2 style={{ fontSize: 24, fontWeight: 800, margin: "0 0 10px 0" }}>
                Ready to Modernize Your Codebase?
              </h2>
              <p className="text-muted" style={{ fontSize: 14, lineHeight: 1.6, marginBottom: 24 }}>
                Upload any enterprise application archive or connect a Git repository. Our engine will fingerprint the architecture, auto-resolve dependencies, apply AST code transformations, and verify differential builds.
              </p>
              <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
                <button className="btn btn-primary" onClick={() => navigate("/new")} style={{ padding: "12px 28px", fontSize: 14, fontWeight: 700 }}>
                  🚀 Start First Migration ➔
                </button>
                <button className="btn btn-ghost" onClick={() => navigate("/dependencies")} style={{ fontSize: 13 }}>
                  📦 Inspect Dependency Catalog
                </button>
              </div>
            </div>
            {/* Quick Highlights */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div style={{ padding: "16px", borderRadius: 10, background: "var(--color-surface-2)", border: "1px solid var(--color-border)" }}>
                <div style={{ fontSize: 20, marginBottom: 6 }}>🛡️</div>
                <div style={{ fontWeight: 700, fontSize: 13 }}>AST Preservation</div>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2 }}>Comments & formatting 100% preserved</div>
              </div>
              <div style={{ padding: "16px", borderRadius: 10, background: "var(--color-surface-2)", border: "1px solid var(--color-border)" }}>
                <div style={{ fontSize: 20, marginBottom: 6 }}>🎯</div>
                <div style={{ fontWeight: 700, fontSize: 13 }}>Git Checkpoints</div>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2 }}>Automatic rollbacks if needed</div>
              </div>
              <div style={{ padding: "16px", borderRadius: 10, background: "var(--color-surface-2)", border: "1px solid var(--color-border)" }}>
                <div style={{ fontSize: 20, marginBottom: 6 }}>🤖</div>
                <div style={{ fontWeight: 700, fontSize: 13 }}>AI Groq Intelligence</div>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2 }}>Tailored recipe recommendations</div>
              </div>
              <div style={{ padding: "16px", borderRadius: 10, background: "var(--color-surface-2)", border: "1px solid var(--color-border)" }}>
                <div style={{ fontSize: 20, marginBottom: 6 }}>🧪</div>
                <div style={{ fontWeight: 700, fontSize: 13 }}>Differential Tests</div>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2 }}>Compiler verification on host</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Recent Migrations (if any) */}
      {stats.recentRuns.length > 0 && (
        <div className="card" style={{ marginBottom: 28, padding: 24 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div>
              <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Recent Migrations</h3>
              <p className="text-muted text-sm" style={{ marginTop: 2 }}>Click any row to view complete modernization report</p>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={() => navigate("/history")}>View All →</button>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {stats.recentRuns.map((run) => (
              <div key={run.resultId} className="flex items-center gap-4"
                style={{ padding: "12px 14px", borderRadius: 8, cursor: "pointer", background: "var(--color-surface-2)", border: "1px solid var(--color-border)", transition: "all 0.15s" }}
                onClick={() => navigate(`/results/${run.resultId}`)}
              >
                <span style={{ fontSize: 22 }}>{LANG_ICON[run.language?.toLowerCase()] || "📦"}</span>
                <div style={{ flex: 1 }}>
                  <span style={{ fontWeight: 600 }}>{run.projectName}</span>
                  <span className="text-muted text-sm" style={{ marginLeft: 10 }}>{run.language} · {run.filesModified} files</span>
                </div>
                <span className={`badge ${STATUS_BADGE[run.status] || "badge-assessment"}`} style={{ fontSize: 10 }}>{run.status?.replace(/_/g, " ")}</span>
                <span className="text-sm text-muted">{run.completedAt ? new Date(run.completedAt).toLocaleTimeString() : ""}</span>
                <span style={{ color: "var(--color-text-muted)" }}>›</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Migration Connectors Grid */}
      <div className="card" style={{ marginBottom: 28, padding: 26 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Supported Transformation Engines</h3>
            <p className="text-muted text-sm" style={{ marginTop: 2, margin: 0 }}>
              {available} of {connectors.length} ecosystems ready for AST refactoring and runtime upgrades
            </p>
          </div>
          <span className="badge badge-available" style={{ fontSize: 12, padding: "4px 12px" }}>
            {available} Active Adapters
          </span>
        </div>

        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: 14
        }}>
          {connectors.map(c => {
            const isAvail = c.status === "AVAILABLE";
            const isPartial = c.status === "PARTIAL";
            return (
              <div
                key={c.lang}
                className="connector-card"
                style={{
                  padding: "16px 18px",
                  borderRadius: 10,
                  background: isAvail ? "var(--color-surface-2)" : "var(--color-surface)",
                  border: isAvail ? "1px solid rgba(16, 185, 129, 0.25)" : "1px solid var(--color-border)",
                  transition: "all 0.2s ease"
                }}
                onMouseEnter={() => setHoveredConnector(c.lang)}
                onMouseLeave={() => setHoveredConnector(null)}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 24 }}>{c.icon}</span>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 14 }}>{c.lang}</div>
                      <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{c.tool}</div>
                    </div>
                  </div>
                  {isAvail && (
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981", animation: "pulse-dot 2s infinite" }} />
                  )}
                </div>

                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 10 }}>
                  <span style={{
                    fontSize: 10,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    padding: "2px 8px",
                    borderRadius: 99,
                    background: isAvail ? "rgba(16, 185, 129, 0.12)" : isPartial ? "rgba(245, 158, 11, 0.12)" : "rgba(255, 255, 255, 0.05)",
                    color: isAvail ? "#10b981" : isPartial ? "#f59e0b" : "var(--color-text-muted)",
                    border: `1px solid ${isAvail ? "rgba(16, 185, 129, 0.25)" : isPartial ? "rgba(245, 158, 11, 0.25)" : "rgba(255, 255, 255, 0.1)"}`
                  }}>
                    {c.status.replace(/_/g, " ")}
                  </span>
                  <span style={{ fontSize: 11, color: "var(--color-accent)", fontFamily: "monospace", fontWeight: 600 }}>
                    {c.target}
                  </span>
                </div>
                {hoveredConnector === c.lang && (
                  <p style={{ fontSize: 11, color: "var(--color-text-muted)", margin: "10px 0 0 0", lineHeight: 1.4, borderTop: "1px solid var(--color-border)", paddingTop: 8 }}>
                    {c.desc}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 6-Phase Pipeline Architecture Flow */}
      <div className="card" style={{ padding: 26 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Automated 17-Step Modernization Flow</h3>
            <p className="text-muted text-sm" style={{ marginTop: 2, margin: 0 }}>
              End-to-end execution lifecycle managed by the AST orchestration engine
            </p>
          </div>
          <span className="badge badge-available">17 Stages</span>
        </div>

        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 12
        }}>
          {PIPELINE_STEPS.map(p => (
            <div
              key={p.num}
              style={{
                padding: "16px 14px",
                borderRadius: 10,
                background: "var(--color-surface-2)",
                border: "1px solid var(--color-border)",
                display: "flex",
                flexDirection: "column",
                gap: 6
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontSize: 20 }}>{p.icon}</span>
                <span style={{ fontSize: 10, fontWeight: 800, color: "var(--color-accent)", padding: "2px 6px", borderRadius: 4, background: "rgba(29, 127, 138, 0.12)" }}>
                  PHASE {p.num}
                </span>
              </div>
              <div style={{ fontWeight: 700, fontSize: 13, marginTop: 4 }}>{p.title}</div>
              <div style={{ fontSize: 11, color: "var(--color-text-muted)", lineHeight: 1.3 }}>{p.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
