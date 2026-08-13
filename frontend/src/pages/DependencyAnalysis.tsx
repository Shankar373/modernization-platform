import { useRef, useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { runDependencyAnalysis, clearDependencyCache } from '../api/client';
import type {
  Dependency,
  DependencyAnalysisResult,
  DependencyStatus,
} from '../types';

// ── Constants ──────────────────────────────────────────────────────────────────

const ECO_ICONS: Record<string, string> = {
  python: '🐍', node: '📦', java: '☕', dotnet: '🔷', unknown: '❓',
};

const STATUS_CONFIG: Record<DependencyStatus, { label: string; color: string; bg: string; icon: string }> = {
  UP_TO_DATE:        { label: 'Up to date',         color: '#34d399', bg: 'rgba(16,185,129,0.08)',  icon: '✓' },
  UPDATE_AVAILABLE:  { label: 'Update available',   color: '#f59e0b', bg: 'rgba(245,158,11,0.10)',  icon: '↑' },
  CONSTRAINT_BLOCKED:{ label: 'Constraint blocked', color: '#8b5cf6', bg: 'rgba(139,92,246,0.10)',  icon: '⛔' },
  LOOKUP_FAILED:     { label: 'Lookup failed',      color: '#6b7280', bg: 'rgba(107,114,128,0.10)', icon: '?' },
  INVALID_VERSION:   { label: 'Invalid version',    color: '#ef4444', bg: 'rgba(239,68,68,0.10)',   icon: '!' },
};

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: DependencyStatus }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.LOOKUP_FAILED;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '2px 10px', borderRadius: 999, fontSize: 11, fontWeight: 600,
      color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.color}44`,
    }}>
      {cfg.icon} {cfg.label}
    </span>
  );
}

function DepRow({ dep }: { dep: Dependency }) {
  const eco = dep.ecosystem;
  return (
    <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
      <td style={{ padding: '10px 12px', fontWeight: 600 }}>
        <span style={{ marginRight: 6 }}>{ECO_ICONS[eco] || '📦'}</span>
        {dep.name}{dep.extras || ''}
      </td>
      <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: 13, color: 'var(--color-text-muted)' }}>
        {dep.current_version ?? <em style={{ color: 'var(--color-text-muted)', fontStyle: 'italic' }}>unconstrained</em>}
        {dep.version_constraint && dep.current_version === null && (
          <span style={{ marginLeft: 6, color: '#8b5cf6', fontSize: 11 }}>({dep.version_constraint})</span>
        )}
      </td>
      <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: 13 }}>
        {dep.latest_stable_version
          ? <span style={{ color: dep.status === 'UPDATE_AVAILABLE' ? '#34d399' : 'inherit' }}>{dep.latest_stable_version}</span>
          : <span style={{ color: 'var(--color-text-muted)', fontSize: 11 }}>—</span>
        }
      </td>
      <td style={{ padding: '10px 12px' }}>
        <StatusBadge status={dep.status} />
      </td>
      <td style={{ padding: '10px 12px', fontSize: 11, color: 'var(--color-text-muted)', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {dep.source_file}
      </td>
    </tr>
  );
}

function SummaryCard({ label, count, color, icon }: { label: string; count: number; color: string; icon: string }) {
  return (
    <div style={{
      flex: '1 1 140px', padding: '16px 20px', borderRadius: 12,
      background: `${color}12`, border: `1px solid ${color}33`,
      textAlign: 'center',
    }}>
      <div style={{ fontSize: 28, fontWeight: 800, color }}>{count}</div>
      <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>{icon} {label}</div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function DependencyAnalysisPage() {
  const [sp] = useSearchParams();
  const [workspacePath, setWorkspacePath] = useState('');
  const [projectId, setProjectId] = useState('');

  // Extract from query params or resolve fallback from session storage
  useEffect(() => {
    let wp = sp.get('wp') || '';
    let projId = sp.get('project') || '';

    if (!wp) {
      const keys = [];
      for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i);
        if (key?.startsWith('project_')) {
          keys.push(key);
        }
      }
      if (keys.length > 0) {
        keys.sort();
        const latestKey = keys[keys.length - 1];
        try {
          const proj = JSON.parse(sessionStorage.getItem(latestKey) || '{}');
          if (proj.workspace_path) {
            wp = proj.workspace_path;
            projId = proj.project_id || '';
          }
        } catch (e) {
          // ignore
        }
      }
    }

    setWorkspacePath(wp);
    setProjectId(projId);
  }, [sp]);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DependencyAnalysisResult | null>(null);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<DependencyStatus | 'ALL'>('ALL');
  const hasRun = useRef(false);

  // Auto-run on first mount or when workspacePath is resolved
  useEffect(() => {
    if (workspacePath && !hasRun.current && !loading && !result) {
      hasRun.current = true;
      handleRun();
    }
  }, [workspacePath]);

  async function handleRun(forceRefresh = false) {
    if (!workspacePath) return;
    setLoading(true); setError(''); setResult(null);
    try {
      const res = await runDependencyAnalysis(workspacePath, projectId, forceRefresh);
      setResult(res.data as DependencyAnalysisResult);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Dependency analysis failed.');
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    if (workspacePath) await clearDependencyCache(workspacePath);
    hasRun.current = false;
    // Trigger run again
    if (workspacePath) {
      setLoading(true); setError(''); setResult(null);
      try {
        const res = await runDependencyAnalysis(workspacePath, projectId, true);
        setResult(res.data as DependencyAnalysisResult);
      } catch (e: any) {
        setError(e?.response?.data?.detail || 'Dependency analysis failed.');
      } finally {
        setLoading(false);
      }
    }
  }

  const filteredDeps = result?.dependencies?.filter(
    d => filter === 'ALL' || d.status === filter
  ) ?? [];

  return (
    <div style={{ maxWidth: 1100 }}>
      {/* Header */}
      <div className="flex items-center justify-between" style={{ marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ marginBottom: 4 }}>🔍 Dependency Analysis</h1>
          <p className="text-muted" style={{ fontSize: 13 }}>
            Dynamically discovers latest stable versions from PyPI · npm · Maven Central
          </p>
        </div>
        <div className="flex gap-3">
          {result && (
            <button className="btn btn-ghost" onClick={handleRefresh} disabled={loading} style={{ fontSize: 13 }}>
              🔄 Refresh Versions
            </button>
          )}
          {!workspacePath && (
            <span className="text-muted text-sm">No workspace path provided</span>
          )}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{
          background: 'linear-gradient(135deg,rgba(99,102,241,0.1),rgba(59,130,246,0.1))',
          border: '1px solid rgba(99,102,241,0.3)', borderRadius: 14,
          padding: '32px 28px', marginBottom: 24,
        }}>
          <div className="flex items-center gap-3" style={{ marginBottom: 16 }}>
            <span className="spinner" style={{ width: 24, height: 24 }} />
            <span style={{ fontWeight: 600, fontSize: '1.05rem' }}>Analyzing dependencies...</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13, color: 'var(--color-text-muted)' }}>
            {['Detecting dependency files', 'Parsing dependency declarations', 'Querying package registries (PyPI · npm · Maven Central)', 'Comparing versions & checking constraints', 'Applying safe updates'].map((step, i) => (
              <div key={step} className="flex items-center gap-2">
                <span className="spinner" style={{ width: 12, height: 12, opacity: 0.6 }} />
                {step}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{ padding: '14px 18px', borderRadius: 10, marginBottom: 24, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#fca5a5' }}>
          ❌ {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Summary cards */}
          <div className="flex gap-3" style={{ marginBottom: 24, flexWrap: 'wrap' }}>
            <SummaryCard label="Total"      count={result.dependencies.length}         color="#6366f1" icon="📦" />
            <SummaryCard label="Up to date" count={result.up_to_date.length}           color="#34d399" icon="✓" />
            <SummaryCard label="Outdated"   count={result.outdated.length}             color="#f59e0b" icon="↑" />
            <SummaryCard label="Blocked"    count={result.constraint_blocked.length}   color="#8b5cf6" icon="⛔" />
            <SummaryCard label="Failed"     count={result.lookup_failed.length}        color="#6b7280" icon="?" />
            <SummaryCard label="Updated"    count={result.changed_files.length}        color="#3b82f6" icon="💾" />
          </div>

          {/* Dependency files detected */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
              <h3>Dependency Files ({result.dependency_files.length})</h3>
              {result.cached && <span className="badge badge-assessment">Cached</span>}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {result.dependency_files.map(f => (
                <span key={f.path} style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  padding: '4px 12px', borderRadius: 8, fontSize: 12, fontFamily: 'monospace',
                  background: f.is_lockfile ? 'rgba(107,114,128,0.1)' : 'rgba(99,102,241,0.1)',
                  border: `1px solid ${f.is_lockfile ? 'rgba(107,114,128,0.3)' : 'rgba(99,102,241,0.3)'}`,
                  color: f.is_lockfile ? 'var(--color-text-muted)' : 'var(--color-accent-2)',
                }}>
                  {ECO_ICONS[f.ecosystem] || '📦'} {f.path}
                </span>
              ))}
            </div>
          </div>

          {/* Detailed table */}
          <div className="card">
            <div className="card-header flex justify-between items-center" style={{ flexWrap: 'wrap', gap: 12 }}>
              <h3>Detailed Diagnostics</h3>
              <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
                {(['ALL', 'UP_TO_DATE', 'UPDATE_AVAILABLE', 'CONSTRAINT_BLOCKED', 'LOOKUP_FAILED'] as const).map(f => (
                  <button
                    key={f}
                    className={`btn ${filter === f ? 'btn-primary' : 'btn-ghost'} btn-sm`}
                    style={{ fontSize: 11, padding: '4px 10px' }}
                    onClick={() => setFilter(f)}
                  >
                    {f.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--color-border)', color: 'var(--color-text-muted)', fontSize: 12, fontWeight: 700 }}>
                  <th style={{ padding: '10px 12px' }}>NAME</th>
                  <th style={{ padding: '10px 12px' }}>CURRENT</th>
                  <th style={{ padding: '10px 12px' }}>LATEST STABLE</th>
                  <th style={{ padding: '10px 12px' }}>STATUS</th>
                  <th style={{ padding: '10px 12px' }}>SOURCE FILE</th>
                </tr>
              </thead>
              <tbody>
                {filteredDeps.map(d => (
                  <DepRow key={`${d.name}-${d.source_file}`} dep={d} />
                ))}
                {filteredDeps.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--color-text-muted)' }}>
                      No dependencies found matching this filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
