import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getResult, getReport } from '../api/client';

const STATUS_BANNER: Record<string, { cls: string; icon: string }> = {
  SUCCESS: { cls: 'success', icon: '✅' },
  PARTIALLY_SUCCESSFUL: { cls: 'partial', icon: '⚠️' },
  FAILED: { cls: 'failed', icon: '❌' },
  ASSESSMENT_ONLY: { cls: 'assessment', icon: 'ℹ️' },
  NOT_SUPPORTED: { cls: 'assessment', icon: '🔲' },
};

export default function Results() {
  const { resultId } = useParams();
  const navigate = useNavigate();
  const [result, setResult] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getResult(resultId!), getReport(resultId!)])
      .then(([rRes, rpRes]) => { setResult(rRes.data); setReport(rpRes.data); })
      .catch(() => {
        const cached = sessionStorage.getItem(`result_${resultId}`);
        if (cached) setResult(JSON.parse(cached));
      })
      .finally(() => setLoading(false));
  }, [resultId]);

  if (loading) return <div className="flex items-center gap-4" style={{ padding: 40 }}><span className="spinner" style={{ width: 28, height: 28 }} /><span>Loading results...</span></div>;
  if (!result) return <div style={{ padding: 24, color: 'var(--color-danger)' }}>Result not found.</div>;

  const s = result.status;
  const banner = STATUS_BANNER[s] || { cls: 'assessment', icon: 'ℹ️' };
  const stats = result.statistics || {};

  return (
    <div>
      {/* Status banner */}
      <div className={`status-banner ${banner.cls}`} style={{ marginBottom: 28 }}>
        <span className="status-icon">{banner.icon}</span>
        <div style={{ flex: 1 }}>
          <h2 style={{ marginBottom: 4 }}>MODERNIZATION RESULT — <span style={{ textTransform: 'uppercase' }}>{s.replace('_', ' ')}</span></h2>
          <p className="text-sm text-muted">Result ID: {resultId?.slice(0, 8)}</p>
        </div>
        <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          {result.completed_at ? new Date(result.completed_at).toLocaleString() : ''}
        </span>
      </div>

      {/* Stats */}
      <div className="stat-grid" style={{ marginBottom: 24 }}>
        {[
          { label: 'Files Scanned', value: stats.files_scanned ?? 0 },
          { label: 'Files Modified', value: stats.files_modified ?? 0 },
          { label: 'Files Unchanged', value: stats.files_unchanged ?? 0 },
          { label: 'Deps Updated', value: stats.dependencies_updated ?? 0 },
          { label: 'Capabilities Run', value: stats.capabilities_run ?? 0 },
          { label: 'Tests Passed', value: stats.tests_passed ?? '—' },
          { label: 'Warnings', value: result.warnings?.length ?? 0 },
          { label: 'Manual Items', value: result.manual_remediation?.length ?? 0 },
        ].map(s => (
          <div className="stat-card" key={s.label}>
            <div className="stat-value">{s.value}</div>
            <div className="stat-label">{s.label}</div>
          </div>
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
            {stats.tests_total ? `${stats.tests_total - (stats.tests_failed ?? 0)} / ${stats.tests_total} passed` : 'N/A'}
          </span>
        </div>
      </div>

      {/* Warnings */}
      {result.warnings?.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h3 style={{ marginBottom: 12, color: 'var(--color-warning)' }}>⚠️ Warnings</h3>
          {result.warnings.map((w: string, i: number) => <p key={i} className="text-sm" style={{ marginBottom: 6 }}>• {w}</p>)}
        </div>
      )}

      {/* Timeline */}
      {result.timeline?.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h3 style={{ marginBottom: 16 }}>Execution Timeline</h3>
          <div className="timeline">
            {result.timeline.map((t: any, i: number) => (
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

      {/* Actions */}
      <div className="flex gap-4" style={{ flexWrap: 'wrap' }}>
        {result.changed_files?.length > 0 && (
          <button className="btn btn-primary" onClick={() => navigate(`/results/${resultId}/changes`)}>
            📄 View Code Changes ({result.changed_files.length} files)
          </button>
        )}
        <button className="btn btn-ghost" onClick={() => {
          const blob = new Blob([JSON.stringify(report || result, null, 2)], { type: 'application/json' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a'); a.href = url; a.download = `migration-report-${resultId?.slice(0, 8)}.json`; a.click();
        }}>⬇ Download Report (JSON)</button>
        <button className="btn btn-ghost" onClick={() => navigate('/')}>← Dashboard</button>
      </div>
    </div>
  );
}
