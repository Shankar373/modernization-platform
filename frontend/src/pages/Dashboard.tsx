import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCapabilities } from "../api/client";

const INITIAL_CONNECTORS = [
  { lang: "Java",        tool: "OpenRewrite",    status: "AVAILABLE",       icon: "☕", color: "#f97316", desc: "Full transformation engine", apiLang: "java" },
  { lang: "Python",      tool: "Ruff",           status: "AVAILABLE",       icon: "🐍", color: "#3b82f6", desc: "AST-level rewrites", apiLang: "python" },
  { lang: "HTML",        tool: "BeautifulSoup4", status: "AVAILABLE",       icon: "🌐", color: "#10b981", desc: "DOM tree transformations", apiLang: "html" },
  { lang: "CSS",         tool: "Custom Parser",  status: "AVAILABLE",       icon: "🎨", color: "#06b6d4", desc: "Property modernization", apiLang: "css" },
  { lang: "JavaScript",  tool: "jscodeshift",    status: "NOT_AVAILABLE",   icon: "🟨", color: "#eab308", desc: "Codemod framework — planned", apiLang: "javascript" },
  { lang: "TypeScript",  tool: "ts-morph",       status: "NOT_AVAILABLE",   icon: "🔷", color: "#3b82f6", desc: "Type-safe AST — planned", apiLang: "typescript" },
  { lang: "C# / .NET",   tool: "Roslyn",         status: "NOT_AVAILABLE",   icon: "🔷", color: "#a855f7", desc: "Compiler-as-a-service", apiLang: "csharp" },
  { lang: "Go",          tool: "go fix",         status: "NOT_AVAILABLE",   icon: "🐹", color: "#22d3ee", desc: "go fix codemod — planned", apiLang: "go" },
  { lang: "PHP",         tool: "Rector",         status: "NOT_AVAILABLE",   icon: "🐘", color: "#8b5cf6", desc: "Automated refactoring — planned", apiLang: "php" },
  { lang: "COBOL",       tool: "—",              status: "ASSESSMENT_ONLY", icon: "🏛️", color: "#94a3b8", desc: "Assessment & inventory only", apiLang: "cobol" },
];

const FLOW_STEPS = [
  { label: "Upload ZIP / Git URL", icon: "📦" }, { label: "Secure Ingestion", icon: "🔒" },
  { label: "Universal Discovery", icon: "🔍" },  { label: "Tech Fingerprint", icon: "🧬" },
  { label: "AI Assessment", icon: "🤖" },        { label: "Migration Plan", icon: "🗺️" },
  { label: "User Approval", icon: "✅" },         { label: "Execute Migration", icon: "⚙️" },
  { label: "Build & Test", icon: "🧪" },          { label: "Report & Download", icon: "📄" },
];

interface DashStats {
  total: number; successful: number; partial: number; filesModified: number;
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
  return { total: runs.length, successful: runs.filter(r => r.status === "SUCCESS").length,
    partial: runs.filter(r => r.status === "PARTIALLY_SUCCESSFUL").length,
    filesModified: runs.reduce((s, r) => s + (r.filesModified ?? 0), 0), recentRuns: runs.slice(0, 5) };
}

const STATUS_BADGE: Record<string, string> = {
  SUCCESS: "badge-available", PARTIALLY_SUCCESSFUL: "badge-partial", FAILED: "badge-danger", ASSESSMENT_ONLY: "badge-assessment",
};
const LANG_ICON: Record<string, string> = {
  python: "🐍", java: "☕", html: "🌐", css: "🎨", javascript: "🟨", typescript: "🔷", csharp: "🔷",
};

function useCountUp(target: number, duration = 900) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (target === 0) { setCount(0); return; }
    let start = 0;
    const inc = target / (duration / 16);
    const t = setInterval(() => { start += inc; if (start >= target) { setCount(target); clearInterval(t); } else setCount(Math.floor(start)); }, 16);
    return () => clearInterval(t);
  }, [target, duration]);
  return count;
}

