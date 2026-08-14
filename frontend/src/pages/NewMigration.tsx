import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ingestZip, ingestGit, analyzeRepo } from '../api/client';

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
      navigate(`/pipeline/${project_id}?wp=${encodeURIComponent(workspace_path)}`);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Ingestion failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 720 }} className="animate-fade-up">
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 26, marginBottom: 8 }} className="text-gradient">New Migration</h1>
        <p className="text-muted">
          Upload your application stack — the platform will automatically detect and assess it.
        </p>
      </div>

      {/* Mode toggle */}
      <div className="tabs" style={{ marginBottom: 28 }}>
        <div
          className={`tab${mode === 'zip' ? ' active' : ''}`}
          onClick={() => { setMode('zip'); setError(''); }}
          style={{ fontSize: 14, padding: '10px 24px' }}
        >
          📦 Upload ZIP
        </div>
        <div
          className={`tab${mode === 'git' ? ' active' : ''}`}
          onClick={() => { setMode('git'); setError(''); }}
          style={{ fontSize: 14, padding: '10px 24px' }}
        >
          🔗 Git Repository
        </div>
      </div>

      <div className="card" style={{ marginBottom: 24, padding: 28, background: '#fff' }}>
        {mode === 'zip' ? (
          <div
            className={`upload-zone${dragging ? ' dragging' : ''}`}
            onClick={() => fileRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
            style={{ position: 'relative' }}
          >
            {loading && (
              <div style={{
                position: 'absolute', inset: 0, background: 'rgba(255,255,255,0.7)',
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', zIndex: 10
              }}>
                <span className="spinner" style={{ width: 32, height: 32, marginBottom: 12 }} />
                <span style={{ fontWeight: 600, color: 'var(--color-accent)' }}>Ingesting & Analyzing Stack...</span>
              </div>
            )}
            <div className="upload-zone-icon" style={{ fontSize: 44, marginBottom: 12 }}>
              {file ? '📄' : '📦'}
            </div>
            <p style={{ fontWeight: 600, fontSize: 15, marginBottom: 8, color: 'var(--color-accent-2)' }}>
              {file ? file.name : 'Drag and drop your ZIP file here or click to browse'}
            </p>
            <p className="text-muted text-sm">
              {file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : 'Supported archive types: .zip (max 4GB)'}
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20, position: 'relative' }}>
            {loading && (
              <div style={{
                position: 'absolute', inset: 0, background: 'rgba(255,255,255,0.7)',
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', zIndex: 10
              }}>
                <span className="spinner" style={{ width: 32, height: 32, marginBottom: 12 }} />
                <span style={{ fontWeight: 600, color: 'var(--color-accent)' }}>Cloning & Analyzing Repository...</span>
              </div>
            )}
            <div className="form-group">
              <label className="form-label">Git Repository URL</label>
              <input
                className="input"
                placeholder="https://github.com/organization/repository.git"
                value={gitUrl}
                onChange={e => setGitUrl(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Branch / Commit Ref</label>
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

      <div className="form-group" style={{ marginBottom: 28 }}>
        <label className="form-label">Custom Project Name (Optional)</label>
        <input
          className="input"
          placeholder={file ? file.name.replace('.zip', '') : 'my-modernized-service'}
          value={projectName}
          onChange={e => setProjectName(e.target.value)}
        />
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 24 }}>
          <span>❌</span>
          <div style={{ fontWeight: 500 }}>{error}</div>
        </div>
      )}

      <div className="flex" style={{ gap: 12 }}>
        <button
          className="btn btn-primary"
          disabled={loading || (mode === 'zip' && !file) || (mode === 'git' && !gitUrl)}
          onClick={handleAnalyze}
          style={{ minWidth: 160 }}
        >
          {loading ? (
            <>
              <span className="spinner" style={{ width: 16, height: 16, borderTopColor: '#fff' }} />
              Analyzing Stack...
            </>
          ) : (
            '🔍 Ingest & Analyze'
          )}
        </button>
        <button className="btn btn-ghost" onClick={() => navigate('/')} disabled={loading}>
          Cancel
        </button>
      </div>

      <div className="card" style={{ marginTop: 40, padding: 20, borderLeft: '4px solid var(--color-accent)' }}>
        <h4 style={{ marginBottom: 8, fontSize: 13, textTransform: 'uppercase', color: 'var(--color-accent)', letterSpacing: '0.04em' }}>
          💡 SYSTEMAOPS STACK RECOGNITION
        </h4>
        <p className="text-sm text-muted" style={{ lineHeight: 1.8 }}>
          Our universal discovery engine automatically inspects package manifests, configuration files, and imports to detect:
          <strong> C#, Java, Python, JavaScript, Go, PHP, Kotlin, Ruby, and CSS</strong> frameworks, build configurations, test files, and dependency trees. No project flags required.
        </p>
      </div>
    </div>
  );
}
