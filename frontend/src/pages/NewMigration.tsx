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
    if (!f.name.endsWith('.zip')) { setError('Only .zip files are supported.'); return; }
    setFile(f); setError('');
  };

  const handleAnalyze = async () => {
    setLoading(true); setError('');
    try {
      let res;
      if (mode === 'zip') {
        if (!file) { setError('Please select a ZIP file.'); setLoading(false); return; }
        res = await ingestZip(file, projectName || file.name.replace('.zip', ''));
      } else {
        if (!gitUrl) { setError('Please enter a Git URL.'); setLoading(false); return; }
        res = await ingestGit(gitUrl, branch, projectName || 'git-project');
      }
      const { project_id, workspace_path } = res.data;
      await analyzeRepo(workspace_path, project_id);
      // Store in sessionStorage for next page
      sessionStorage.setItem(`project_${project_id}`, JSON.stringify(res.data));
      navigate(`/analyze/${project_id}?wp=${encodeURIComponent(workspace_path)}`);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Ingestion failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 720 }}>
      <h1 style={{ marginBottom: 8 }}>New Migration</h1>
      <p className="text-muted" style={{ marginBottom: 32 }}>
        Upload your application — the platform will detect the technology stack automatically.
      </p>

      {/* Mode toggle */}
      <div className="tabs" style={{ marginBottom: 28 }}>
        <div className={`tab${mode === 'zip' ? ' active' : ''}`} onClick={() => setMode('zip')}>📦 Upload ZIP</div>
        <div className={`tab${mode === 'git' ? ' active' : ''}`} onClick={() => setMode('git')}>🔗 Git Repository</div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        {mode === 'zip' ? (
          <div
            className={`upload-zone${dragging ? ' dragging' : ''}`}
            onClick={() => fileRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
          >
            <div className="upload-zone-icon">{file ? '✅' : '📦'}</div>
            <p style={{ fontWeight: 600, marginBottom: 8 }}>
              {file ? file.name : 'Drop your ZIP here or click to browse'}
            </p>
            <p className="text-muted text-sm">
              {file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : 'Maximum 100MB · .zip only'}
            </p>
            <input ref={fileRef} type="file" accept=".zip" style={{ display: 'none' }}
              onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="form-group">
              <label className="form-label">Git Repository URL</label>
              <input className="input" placeholder="https://github.com/org/repo.git"
                value={gitUrl} onChange={e => setGitUrl(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Branch</label>
              <input className="input" placeholder="main" value={branch} onChange={e => setBranch(e.target.value)} />
            </div>
          </div>
        )}
      </div>

      <div className="form-group" style={{ marginBottom: 24 }}>
        <label className="form-label">Project Name (optional)</label>
        <input className="input" placeholder="my-legacy-app"
          value={projectName} onChange={e => setProjectName(e.target.value)} />
      </div>

      {error && (
        <div style={{
          padding: '12px 16px', borderRadius: 8, background: 'rgba(239,68,68,0.1)',
          border: '1px solid rgba(239,68,68,0.3)', color: '#fca5a5', marginBottom: 20,
        }}>{error}</div>
      )}

      <div className="flex" style={{ gap: 12 }}>
        <button className="btn btn-primary" disabled={loading} onClick={handleAnalyze}>
          {loading ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Analyzing...</> : '🔍 Analyze Application'}
        </button>
        <button className="btn btn-ghost" onClick={() => navigate('/')}>Cancel</button>
      </div>

      <div className="card" style={{ marginTop: 32, padding: 16 }}>
        <p className="text-sm text-muted" style={{ lineHeight: 1.8 }}>
          💡 <strong>You don't need to tell us the language.</strong> The platform will automatically detect:<br />
          programming languages · versions · frameworks · build systems · dependencies · databases · testing frameworks
        </p>
      </div>
    </div>
  );
}
