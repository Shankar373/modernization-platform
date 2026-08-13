import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface HistoryEntry {
  resultId: string; planId: string; projectName: string; language: string;
  status: string; completedAt: string; filesModified: number; filesScanned: number;
}

const STATUS_META: Record<string, { cls: string; icon: string; label: string; color: string }> = {
  SUCCESS:              { cls: 'badge-available',   icon: '\u2705', label: 'Success',       color: '#10b981' },
  PARTIALLY_SUCCESSFUL: { cls: 'badge-partial',     icon: '\u26a0\ufe0f', label: 'Partial',  color: '#f2bd22' },
  FAILED:               { cls: 'badge-danger',      icon: '\u274c', label: 'Failed',         color: '#ef4444' },
  ASSESSMENT_ONLY:      { cls: 'badge-assessment',  icon: '\u2139\ufe0f', label: 'Assessment', color: '#8b5cf6' },
  NOT_SUPPORTED:        { cls: 'badge-unavailable', icon: '\u2b1c', label: 'Not Supported', color: '#475569' },
};

const LANG_ICONS: Record<string, string> = {
  python: '\ud83d\udc0d', java: '\u2615', html: '\ud83c\udf10', css: '\ud83c\udfa8',
  javascript: '\ud83d\udfe8', typescript: '\ud83d\udd37', go: '\ud83d\udc39', php: '\ud83d\udc18',
  csharp: '\ud83d\udd37',
};

const LANG_COLORS: Record<string, string> = {
  python: '#3b82f6', java: '#f97316', html: '#10b981', css: '#06b6d4',
  javascript: '#eab308', typescript: '#3b82f6', csharp: '#a855f7',
};

function countUp(target: number, setter: (v: number) => void, duration = 700) {
  if (target === 0) { setter(0); return; }
  let start = 0;
  const inc = target / (duration / 16);
  const t = setInterval(() => {
    start += inc;
    if (start >= target) { setter(target); clearInterval(t); }
    else setter(Math.floor(start));
  }, 16);
}

