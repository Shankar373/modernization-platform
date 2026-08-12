import { useRef, useState } from 'react';
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
  const workspacePath = sp.get('wp') || '';
  const projectId = sp.get('project') || '';

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DependencyAnalysisResult | null>(null);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<DependencyStatus | 'ALL'>('ALL');
  const hasRun = useRef(false);

  // Auto-run on first mount if wp is provided
  if (workspacePath && !hasRun.current && !loading && !result) {
    hasRun.current = true;
    setTimeout(() => handleRun(), 0);
  }

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
    handleRun(true);
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
                  {f.is_lockfile && <span style={{ fontSize: 10, opacity: 0.7 }}> 🔒 lockfile</span>}
                </span>
              ))}
              {result.dependency_files.length === 0 && (
                <p className="text-muted">No dependency files found in workspace.</p>
              )}
            </div>
          </div>

          {/* Updated files */}
          {result.changed_files.length > 0 && (
            <div style={{
              background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.3)',
              borderRadius: 12, padding: '16px 20px', marginBottom: 20,
            }}>
              <p style={{ fontWeight: 700, marginBottom: 8 }}>
                💾 {result.changed_files.length} file(s) updated on disk
              </p>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {result.changed_files.map(f => (
                  <span key={f} style={{
                    padding: '3px 10px', borderRadius: 6, fontSize: 12, fontFamily: 'monospace',
                    background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.3)',
                    color: '#34d399',
                  }}>{f}</span>
                ))}
              </div>
              <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 8 }}>
                Validation: <strong style={{ color: result.validation_status === 'PASSED' ? '#34d399' : result.validation_status === 'FAILED' ? '#ef4444' : 'var(--color-text-muted)' }}>
                  {result.validation_status}
                </strong>
                {result.validation_errors.length > 0 && (
                  <span style={{ color: '#fca5a5', marginLeft: 8 }}>⚠ {result.validation_errors.join(' · ')}</span>
                )}
              </p>
            </div>
          )}

          {/* Dependencies table */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
              <h3>Dependencies ({filteredDeps.length}{filter !== 'ALL' ? ` of ${result.dependencies.length}` : ''})</h3>
              {/* Filter buttons */}
              <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
                {(['ALL', 'UPDATE_AVAILABLE', 'UP_TO_DATE', 'CONSTRAINT_BLOCKED', 'LOOKUP_FAILED'] as const).map(f => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    style={{
                      padding: '4px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer',
                      border: `1px solid ${filter === f ? 'var(--color-accent)' : 'var(--color-border)'}`,
                      background: filter === f ? 'rgba(99,102,241,0.15)' : 'transparent',
                      color: filter === f ? 'var(--color-accent-2)' : 'var(--color-text-muted)',
                    }}
                  >
                    {f === 'ALL' ? 'All' : STATUS_CONFIG[f]?.label ?? f}
                  </button>
                ))}
              </div>
            </div>

            {filteredDeps.length === 0 ? (
              <p className="text-muted" style={{ padding: 20 }}>No dependencies matching the current filter.</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--color-border)' }}>
                      {['Package', 'Current', 'Latest (live)', 'Status', 'Source File'].map(h => (
                        <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--color-text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredDeps.map(dep => <DepRow key={`${dep.name}-${dep.source_file}`} dep={dep} />)}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Proposed updates */}
          {result.proposed_updates.length > 0 && (
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="card-header"><h3>Update Plan ({result.proposed_updates.length})</h3></div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {result.proposed_updates.map(u => (
                  <div key={`${u.dependency_name}-${u.source_file}`} style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '10px 14px', borderRadius: 8,
                    background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.2)',
                    flexWrap: 'wrap',
                  }}>
                    <span style={{ fontWeight: 600, minWidth: 160 }}>{u.dependency_name}</span>
                    <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--color-text-muted)' }}>
                      {u.current_version ?? '—'}
                    </span>
                    <span style={{ color: '#f59e0b' }}>→</span>
                    <span style={{ fontFamily: 'monospace', fontSize: 12, color: '#34d399', fontWeight: 700 }}>
                      {u.proposed_version}
                    </span>
                    <span className="badge badge-assessment" style={{ fontSize: 10, marginLeft: 4 }}>{u.source_file}</span>
                    <span style={{ fontSize: 11, color: 'var(--color-text-muted)', marginLeft: 'auto' }}>{u.reason}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Warnings */}
          {result.warnings.length > 0 && (
            <div style={{
              padding: '14px 18px', borderRadius: 10, marginBottom: 20,
              background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)',
            }}>
              <p style={{ fontWeight: 600, marginBottom: 8 }}>⚠ Warnings ({result.warnings.length})</p>
              {result.warnings.map((w, i) => (
                <p key={i} style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>• {w}</p>
              ))}
            </div>
          )}
        </>
      )}

      {/* Empty state */}
      {!loading && !result && !error && workspacePath && (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--color-text-muted)' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔍</div>
          <p>Initializing dependency analysis...</p>
        </div>
      )}
    </div>
  );
}
