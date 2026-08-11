import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface HistoryEntry {
  resultId: string;
  planId: string;
  projectName: string;
  language: string;
  status: string;
  completedAt: string;
  filesModified: number;
  filesScanned: number;
}

const STATUS_META: Record<string, { cls: string; icon: string; label: string }> = {
  SUCCESS:              { cls: 'badge-available',   icon: '✅', label: 'Success' },
  PARTIALLY_SUCCESSFUL: { cls: 'badge-partial',     icon: '⚠️', label: 'Partial' },
  FAILED:               { cls: 'badge-danger',      icon: '❌', label: 'Failed' },
  ASSESSMENT_ONLY:      { cls: 'badge-assessment',  icon: 'ℹ️', label: 'Assessment' },
  NOT_SUPPORTED:        { cls: 'badge-unavailable', icon: '🔲', label: 'Not Supported' },
};

const LANG_ICONS: Record<string, string> = {
  python: '🐍', java: '☕', html: '🌐', css: '🎨',
  javascript: '🟨', typescript: '🔷', go: '🐹', php: '🐘',
};

export default function History() {
  const navigate = useNavigate();
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    // Collect all history entries from sessionStorage
    const found: HistoryEntry[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i);
      if (!key?.startsWith('run_')) continue;
      try {
        const entry = JSON.parse(sessionStorage.getItem(key) || '{}') as HistoryEntry;
        if (entry.resultId) found.push(entry);
      } catch {
        // ignore malformed entries
      }
    }
    // Sort newest first
    found.sort((a, b) => new Date(b.completedAt).getTime() - new Date(a.completedAt).getTime());
    setEntries(found);
  }, []);

  const clearHistory = () => {
    const keys: string[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i);
      if (key?.startsWith('run_')) keys.push(key);
    }
    keys.forEach(k => sessionStorage.removeItem(k));
    setEntries([]);
  };

  const filtered = filter
    ? entries.filter(e =>
        e.projectName.toLowerCase().includes(filter.toLowerCase()) ||
        e.language.toLowerCase().includes(filter.toLowerCase()) ||
        e.status.toLowerCase().includes(filter.toLowerCase())
      )
    : entries;

  return (
    <div>
      <div className="flex items-center justify-between" style={{ marginBottom: 32 }}>
        <div>
          <h1>Migration History</h1>
          <p className="text-muted" style={{ marginTop: 8 }}>
            {entries.length} migration{entries.length !== 1 ? 's' : ''} recorded this session
          </p>
        </div>
        <div className="flex gap-2">
          {entries.length > 0 && (
            <button className="btn btn-ghost" onClick={clearHistory} style={{ fontSize: 12 }}>
              🗑 Clear History
            </button>
          )}
          <button className="btn btn-primary" onClick={() => navigate('/new')}>
            ＋ New Migration
          </button>
        </div>
      </div>

      {entries.length > 0 && (
        <div className="form-group" style={{ maxWidth: 360, marginBottom: 24 }}>
          <input
            className="input"
            placeholder="🔍  Filter by project, language or status…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
          />
        </div>
      )}

      {filtered.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 64 }}>
          <p style={{ fontSize: 48, marginBottom: 20 }}>📋</p>
          <p className="text-muted" style={{ marginBottom: 20 }}>
            {filter ? 'No migrations match your filter.' : 'No migrations yet this session.'}
          </p>
          {!filter && (
            <button className="btn btn-primary" onClick={() => navigate('/new')}>
              Start your first migration →
            </button>
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {filtered.map((entry) => {
            const meta = STATUS_META[entry.status] || STATUS_META.ASSESSMENT_ONLY;
            const icon = LANG_ICONS[entry.language?.toLowerCase()] || '📦';
            const date = entry.completedAt
              ? new Date(entry.completedAt).toLocaleString()
              : '—';

            return (
              <div
                key={entry.resultId}
                className="card"
                style={{
                  display: 'grid',
                  gridTemplateColumns: '48px 1fr auto auto',
                  alignItems: 'center',
                  gap: 20,
                  padding: '18px 24px',
                  cursor: 'pointer',
                  transition: 'border-color 0.18s',
                }}
                onClick={() => navigate(`/results/${entry.resultId}`)}
              >
                {/* Language icon */}
                <div style={{
                  width: 48, height: 48, borderRadius: 12,
                  background: 'var(--color-surface-2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 24,
                }}>
                  {icon}
                </div>

                {/* Info */}
                <div>
                  <div className="flex items-center gap-3" style={{ marginBottom: 6 }}>
                    <span style={{ fontWeight: 600, fontSize: 15 }}>
                      {entry.projectName || 'Unnamed project'}
                    </span>
                    <span className={`badge ${meta.cls}`} style={{ fontSize: 11 }}>
                      {meta.icon} {meta.label}
                    </span>
                    <span className="badge badge-assessment" style={{ fontSize: 10, textTransform: 'uppercase' }}>
                      {entry.language}
                    </span>
                  </div>
                  <p className="text-sm text-muted">
                    {entry.filesModified ?? 0} file{entry.filesModified !== 1 ? 's' : ''} modified
                    &nbsp;·&nbsp;{entry.filesScanned ?? 0} scanned
                    &nbsp;·&nbsp;{date}
                  </p>
                </div>

                {/* Stats pill */}
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-accent)' }}>
                    {entry.filesModified ?? 0}
                  </div>
                  <div className="text-sm text-muted">changed</div>
                </div>

                {/* Arrow */}
                <span style={{ color: 'var(--color-text-muted)', fontSize: 20 }}>›</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Summary stats */}
      {entries.length > 0 && (
        <div className="stat-grid" style={{ marginTop: 32 }}>
          {[
            { label: 'Total Runs',     value: entries.length },
            { label: 'Successful',     value: entries.filter(e => e.status === 'SUCCESS').length },
            { label: 'Partial',        value: entries.filter(e => e.status === 'PARTIALLY_SUCCESSFUL').length },
            { label: 'Files Modified', value: entries.reduce((s, e) => s + (e.filesModified ?? 0), 0) },
          ].map(s => (
            <div className="stat-card" key={s.label}>
              <div className="stat-value">{s.value}</div>
              <div className="stat-label">{s.label}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
