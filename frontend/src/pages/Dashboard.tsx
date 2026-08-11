import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCapabilities } from '../api/client';

const CONNECTORS = [
  { lang: 'Java',       tool: 'OpenRewrite',    status: 'AVAILABLE',        icon: '☕' },
  { lang: 'Python',     tool: 'Ruff',           status: 'AVAILABLE',        icon: '🐍' },
  { lang: 'HTML',       tool: 'BeautifulSoup4', status: 'AVAILABLE',        icon: '🌐' },
  { lang: 'CSS',        tool: 'Custom Parser',  status: 'AVAILABLE',        icon: '🎨' },
  { lang: 'JavaScript', tool: 'jscodeshift',    status: 'NOT_AVAILABLE',    icon: '🟨' },
  { lang: 'TypeScript', tool: 'ts-morph',       status: 'NOT_AVAILABLE',    icon: '🔷' },
  { lang: 'C# / .NET',  tool: 'Roslyn',         status: 'NOT_AVAILABLE',    icon: '#️⃣' },
  { lang: 'Go',         tool: 'go fix',         status: 'NOT_AVAILABLE',    icon: '🐹' },
  { lang: 'PHP',        tool: 'Rector',         status: 'NOT_AVAILABLE',    icon: '🐘' },
  { lang: 'COBOL',      tool: '—',              status: 'ASSESSMENT_ONLY',  icon: '🏛️' },
];

const FLOW_STEPS = [
  'Upload ZIP / Git URL', 'Secure Ingestion', 'Universal Discovery',
  'Technology Fingerprint', 'Capability Registry', 'Migration Assessment',
  'Target Recommendation', 'Migration Plan', 'User Approval',
  'Dry Run Preview', 'Execute Migration', 'Build & Test Validation',
  'Before/After Diff', 'Report', 'Download',
];

interface DashStats {
  total: number;
  successful: number;
  partial: number;
  filesModified: number;
  recentRuns: { resultId: string; projectName: string; language: string; status: string; filesModified: number; completedAt: string }[];
}

function loadStats(): DashStats {
  const runs: any[] = [];
  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    if (!key?.startsWith('run_')) continue;
    try { runs.push(JSON.parse(sessionStorage.getItem(key) || '{}')); } catch { /* skip */ }
  }
  runs.sort((a, b) => new Date(b.completedAt).getTime() - new Date(a.completedAt).getTime());
  return {
    total:         runs.length,
    successful:    runs.filter(r => r.status === 'SUCCESS').length,
    partial:       runs.filter(r => r.status === 'PARTIALLY_SUCCESSFUL').length,
    filesModified: runs.reduce((s, r) => s + (r.filesModified ?? 0), 0),
    recentRuns:    runs.slice(0, 5),
  };
}

const STATUS_BADGE: Record<string, string> = {
  SUCCESS: 'badge-available', PARTIALLY_SUCCESSFUL: 'badge-partial',
  FAILED: 'badge-danger', ASSESSMENT_ONLY: 'badge-assessment',
};
const LANG_ICON: Record<string, string> = {
  python: '🐍', java: '☕', html: '🌐', css: '🎨',
  javascript: '🟨', typescript: '🔷',
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashStats>(loadStats());
  const [backendUp, setBackendUp] = useState<boolean | null>(null);

  // Ping backend health
  useEffect(() => {
    getCapabilities()
      .then(() => setBackendUp(true))
      .catch(() => setBackendUp(false));
    // Refresh stats from sessionStorage on mount
    setStats(loadStats());
  }, []);

  const available = CONNECTORS.filter(c => c.status === 'AVAILABLE').length;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between" style={{ marginBottom: 32 }}>
        <div>
          <h1>Migration Dashboard</h1>
          <p className="text-muted" style={{ marginTop: 8 }}>
            Enterprise Application Modernization &amp; Migration Platform
          </p>
        </div>
        <div className="flex gap-3 items-center">
          {backendUp !== null && (
            <span
              className={`badge ${backendUp ? 'badge-available' : 'badge-danger'}`}
              style={{ fontSize: 11 }}
            >
              {backendUp ? '● Backend Online' : '● Backend Offline'}
            </span>
          )}
          <button className="btn btn-primary" onClick={() => navigate('/new')}>
            ＋ New Migration
          </button>
        </div>
      </div>

      {/* Live Stats */}
      <div className="stat-grid" style={{ marginBottom: 32 }}>
        {[
          { label: 'Total Migrations',    value: stats.total },
          { label: 'Successful',          value: stats.successful },
          { label: 'Partial',             value: stats.partial },
          { label: 'Files Modernized',    value: stats.filesModified },
          { label: 'Languages Supported', value: available },
        ].map(s => (
          <div className="stat-card" key={s.label}>
            <div className="stat-value">{s.value}</div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Recent runs */}
      {stats.recentRuns.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <h3>Recent Migrations</h3>
            <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => navigate('/history')}>
              View All →
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {stats.recentRuns.map(run => (
              <div
                key={run.resultId}
                className="flex items-center gap-4"
                style={{
                  padding: '12px 0', borderBottom: '1px solid var(--color-border)',
                  cursor: 'pointer',
                }}
                onClick={() => navigate(`/results/${run.resultId}`)}
              >
                <span style={{ fontSize: 20 }}>{LANG_ICON[run.language?.toLowerCase()] || '📦'}</span>
                <div style={{ flex: 1 }}>
                  <span style={{ fontWeight: 600 }}>{run.projectName}</span>
                  <span className="text-muted text-sm" style={{ marginLeft: 10 }}>
                    {run.language} · {run.filesModified} files changed
                  </span>
                </div>
                <span className={`badge ${STATUS_BADGE[run.status] || 'badge-assessment'}`} style={{ fontSize: 11 }}>
                  {run.status?.replace('_', ' ')}
                </span>
                <span className="text-sm text-muted">
                  {run.completedAt ? new Date(run.completedAt).toLocaleTimeString() : ''}
                </span>
                <span style={{ color: 'var(--color-text-muted)' }}>›</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Connectors grid */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header"><h3>Migration Connectors</h3></div>
        <div className="card-grid">
          {CONNECTORS.map(c => (
            <div key={c.lang} className="card" style={{ padding: 16 }}>
              <div className="flex items-center gap-2" style={{ marginBottom: 10 }}>
                <span style={{ fontSize: 20 }}>{c.icon}</span>
                <span style={{ fontWeight: 600 }}>{c.lang}</span>
                <span className="text-muted" style={{ marginLeft: 'auto', fontSize: 11 }}>{c.tool}</span>
              </div>
              <span className={`badge badge-${c.status === 'AVAILABLE' ? 'available' : c.status === 'ASSESSMENT_ONLY' ? 'assessment' : 'unavailable'}`}>
                {c.status.replace('_', ' ')}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Platform flow */}
      <div className="card">
        <div className="card-header"><h3>Platform Flow</h3></div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          {FLOW_STEPS.map((step, i, arr) => (
            <span key={step} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{
                padding: '4px 10px', borderRadius: 6,
                background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
                fontSize: 12, color: 'var(--color-text-muted)',
              }}>{step}</span>
              {i < arr.length - 1 && <span style={{ color: 'var(--color-accent)', fontWeight: 700 }}>→</span>}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
