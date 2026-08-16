import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ingestZip, ingestGit, analyzeRepo } from '../api/client';

const SUPPORTED_STACKS = [
  { name: 'C# / .NET', icon: '🔷', engine: 'Roslyn AST + .NET 8 SDK', color: '#a855f7' },
  { name: 'Java', icon: '☕', engine: 'OpenRewrite + Maven/Gradle', color: '#f97316' },
  { name: 'Python', icon: '🐍', engine: 'Ruff AST + Pytest Suite', color: '#3b82f6' },
  { name: 'Node / TS', icon: '📦', engine: 'pnpm / npm + Vite AST', color: '#10b981' },
  { name: 'HTML & CSS', icon: '🎨', engine: 'DOM Tree + Modernizer', color: '#06b6d4' },
];

const PIPELINE_ROADMAP = [
  { step: '01', title: 'Universal Discovery', desc: 'Auto-detects languages, frameworks, and manifests' },
  { step: '02', title: 'Dependency Audit', desc: 'Analyzes lockfiles and auto-resolves stable updates' },
  { step: '03', title: 'AST Code Modernization', desc: 'Applies syntax transformations and preserves comments' },
  { step: '04', title: 'Differential Host Build', desc: 'Compiles and verifies zero-regression safety' },
];

export default function NewMigration() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'zip' | 'git'>('zip');
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [gitUrl, setGitUrl] = useState('');
  const [branch, setBranch] = useState('main');
  const [projectName, setProjectName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    if (!f.name.endsWith('.zip')) {
      setError('Only .zip files are supported.');
      return;
    }
    setFile(f);
    setError('');
  };

  const handleAnalyze = async () => {
    setLoading(true);
    setError('');
    try {
      let res;
      if (mode === 'zip') {
        if (!file) {
          setError('Please select a ZIP file.');
          setLoading(false);
          return;
        }
        res = await ingestZip(file, projectName || file.name.replace('.zip', ''));
      } else {
        if (!gitUrl) {
          setError('Please enter a Git URL.');
          setLoading(false);
          return;
        }
        res = await ingestGit(gitUrl, branch, projectName || 'git-project');
      }
      const { project_id, workspace_path } = res.data;
      await analyzeRepo(workspace_path, project_id);
      sessionStorage.setItem(`project_${project_id}`, JSON.stringify(res.data));
      const pName = projectName || (file ? file.name.replace(/\.zip$/i, '') : gitUrl ? gitUrl.split('/').pop()?.replace(/\.git$/i, '') : 'Project');
      navigate(`/pipeline/${project_id}?wp=${encodeURIComponent(workspace_path)}&name=${encodeURIComponent(pName || 'Project')}`);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Ingestion failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="animate-fade-up" style={{ maxWidth: 1280, margin: '0 auto', paddingBottom: 40 }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, marginBottom: 6 }}>
          <span className="text-gradient">Start New Migration</span>
        </h1>
        <p className="text-muted" style={{ fontSize: 14 }}>
          Upload your application stack or connect a repository — the platform will automatically fingerprint and modernize it.
        </p>
      </div>

      {/* 2-Column Responsive Layout */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1.35fr) minmax(0, 1fr)',
        gap: 32,
        alignItems: 'start'
      }}>
        {/* Left Column: Ingestion Controls */}
        <div>
          {/* Mode toggle */}
          <div className="tabs" style={{ marginBottom: 20 }}>
            <div
              className={`tab${mode === 'zip' ? ' active' : ''}`}
              onClick={() => { setMode('zip'); setError(''); }}
              style={{ fontSize: 14, padding: '10px 24px', fontWeight: 600 }}
            >
              📦 Upload Application ZIP
            </div>
            <div
              className={`tab${mode === 'git' ? ' active' : ''}`}
              onClick={() => { setMode('git'); setError(''); }}
              style={{ fontSize: 14, padding: '10px 24px', fontWeight: 600 }}
            >
              🔗 Git Repository Clone
            </div>
          </div>

          <div className="card" style={{ marginBottom: 20, padding: 24 }}>
            {mode === 'zip' ? (
              <div
                className={`upload-zone${dragging ? ' dragging' : ''}`}
                onClick={() => !loading && fileRef.current?.click()}
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
                style={{
                  position: 'relative',
                  padding: '36px 24px',
                  borderRadius: 12,
                  border: dragging ? '2px dashed var(--color-accent)' : '2px dashed var(--color-border)',
                  background: dragging ? 'rgba(29, 127, 138, 0.08)' : 'var(--color-surface-2)',
                  transition: 'all 0.2s ease',
                  cursor: loading ? 'wait' : 'pointer',
                  textAlign: 'center'
                }}
              >
                {loading && (
                  <div style={{
                    position: 'absolute', inset: 0,
                    background: 'rgba(15, 23, 42, 0.85)',
                    backdropFilter: 'blur(8px)',
                    borderRadius: 12,
                    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                    zIndex: 10
                  }}>
                    <span className="spinner" style={{ width: 36, height: 36, marginBottom: 14 }} />
                    <span style={{ fontWeight: 700, fontSize: 14, color: '#fff' }}>Ingesting & Fingerprinting Codebase...</span>
                    <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.6)', marginTop: 4 }}>Extracting AST signals, dependencies & README info</span>
                  </div>
                )}
                <div style={{ fontSize: 44, marginBottom: 12 }}>
                  {file ? '📦' : '☁️'}
                </div>
                <p style={{ fontWeight: 700, fontSize: 16, marginBottom: 6, color: file ? 'var(--color-accent)' : 'var(--color-text)' }}>
                  {file ? file.name : 'Drag and drop your ZIP archive here or click to browse'}
                </p>
                <p className="text-muted text-sm" style={{ margin: 0 }}>
                  {file ? `Size: ${(file.size / 1024 / 1024).toFixed(2)} MB · Ready for Ingestion` : 'Supports standard multi-project and monorepo ZIP archives (up to 4 GB)'}
                </p>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".zip"
                  style={{ display: 'none' }}
                  onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
                />
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16, position: 'relative' }}>
                {loading && (
                  <div style={{
                    position: 'absolute', inset: 0,
                    background: 'rgba(15, 23, 42, 0.85)',
                    backdropFilter: 'blur(8px)',
                    borderRadius: 8,
                    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                    zIndex: 10
                  }}>
                    <span className="spinner" style={{ width: 36, height: 36, marginBottom: 14 }} />
                    <span style={{ fontWeight: 700, fontSize: 14, color: '#fff' }}>Cloning & Analyzing Repository...</span>
                  </div>
                )}
                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600, fontSize: 13 }}>Git Repository URL</label>
                  <input
                    className="input"
                    placeholder="https://github.com/organization/repository.git"
                    value={gitUrl}
                    onChange={e => setGitUrl(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600, fontSize: 13 }}>Branch / Tag / Commit Ref</label>
                  <input
                    className="input"
                    placeholder="main"
                    value={branch}
                    onChange={e => setBranch(e.target.value)}
                  />
                </div>
              </div>
            )}
          </div>

          <div className="card" style={{ marginBottom: 20, padding: 20 }}>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label" style={{ fontWeight: 600, fontSize: 13 }}>
                Project Display Name (Optional)
              </label>
              <input
                className="input"
                placeholder={file ? file.name.replace('.zip', '') : 'e.g. enterprise-core-service'}
                value={projectName}
                onChange={e => setProjectName(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <div className="alert alert-error" style={{ marginBottom: 20 }}>
              <span>❌</span>
              <div style={{ fontWeight: 500, fontSize: 13 }}>{error}</div>
            </div>
          )}

          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <button
              className="btn btn-primary"
              disabled={loading || (mode === 'zip' && !file) || (mode === 'git' && !gitUrl)}
              onClick={handleAnalyze}
              style={{ minWidth: 200, padding: '12px 28px', fontSize: 15, fontWeight: 700 }}
            >
              {loading ? (
                <>
                  <span className="spinner" style={{ width: 16, height: 16, borderTopColor: '#fff', marginRight: 8 }} />
                  Analyzing Stack...
                </>
              ) : (
                '🚀 Start Modernization ➔'
              )}
            </button>
            <button className="btn btn-ghost" onClick={() => navigate('/')} disabled={loading} style={{ fontSize: 13 }}>
              Cancel
            </button>
          </div>
        </div>

        {/* Right Column: Engine Capabilities & Trust Roadmap */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Supported Stacks Card */}
          <div className="card" style={{ padding: 22 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-accent)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                ⚡ Supported Transformation Engines
              </h3>
              <span className="badge badge-available">7 Ready</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {SUPPORTED_STACKS.map(s => (
                <div key={s.name} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 14px', borderRadius: 8, background: 'var(--color-surface-2)',
                  border: '1px solid var(--color-border)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 18 }}>{s.icon}</span>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{s.name}</span>
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>{s.engine}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Workflow Roadmap */}
          <div className="card" style={{ padding: 22 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-accent)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 14 }}>
              🗺️ Automated 4-Phase Pipeline
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {PIPELINE_ROADMAP.map(item => (
                <div key={item.step} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                  <span style={{
                    width: 24, height: 24, borderRadius: 6,
                    background: 'rgba(29, 127, 138, 0.15)', color: 'var(--color-accent)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11, fontWeight: 700, flexShrink: 0
                  }}>{item.step}</span>
                  <div>
                    <h4 style={{ fontSize: 13, fontWeight: 600, margin: 0 }}>{item.title}</h4>
                    <p className="text-muted" style={{ fontSize: 12, margin: '2px 0 0 0', lineHeight: 1.4 }}>{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Security & Sandbox Guarantee */}
          <div style={{
            padding: '14px 18px',
            background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08), rgba(99, 102, 241, 0.06))',
            borderRadius: 10,
            border: '1px solid rgba(16, 185, 129, 0.25)',
            display: 'flex', alignItems: 'center', gap: 12
          }}>
            <span style={{ fontSize: 24 }}>🛡️</span>
            <div>
              <strong style={{ fontSize: 12, color: 'var(--color-success)' }}>Air-Gapped Sandbox & Zero-Risk AST Safety</strong>
              <p style={{ fontSize: 11, color: 'var(--color-text-muted)', margin: '2px 0 0 0' }}>
                All transformations preserve comments, format styles, and create atomic Git checkpoints before writing.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
