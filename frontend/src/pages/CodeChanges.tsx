import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getChangedFiles } from '../api/client';

export default function CodeChanges() {
  const { resultId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<any>(null);
  const [selected, setSelected] = useState<any>(null);
  const [viewMode, setViewMode] = useState<'diff' | 'sidebyside'>('diff');

  useEffect(() => {
    getChangedFiles(resultId!)
      .then(r => { setData(r.data); if (r.data.changed_files?.[0]) setSelected(r.data.changed_files[0]); })
      .catch(() => {});
  }, [resultId]);

  const renderDiff = (diff: string) => {
    if (!diff) return <p className="text-muted text-sm" style={{ padding: 16 }}>No diff available</p>;
    return (
      <div className="diff-viewer">
        {diff.split('\n').map((line, i) => {
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
      </div>
    );
  };

  if (!data) return <div className="flex items-center gap-4" style={{ padding: 40 }}><span className="spinner" style={{ width: 28, height: 28 }} /><span>Loading changes...</span></div>;

  return (
    <div>
      <div className="flex items-center justify-between" style={{ marginBottom: 24 }}>
        <div>
          <h1>Code Changes</h1>
          <p className="text-muted" style={{ marginTop: 8 }}>{data.changed_files?.length} files modified</p>
        </div>
        <div className="flex gap-2">
          <button className={`btn btn-sm ${viewMode === 'diff' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setViewMode('diff')}>Unified Diff</button>
          <button className={`btn btn-sm ${viewMode === 'sidebyside' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setViewMode('sidebyside')}>Side by Side</button>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate(-1)}>← Back</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 20 }}>
        {/* File tree */}
        <div className="card" style={{ padding: 12, alignSelf: 'start', maxHeight: '80vh', overflow: 'auto' }}>
          <p className="text-sm text-muted" style={{ padding: '4px 8px 12px', fontWeight: 600 }}>Changed Files</p>
          <div className="file-tree">
            {data.changed_files?.map((f: any) => (
              <div
                key={f.file}
                className={`file-item${selected?.file === f.file ? ' selected' : ''}`}
                onClick={() => setSelected(f)}
              >
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>
                  {f.file.split('/').pop()}
                </span>
                <span className={`badge file-badge ${f.status === 'MODIFIED' ? 'badge-warning' : f.status === 'ADDED' ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: 9 }}>
                  {f.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Diff viewer */}
        {selected && (
          <div>
            <div className="card" style={{ marginBottom: 16, padding: 16 }}>
              <p style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: 13, marginBottom: 8 }}>{selected.file}</p>
              <div className="flex gap-2">
                <span className={`badge ${selected.status === 'MODIFIED' ? 'badge-warning' : selected.status === 'ADDED' ? 'badge-success' : 'badge-danger'}`}>{selected.status}</span>
                {selected.tools?.map((t: string) => <span key={t} className="badge badge-assessment">{t}</span>)}
                {selected.changes?.map((c: any, i: number) => <span key={i} className="badge badge-unavailable text-sm">{c.type}</span>)}
              </div>
              {selected.changes?.[0]?.description && (
                <p className="text-sm text-muted" style={{ marginTop: 8 }}>{selected.changes[0].description}</p>
              )}
            </div>

            {viewMode === 'diff' ? (
              renderDiff(selected.diff)
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <p className="text-sm text-muted" style={{ marginBottom: 8, fontWeight: 600 }}>LEGACY VERSION</p>
                  <div className="diff-viewer">
                    <div className="diff-line removed">
                      <span className="diff-line-num"></span>
                      <span className="diff-line-content">{selected.before_content?.slice(0, 3000) || '(empty)'}</span>
                    </div>
                  </div>
                </div>
                <div>
                  <p className="text-sm" style={{ marginBottom: 8, fontWeight: 600, color: 'var(--color-success)' }}>MODERNIZED VERSION</p>
                  <div className="diff-viewer">
                    <div className="diff-line added">
                      <span className="diff-line-num"></span>
                      <span className="diff-line-content">{selected.after_content?.slice(0, 3000) || '(empty)'}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
