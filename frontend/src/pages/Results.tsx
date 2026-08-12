import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getResult, getReport, downloadModernizedZip } from '../api/client';
import type { MigrationResult, MigrationReport, FileChangeMetadata, MigrationStatistics } from '../types';

const STATUS_BANNER: Record<string, { cls: string; icon: string }> = {
  SUCCESS:              { cls: 'success',    icon: '✅' },
  PARTIALLY_SUCCESSFUL: { cls: 'partial',    icon: '⚠️' },
  FAILED:               { cls: 'failed',     icon: '❌' },
  ASSESSMENT_ONLY:      { cls: 'assessment', icon: 'ℹ️' },
  NOT_SUPPORTED:        { cls: 'assessment', icon: '🔲' },
};

function MiniDiff({ diff }: { diff: string }) {
  if (!diff) return <p className="text-muted text-sm" style={{ padding: '8px 0' }}>No diff available.</p>;
  const lines = diff.split('\n').slice(0, 60);
  return (
    <div className="diff-viewer" style={{ maxHeight: 260, overflow: 'auto', marginTop: 8, fontSize: 12 }}>
      {lines.map((line, i) => {
        const cls = line.startsWith('+') && !line.startsWith('+++') ? 'added'
          : line.startsWith('-') && !line.startsWith('---') ? 'removed'
          : line.startsWith('@@') ? 'header' : '';
        return (
          <div key={i} className={`diff-line ${cls}`}>
            <span className="diff-line-num">{i + 1}</span>
            <span className="diff-line-content">{line}</span>
          </div>
        );
      })}
      {diff.split('\n').length > 60 && (
        <div className="diff-line header" style={{ padding: '4px 12px', fontStyle: 'italic' }}>
          … {diff.split('\n').length - 60} more lines — view full diff in Code Changes
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function FileRow({
  f,
  expanded,
  onToggle,
}: {
  f: FileChangeMetadata;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div style={{ borderBottom: '1px solid var(--color-border)' }}>
      <div
        className="flex items-center gap-3"
        style={{ padding: '10px 0', cursor: 'pointer' }}
        onClick={onToggle}
      >
        <span style={{ color: 'var(--color-text-muted)', fontSize: 16, width: 20, textAlign: 'center' }}>
          {expanded ? '▼' : '▶'}
        </span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {f.file}
        </span>
        <div className="flex gap-2">
          <span
            className={`badge ${f.status === 'MODIFIED' ? 'badge-warning' : f.status === 'ADDED' ? 'badge-success' : 'badge-danger'}`}
            style={{ fontSize: 10 }}
          >
            {f.status}
          </span>
          {f.tools?.map((t) => (
            <span key={t} className="badge badge-assessment" style={{ fontSize: 10 }}>{t}</span>
          ))}
        </div>
      </div>
      {expanded && <MiniDiff diff={f.diff} />}
    </div>
  );
}

export default function Results() {
  const { resultId } = useParams<{ resultId: string }>();
  const navigate = useNavigate();
  const [result, setResult]   = useState<MigrationResult | null>(null);
  const [report, setReport]   = useState<MigrationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedFile, setExpandedFile] = useState<string | null>(null);

  useEffect(() => {
    if (!resultId) return;
    Promise.all([getResult(resultId), getReport(resultId)])
      .then(([rRes, rpRes]) => {
        setResult(rRes.data as MigrationResult);
        setReport(rpRes.data as MigrationReport);
      })
      .catch(() => {
        const cached = sessionStorage.getItem(`result_${resultId}`);
        if (cached) setResult(JSON.parse(cached) as MigrationResult);
      })
      .finally(() => setLoading(false));
  }, [resultId]);

  if (loading) return (
    <div className="flex items-center gap-4" style={{ padding: 40 }}>
      <span className="spinner" style={{ width: 28, height: 28 }} />
      <span>Loading results...</span>
    </div>
  );
  if (!result) return <div style={{ padding: 24, color: 'var(--color-danger)' }}>Result not found.</div>;

  const s: string   = result.status;
  const banner      = STATUS_BANNER[s] || { cls: 'assessment', icon: 'ℹ️' };
  const stats: MigrationStatistics = result.statistics || {} as MigrationStatistics;
  const changed: FileChangeMetadata[] = result.changed_files || [];

  const statCards = [
    { label: 'Files Scanned',    value: stats.files_scanned   ?? 0 },
    { label: 'Files Modified',   value: stats.files_modified  ?? 0 },
    { label: 'Files Unchanged',  value: stats.files_unchanged ?? 0 },
    { label: 'Deps Updated',     value: stats.dependencies_updated ?? 0 },
    { label: 'Capabilities Run', value: stats.capabilities_run ?? 0 },
    { label: 'Tests Passed',     value: stats.tests_passed ?? '—' },
    { label: 'Warnings',         value: result.warnings?.length ?? 0 },
    { label: 'Manual Items',     value: result.manual_remediation?.length ?? 0 },
  ];

  return (
    <div>
      {/* Status banner */}
      <div className={`status-banner ${banner.cls}`} style={{ marginBottom: 28 }}>
        <span className="status-icon">{banner.icon}</span>
        <div style={{ flex: 1 }}>
          <h2 style={{ marginBottom: 4 }}>
            MODERNIZATION RESULT — <span style={{ textTransform: 'uppercase' }}>{s.replace(/_/g, ' ')}</span>
          </h2>
          <p className="text-sm text-muted">Result ID: {resultId?.slice(0, 8)}</p>
        </div>
        <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          {result.completed_at ? new Date(result.completed_at).toLocaleString() : ''}
        </span>
      </div>

      {/* Stats grid */}
      <div className="stat-grid" style={{ marginBottom: 24 }}>
        {statCards.map((sc) => (
          <StatCard key={sc.label} label={sc.label} value={sc.value as string | number} />
        ))}
      </div>

      {/* Build & Test status */}
      <div className="card-grid" style={{ marginBottom: 24 }}>
        <div className="card" style={{ textAlign: 'center' }}>
          <p className="text-muted text-sm" style={{ marginBottom: 8 }}>Build</p>
          <span className={`badge ${stats.build_passed ? 'badge-success' : 'badge-danger'}`}>
            {stats.build_passed == null ? 'N/A' : stats.build_passed ? 'PASSED' : 'FAILED'}
          </span>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <p className="text-muted text-sm" style={{ marginBottom: 8 }}>Tests</p>
          <span className={`badge ${stats.tests_passed ? 'badge-success' : stats.tests_total ? 'badge-danger' : 'badge-unavailable'}`}>
            {stats.tests_total
              ? `${stats.tests_total - (stats.tests_failed ?? 0)} / ${stats.tests_total} passed`
              : 'N/A'}
          </span>
        </div>
      </div>

      {/* Warnings */}
      {(result.warnings?.length ?? 0) > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h3 style={{ marginBottom: 12, color: 'var(--color-warning)' }}>⚠️ Warnings</h3>
          {result.warnings!.map((w, i) => (
            <p key={i} className="text-sm" style={{ marginBottom: 6 }}>• {w}</p>
          ))}
        </div>
      )}

      {/* Changed Files with Mini Diff */}
      {changed.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <h3>📄 Changed Files ({changed.length})</h3>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => navigate(`/results/${resultId}/changes`)}
            >
              Full Diff Viewer →
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {changed.map((f) => (
              <FileRow
                key={f.file}
                f={f}
                expanded={expandedFile === f.file}
                onToggle={() => setExpandedFile(expandedFile === f.file ? null : f.file)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Timeline */}
      {(result.timeline?.length ?? 0) > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h3 style={{ marginBottom: 16 }}>Execution Timeline</h3>
          <div className="timeline">
            {result.timeline!.map((t, i) => (
              <div className="timeline-item" key={i}>
                <div className={`timeline-dot ${t.status === 'completed' ? 'done' : t.status === 'failed' ? 'failed' : 'running'}`}>
                  {t.status === 'completed' ? '✓' : t.status === 'failed' ? '✗' : i + 1}
                </div>
                <div>
                  <p style={{ fontWeight: 500 }}>{t.step}</p>
                  <p className="text-sm text-muted">{t.ts}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-4" style={{ flexWrap: 'wrap' }}>
        {changed.length > 0 && (
          <button className="btn btn-primary" onClick={() => navigate(`/results/${resultId}/changes`)}>
            📄 Full Code Diff ({changed.length} files)
          </button>
        )}
        <button
          id="btn-download-zip"
          className="btn btn-primary"
          style={{ background: 'linear-gradient(135deg,#7c3aed,#3b82f6)', border: 'none' }}
          onClick={() => resultId && downloadModernizedZip(resultId)}
        >
          📦 Download Modernized Application (ZIP)
        </button>
        <button className="btn btn-ghost" onClick={() => navigate('/')}>← Dashboard</button>
        <button className="btn btn-ghost" onClick={() => navigate('/history')}>⟳ History</button>
      </div>
    </div>
  );
}
