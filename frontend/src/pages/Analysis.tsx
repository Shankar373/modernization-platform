import { useEffect, useRef, useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { analyzeRepo, migrateAll } from '../api/client';

const STATUS_CLASSES: Record<string, string> = {
  AVAILABLE: 'badge-available', PARTIAL: 'badge-partial',
  PARTIALLY_AVAILABLE: 'badge-partial',
  ASSESSMENT_ONLY: 'badge-assessment', NOT_AVAILABLE: 'badge-unavailable',
};

const LANG_ICONS: Record<string, string> = {
  python: '🐍', javascript: '🟨', typescript: '🔷', html: '🌐',
  css: '🎨', java: '☕', json: '{ }', yaml: '📄', markdown: '📝',
  go: '🔵', ruby: '💎', php: '🐘', shell: '🖥️',
};

export default function Analysis() {
  const { projectId } = useParams();
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const workspacePath = sp.get('wp') || '';

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedLang, setSelectedLang] = useState('');
  const [targetVersion, setTargetVersion] = useState('');
  const [migratingAll, setMigratingAll] = useState(false);
  const [migrateError, setMigrateError] = useState('');
  const hasFiredAnalysis = useRef(false);

  useEffect(() => {
    if (hasFiredAnalysis.current) return;
    hasFiredAnalysis.current = true;
    analyzeRepo(workspacePath, projectId!)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(e => { setError(e?.response?.data?.detail || 'Analysis failed'); setLoading(false); });
  }, [projectId, workspacePath]);

  const handleMigrateAll = async () => {
    setMigratingAll(true);
    setMigrateError('');
    try {
      const res = await migrateAll(workspacePath, projectId!);
      const resultId = res.data.result_id;
      // Store in sessionStorage for History page
      sessionStorage.setItem(`run_${resultId}`, JSON.stringify({
        result_id: resultId,
        project_name: projectId?.slice(0, 8) || 'unknown',
        language: 'multi-language',
        status: res.data.status,
        files_modified: res.data.statistics?.files_modified || 0,
        timestamp: new Date().toISOString(),
        workspace_path: workspacePath,
      }));
      navigate(`/results/${resultId}?wp=${encodeURIComponent(workspacePath)}&mode=all`);
    } catch (e: any) {
      setMigrateError(e?.response?.data?.detail || 'Migration failed');
      setMigratingAll(false);
    }
  };

  if (loading) return (
    <div className="flex items-center gap-4" style={{ padding: 40 }}>
      <span className="spinner" style={{ width: 28, height: 28 }} />
      <span>Scanning repository and detecting technologies...</span>
    </div>
  );
  if (error) return <div style={{ color: 'var(--color-danger)', padding: 24 }}>Error: {error}</div>;
  if (!data) return null;

  const {
    profile, capabilities = [], supported_languages = [],
    unsupported_languages = [], target_recommendations = [],
  } = data;

  const availableCapabilities = capabilities.filter((c: any) => c.status === 'AVAILABLE' || c.status === 'PARTIALLY_AVAILABLE');
  const selectedCaps = capabilities.filter((c: any) => c.language?.toLowerCase() === selectedLang.toLowerCase() && c.status === 'AVAILABLE');
  const selectedRec = target_recommendations.find((r: any) => r.language?.toLowerCase() === selectedLang.toLowerCase());

  return (
    <div>
      <div className="flex items-center justify-between" style={{ marginBottom: 24 }}>
        <div>
          <h1>Application Analysis</h1>
          <p className="text-muted" style={{ marginTop: 8 }}>
            Project: <span className="text-mono">{projectId?.slice(0, 8)}</span>
            &nbsp;·&nbsp;{profile?.languages?.length || 0} languages detected
          </p>
        </div>
        <span className={`badge ${supported_languages.length > 0 ? 'badge-available' : 'badge-unavailable'}`}>
          {supported_languages.length > 0 ? `${supported_languages.length} supported` : 'Assessment only'}
        </span>
      </div>

      {/* ⚡ MODERNIZE EVERYTHING — main CTA */}
      {supported_languages.length > 0 && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(124,58,237,0.18) 0%, rgba(59,130,246,0.18) 100%)',
          border: '1.5px solid rgba(124,58,237,0.45)',
          borderRadius: 16, padding: '24px 28px', marginBottom: 24,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20,
          flexWrap: 'wrap',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <span style={{ fontSize: 22 }}>⚡</span>
              <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700 }}>Modernize Entire Application</h2>
            </div>
            <p className="text-muted" style={{ margin: 0, fontSize: 13 }}>
              Auto-runs all available adapters simultaneously:&nbsp;
              {supported_languages.map((l: string) => (
                <span key={l} style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  background: 'rgba(255,255,255,0.08)', borderRadius: 6,
                  padding: '2px 8px', marginRight: 4, fontSize: 12,
                }}>
                  {LANG_ICONS[l] || '📦'} {l}
                </span>
              ))}
            </p>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
            <button
              id="btn-modernize-all"
              className="btn btn-primary"
              onClick={handleMigrateAll}
              disabled={migratingAll}
              style={{ minWidth: 220, fontSize: '0.95rem', padding: '12px 24px' }}
            >
              {migratingAll
                ? <><span className="spinner" style={{ width: 16, height: 16, marginRight: 8 }} />Modernizing...</>
                : '⚡ Modernize Everything →'}
            </button>
            {migrateError && <span style={{ color: 'var(--color-danger)', fontSize: 12 }}>{migrateError}</span>}
          </div>
        </div>
      )}

      {/* Technology Fingerprint */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header"><h3>Technology Fingerprint</h3></div>
        {profile?.languages?.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {profile.languages.map((lang: any) => (
              <div key={lang.name} style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <span style={{ fontSize: 18 }}>{LANG_ICONS[lang.name.toLowerCase()] || '📦'}</span>
                <span style={{ width: 100, fontWeight: 600 }}>{lang.name}</span>
                {lang.version && <span className="text-muted text-mono text-sm">v{lang.version}</span>}
                <div style={{ flex: 1 }}>
                  <div className="confidence-bar" style={{ maxWidth: 200 }}>
                    <div className="confidence-fill" style={{ width: `${lang.confidence * 100}%` }} />
                  </div>
                </div>
                <span className="text-sm text-muted">{(lang.confidence * 100).toFixed(0)}% confidence</span>
                <span className={`badge ${supported_languages.includes(lang.name.toLowerCase()) ? 'badge-available' : 'badge-unavailable'}`}>
                  {supported_languages.includes(lang.name.toLowerCase()) ? 'SUPPORTED' : 'UNSUPPORTED'}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-muted">No languages detected. Is the workspace path correct?</p>
        )}
      </div>

      {/* Frameworks & Build Systems */}
      {(profile?.frameworks?.length > 0 || profile?.build_systems?.length > 0) && (
        <div className="card-grid" style={{ marginBottom: 20 }}>
          {profile.frameworks?.length > 0 && (
            <div className="card">
              <h3 style={{ marginBottom: 12 }}>Frameworks</h3>
              {profile.frameworks.map((f: any) => (
                <div key={f.name} className="flex items-center gap-2" style={{ marginBottom: 8 }}>
                  <span>{f.name}</span>
                  <span className="text-muted text-sm">({f.language})</span>
                </div>
              ))}
            </div>
          )}
          {profile.build_systems?.length > 0 && (
            <div className="card">
              <h3 style={{ marginBottom: 12 }}>Build Systems</h3>
              {profile.build_systems.map((b: any) => (
                <div key={b.name} className="flex items-center gap-2" style={{ marginBottom: 8 }}>
                  <span>{b.name}</span>
                  <span className="text-muted text-sm">({b.language})</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Capabilities */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header"><h3>Available Modernization Adapters</h3></div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {capabilities.map((cap: any, i: number) => (
            <div key={i} className="flex items-center gap-4" style={{ padding: '10px 0', borderBottom: '1px solid var(--color-border)' }}>
              <span className={`badge ${STATUS_CLASSES[cap.status] || 'badge-unavailable'}`}>{cap.status}</span>
              <span style={{ fontSize: 16 }}>{LANG_ICONS[cap.language?.toLowerCase()] || '📦'}</span>
              <span style={{ fontWeight: 500 }}>{cap.name || cap.language}</span>
              <span className="text-muted text-sm">{cap.provider}</span>
              <span className="text-sm text-muted" style={{ marginLeft: 'auto' }}>{cap.description || cap.notes}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Advanced: Per-language plan builder */}
      {availableCapabilities.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3>Advanced: Migrate Single Language</h3>
            <span className="text-muted text-sm">For fine-grained control over a specific language</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 20 }}>
            <div className="form-group">
              <label className="form-label">Language</label>
              <select className="select" value={selectedLang} onChange={e => { setSelectedLang(e.target.value); setTargetVersion(''); }}>
                <option value="">Select language...</option>
                {supported_languages.map((l: string) => <option key={l} value={l}>{LANG_ICONS[l] || ''} {l}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Target Version</label>
              <select className="select" value={targetVersion} onChange={e => setTargetVersion(e.target.value)} disabled={!selectedLang}>
                <option value="">Select target...</option>
                {selectedCaps.flatMap((c: any) => c.target_versions || [])
                  .filter((v: string, i: number, a: string[]) => a.indexOf(v) === i)
                  .map((v: string) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
            {selectedRec && (
              <div style={{ paddingTop: 28, fontSize: 12, color: 'var(--color-success)' }}>
                💡 Recommended: {selectedRec.recommended_target}
              </div>
            )}
          </div>
          <button
            className="btn btn-secondary"
            disabled={!selectedLang || !targetVersion}
            onClick={() => navigate(`/plan/${projectId}?wp=${encodeURIComponent(workspacePath)}&lang=${selectedLang}&target=${targetVersion}`)}
          >
            Build Migration Plan →
          </button>
        </div>
      )}

      {unsupported_languages.length > 0 && (
        <div className="status-banner assessment" style={{ marginTop: 20 }}>
          <span className="status-icon">ℹ️</span>
          <div>
            <strong>Unsupported technologies detected</strong>
            <p className="text-sm" style={{ marginTop: 4 }}>
              {unsupported_languages.join(', ')} — no migration connector available yet.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
