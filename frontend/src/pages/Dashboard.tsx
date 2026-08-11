export default function Dashboard() {
  return (
    <div>
      <div className="flex items-center justify-between mb-4" style={{ marginBottom: 32 }}>
        <div>
          <h1>Migration Dashboard</h1>
          <p className="text-muted mt-4" style={{ marginTop: 8 }}>
            Enterprise Application Modernization &amp; Migration Platform
          </p>
        </div>
        <a href="/new">
          <button className="btn btn-primary">＋ New Migration</button>
        </a>
      </div>

      {/* Stats */}
      <div className="stat-grid" style={{ marginBottom: 32 }}>
        {[
          { label: 'Total Migrations', value: '0' },
          { label: 'Successful', value: '0' },
          { label: 'In Progress', value: '0' },
          { label: 'Languages Supported', value: '2' },
        ].map(s => (
          <div className="stat-card" key={s.label}>
            <div className="stat-value">{s.value}</div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Platform capabilities overview */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <h3>Migration Connectors</h3>
        </div>
        <div className="card-grid">
          {[
            { lang: 'Java', tool: 'OpenRewrite', status: 'AVAILABLE', icon: '☕' },
            { lang: 'Python', tool: 'Ruff', status: 'AVAILABLE', icon: '🐍' },
            { lang: 'C / C++', tool: 'clang-tidy', status: 'NOT_AVAILABLE', icon: '⚙️' },
            { lang: 'C# / .NET', tool: 'Roslyn', status: 'NOT_AVAILABLE', icon: '#️⃣' },
            { lang: 'JavaScript', tool: 'jscodeshift', status: 'NOT_AVAILABLE', icon: '🟨' },
            { lang: 'TypeScript', tool: 'ts-morph', status: 'NOT_AVAILABLE', icon: '🔷' },
            { lang: 'Go', tool: 'go fix', status: 'NOT_AVAILABLE', icon: '🐹' },
            { lang: 'PHP', tool: 'Rector', status: 'NOT_AVAILABLE', icon: '🐘' },
            { lang: 'COBOL', tool: '—', status: 'ASSESSMENT_ONLY', icon: '🏛️' },
          ].map(c => (
            <div key={c.lang} className="card" style={{ padding: '16px', gap: 0 }}>
              <div className="flex items-center gap-2" style={{ marginBottom: 10 }}>
                <span style={{ fontSize: 20 }}>{c.icon}</span>
                <span style={{ fontWeight: 600 }}>{c.lang}</span>
                <span className="text-muted" style={{ marginLeft: 'auto', fontSize: 12 }}>{c.tool}</span>
              </div>
              <span className={`badge badge-${c.status === 'AVAILABLE' ? 'available' : c.status === 'ASSESSMENT_ONLY' ? 'assessment' : 'unavailable'}`}>
                {c.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Architecture flow */}
      <div className="card">
        <div className="card-header"><h3>Platform Flow</h3></div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          {[
            'Upload ZIP / Git URL', 'Secure Ingestion', 'Universal Discovery',
            'Technology Fingerprint', 'Capability Registry', 'Migration Assessment',
            'Target Recommendation', 'Migration Plan', 'User Approval',
            'Dry Run', 'Migration', 'Build / Test / Security',
            'Before/After Diff', 'File Explorer', 'Report', 'Download',
          ].map((step, i, arr) => (
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