function StatCard({ icon, label, value, color, onClick }: { icon: string; label: string; value: number; color: string; onClick?: () => void; }) {
  const count = useCountUp(value);
  return (
    <div className="stat-card" style={{ cursor: onClick ? "pointer" : "default" }} onClick={onClick}>
      <div style={{ fontSize: 22, marginBottom: 6 }}>{icon}</div>
      <div className="stat-value" style={{ color }}>{count}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashStats>(loadStats());
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [hoveredConnector, setHoveredConnector] = useState<string | null>(null);
  const [connectors, setConnectors] = useState(INITIAL_CONNECTORS);

  useEffect(() => {
    getCapabilities()
      .then((res) => {
        setBackendUp(true);
        const caps = res.data?.capabilities || [];
        const updated = INITIAL_CONNECTORS.map(conn => {
          // Find if there's any active capability for this connector language
          const matchingCaps = caps.filter((c: any) => c.language.toLowerCase() === conn.apiLang.toLowerCase());
          if (matchingCaps.length > 0) {
            const hasAvailable = matchingCaps.some((c: any) => c.status === "available" || c.status === "AVAILABLE");
            const hasPartial = matchingCaps.some((c: any) => c.status === "partial" || c.status === "PARTIAL");
            if (hasAvailable) {
              return { ...conn, status: "AVAILABLE" };
            } else if (hasPartial) {
              return { ...conn, status: "PARTIAL" };
            }
          }
          return conn;
        });
        setConnectors(updated);
      })
      .catch(() => setBackendUp(false));
    setStats(loadStats());
  }, []);

  const available = connectors.filter(c => c.status === "AVAILABLE" || c.status === "PARTIAL").length;

  return (
    <div className="animate-fade-up">
      <div className="flex items-center justify-between" style={{ marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: 26, marginBottom: 6 }}><span className="text-gradient">Migration Dashboard</span></h1>
          <p className="text-muted" style={{ fontSize: 14 }}>Enterprise Application Modernization &amp; Migration Platform</p>
        </div>
        <div className="flex gap-3 items-center">
          {backendUp !== null && (
            <div className={`top-bar-status ${backendUp ? "online" : "offline"}`}>
              <span className="status-dot" />{backendUp ? "Backend Online" : "Backend Offline"}
            </div>
          )}
          <button className="btn btn-systema" onClick={() => navigate("/new")}>＋ New Migration</button>
        </div>
      </div>

      <div className="stat-grid" style={{ marginBottom: 32 }}>
        <StatCard icon="🚀" label="Total Migrations"    value={stats.total}         color="var(--color-accent-2)"       onClick={() => navigate("/history")} />
        <StatCard icon="✅" label="Successful"          value={stats.successful}    color="var(--color-success)"        onClick={() => navigate("/history")} />
        <StatCard icon="⚡" label="Partial"             value={stats.partial}       color="var(--color-warning)"        />
        <StatCard icon="📄" label="Files Modernized"    value={stats.filesModified} color="var(--color-accent)"         />
        <StatCard icon="🔌" label="Languages Ready"     value={available}           color="var(--color-systema-purple)" />
      </div>

      {stats.recentRuns.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <div><h3>Recent Migrations</h3><p className="text-muted text-sm" style={{ marginTop: 2 }}>Click any row to view results</p></div>
            <button className="btn btn-ghost btn-sm" onClick={() => navigate("/history")}>View All →</button>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {stats.recentRuns.map((run) => (
              <div key={run.resultId} className="flex items-center gap-4"
                style={{ padding: "12px 14px", borderRadius: 8, cursor: "pointer", transition: "background 0.15s" }}
                onClick={() => navigate(`/results/${run.resultId}`)}
                onMouseEnter={e => (e.currentTarget.style.background = "var(--color-surface-2)")}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
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

      {stats.recentRuns.length === 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="empty-state" style={{ padding: "40px 32px" }}>
            <div className="empty-icon">🚀</div>
            <h3>No migrations yet</h3>
            <p>Upload your first application ZIP or connect a Git repository to get started.</p>
            <button className="btn btn-primary" onClick={() => navigate("/new")}>Start Your First Migration</button>
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div><h3>Migration Connectors</h3><p className="text-muted text-sm" style={{ marginTop: 2 }}>{available} of {connectors.length} adapters · hover for details</p></div>
          <span className="badge badge-available">{available} Active</span>
        </div>
        <div className="card-grid">
          {connectors.map(c => {
            const cls = c.status === "AVAILABLE" ? "available" : c.status === "PARTIAL" ? "available" : c.status === "ASSESSMENT_ONLY" ? "assessment" : "unavailable";
            const badgeCls = c.status === "AVAILABLE" ? "badge-available" : c.status === "PARTIAL" ? "badge-partial" : c.status === "ASSESSMENT_ONLY" ? "badge-assessment" : "badge-unavailable";
            return (
              <div key={c.lang} className={`connector-card ${cls}`}
                onMouseEnter={() => setHoveredConnector(c.lang)} onMouseLeave={() => setHoveredConnector(null)}>
                <div className="flex items-center gap-2" style={{ marginBottom: 10 }}>
                  <span style={{ fontSize: 22 }}>{c.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>{c.lang}</div>
                    <div className="text-muted text-xs">{c.tool}</div>
                  </div>
                  {(c.status === "AVAILABLE" || c.status === "PARTIAL") && <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981", animation: "pulse-dot 2s infinite" }} />}
                </div>
                <span className={`badge ${badgeCls}`} style={{ fontSize: 10 }}>{c.status.replace(/_/g, " ")}</span>
                {hoveredConnector === c.lang && <p className="text-muted text-xs" style={{ marginTop: 8, lineHeight: 1.5 }}>{c.desc}</p>}
              </div>
            );
          })}
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h3>Platform Flow</h3><span className="badge badge-info">{FLOW_STEPS.length} Stages</span></div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
          {FLOW_STEPS.map((step, i, arr) => (
            <span key={step.label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{
                padding: "5px 12px", borderRadius: 8, display: "flex", alignItems: "center", gap: 6,
                background: "var(--color-surface-2)", border: "1px solid var(--color-border)",
                fontSize: 12, color: "var(--color-text-muted)", transition: "all 0.15s", cursor: "default",
              }}
                onMouseEnter={e => { const el = e.currentTarget as HTMLElement; el.style.background="rgba(29,127,138,0.08)"; el.style.color="var(--color-accent)"; el.style.borderColor="rgba(29,127,138,0.2)"; }}
                onMouseLeave={e => { const el = e.currentTarget as HTMLElement; el.style.background="var(--color-surface-2)"; el.style.color="var(--color-text-muted)"; el.style.borderColor="var(--color-border)"; }}
              >
                <span>{step.icon}</span><span>{step.label}</span>
              </span>
              {i < arr.length - 1 && <span style={{ color: "var(--color-accent)", fontWeight: 700, fontSize: 14, opacity: 0.6 }}>→</span>}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