export default function History() {
  const navigate = useNavigate();
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [filter, setFilter] = useState('');
  const [animTotals, setAnimTotals] = useState({ runs: 0, success: 0, partial: 0, files: 0 });

  useEffect(() => {
    const found: HistoryEntry[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i);
      if (!key?.startsWith('run_')) continue;
      try {
        const e = JSON.parse(sessionStorage.getItem(key) || '{}') as HistoryEntry;
        if (e.resultId) found.push(e);
      } catch { /* ignore */ }
    }
    found.sort((a, b) => new Date(b.completedAt).getTime() - new Date(a.completedAt).getTime());
    setEntries(found);
    const t = { runs: found.length, success: found.filter(e => e.status === 'SUCCESS').length, partial: found.filter(e => e.status === 'PARTIALLY_SUCCESSFUL').length, files: found.reduce((s, e) => s + (e.filesModified ?? 0), 0) };
    countUp(t.runs,    v => setAnimTotals(p => ({ ...p, runs: v })));
    countUp(t.success, v => setAnimTotals(p => ({ ...p, success: v })));
    countUp(t.partial, v => setAnimTotals(p => ({ ...p, partial: v })));
    countUp(t.files,   v => setAnimTotals(p => ({ ...p, files: v })));
  }, []);

  const clearHistory = () => {
    const keys: string[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i);
      if (k?.startsWith('run_')) keys.push(k);
    }
    keys.forEach(k => sessionStorage.removeItem(k));
    setEntries([]); setAnimTotals({ runs: 0, success: 0, partial: 0, files: 0 });
  };

  const filtered = filter ? entries.filter(e =>
    e.projectName?.toLowerCase().includes(filter.toLowerCase()) ||
    e.language?.toLowerCase().includes(filter.toLowerCase()) ||
    e.status?.toLowerCase().includes(filter.toLowerCase())
  ) : entries;

  const statCards = [
    { label: 'Total Runs',     value: animTotals.runs,    color: 'var(--color-accent-2)',      icon: '\ud83d\ude80' },
    { label: 'Successful',     value: animTotals.success,  color: 'var(--color-success)',        icon: '\u2705' },
    { label: 'Partial',        value: animTotals.partial,  color: 'var(--color-warning)',        icon: '\u26a1' },
    { label: 'Files Modified', value: animTotals.files,    color: 'var(--color-systema-purple)', icon: '\ud83d\udcc4' },
  ];

  return (
    <div className="animate-fade-up">
      <div className="flex items-center justify-between" style={{ marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: 26, marginBottom: 6 }}><span className="text-gradient">Migration History</span></h1>
          <p className="text-muted" style={{ fontSize: 14 }}>{entries.length} migration{entries.length !== 1 ? 's' : ''} recorded this session</p>
        </div>
        <div className="flex gap-2">
          {entries.length > 0 && <button className="btn btn-ghost" onClick={clearHistory} style={{ fontSize: 12 }}>\ud83d\uddd1 Clear</button>}
          <button className="btn btn-systema" onClick={() => navigate('/new')}> New Migration</button>
        </div>
      </div>

      {entries.length > 0 && (
        <div className="stat-grid" style={{ marginBottom: 28 }}>
          {statCards.map(s => (
            <div className="stat-card" key={s.label}>
              <div style={{ fontSize: 20, marginBottom: 4 }}>{s.icon}</div>
              <div className="stat-value" style={{ color: s.color }}>{s.value}</div>
              <div className="stat-label">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {entries.length > 0 && (
        <div className="form-group" style={{ maxWidth: 380, marginBottom: 20 }}>
          <input className="input" placeholder="Filter by project, language or status" value={filter} onChange={e => setFilter(e.target.value)} />
        </div>
      )}

      {filtered.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '56px 32px' }}>
          <div className="empty-icon">\ud83d\udccb</div>
          <h3 style={{ marginBottom: 10 }}>{filter ? 'No migrations match your filter.' : 'No migrations yet this session.'}</h3>
          <p className="text-muted" style={{ marginBottom: 20 }}>Upload a ZIP or connect a repository to get started.</p>
          {!filter && <button className="btn btn-primary" onClick={() => navigate('/new')}>Start your first migration</button>}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map((entry) => {
            const meta = STATUS_META[entry.status] || STATUS_META.ASSESSMENT_ONLY;
            const langKey = entry.language?.toLowerCase();
            const icon = LANG_ICONS[langKey] || '\ud83d\udce6';
            const langColor = LANG_COLORS[langKey] || 'var(--color-systema-purple)';
            const date = entry.completedAt ? new Date(entry.completedAt).toLocaleString() : '-';
            return (
              <div key={entry.resultId} className="card"
                style={{ display: 'grid', gridTemplateColumns: '56px 1fr auto auto', alignItems: 'center', gap: 20, padding: '18px 24px', cursor: 'pointer', transition: 'transform 0.18s, box-shadow 0.18s', borderLeft: '3px solid ' + meta.color }}
                onClick={() => navigate('/results/' + entry.resultId)}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.transform = 'translateX(4px)'; (e.currentTarget as HTMLElement).style.boxShadow = 'var(--shadow-lg)'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.transform = 'translateX(0)'; (e.currentTarget as HTMLElement).style.boxShadow = ''; }}
              >
                <div style={{ width: 48, height: 48, borderRadius: 12, background: langColor + '18', border: '1px solid ' + langColor + '33', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24 }}>{icon}</div>
                <div>
                  <div className="flex items-center gap-3" style={{ marginBottom: 6 }}>
                    <span style={{ fontWeight: 700, fontSize: 15 }}>{entry.projectName || 'Unnamed project'}</span>
                    <span className={'badge ' + meta.cls} style={{ fontSize: 11 }}>{meta.icon} {meta.label}</span>
                    <span className="badge badge-assessment" style={{ fontSize: 10, textTransform: 'uppercase' }}>{entry.language}</span>
                  </div>
                  <p className="text-sm text-muted">{entry.filesModified ?? 0} files modified &middot; {entry.filesScanned ?? 0} scanned &middot; {date}</p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--color-accent)' }}>{entry.filesModified ?? 0}</div>
                  <div className="text-sm text-muted">changed</div>
                </div>
                <span style={{ color: 'var(--color-text-muted)', fontSize: 20 }}>&#8250;</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
