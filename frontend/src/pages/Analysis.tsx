import { useEffect, useRef, useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { analyzeRepo, dryRunAll, approveAndExecute, runDependencyAnalysis } from '../api/client';
import type { DryRunAllResult, AdapterDryRunResult, MigrationProfile, Dependency } from '../types';

// ── Constants ─────────────────────────────────────────────────────────────────

const LANG_ICONS: Record<string, string> = {
  python: '🐍', javascript: '🟨', typescript: '🔷', html: '🌐',
  css: '🎨', java: '☕', json: '{ }', yaml: '📄', markdown: '📝',
  go: '🔵', ruby: '💎', php: '🐘', shell: '🖥️', generic: '📦',
  csharp: '🔷', 'c#': '🔷',
};


const STATUS_CLASSES: Record<string, string> = {
  AVAILABLE: 'badge-available', PARTIAL: 'badge-partial',
  PARTIALLY_AVAILABLE: 'badge-partial',
  ASSESSMENT_ONLY: 'badge-assessment', NOT_AVAILABLE: 'badge-unavailable',
};

const PROFILES: Array<{ value: MigrationProfile; label: string; desc: string; color: string }> = [
  { value: 'CONSERVATIVE', label: 'Conservative', desc: 'Safety-first — only required compatibility changes.', color: 'var(--color-success)' },
  { value: 'STANDARD',     label: 'Standard',     desc: 'Balanced — all supported modernizations.',           color: 'var(--color-accent)' },
  { value: 'AGGRESSIVE',   label: 'Aggressive',   desc: 'Maximum impact — broadest refactoring scope.',       color: 'var(--color-warning)' },
];

// ── Pipeline stages ───────────────────────────────────────────────────────────
type Stage = 'analysis' | 'dry-run-running' | 'dry-run-done' | 'executing' | 'done';

// ── Sub-components ────────────────────────────────────────────────────────────

function AdapterRow({ r, isRunning }: { r: AdapterDryRunResult; isRunning: boolean }) {
  const icon = LANG_ICONS[r.language] ?? '📦';
  return (
    <div
      className="flex items-center gap-3"
      style={{
        padding: '12px 16px', borderRadius: 10,
        background: r.success ? 'rgba(16,185,129,0.06)' : 'rgba(239,68,68,0.06)',
        border: `1px solid ${r.success ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
        marginBottom: 8,
      }}
    >
      {isRunning
        ? <span className="spinner" style={{ width: 18, height: 18, flexShrink: 0 }} />
        : <span style={{ fontSize: 20, width: 26, textAlign: 'center' }}>{r.success ? icon : '⚠️'}</span>
      }
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="flex items-center gap-2">
          <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{r.language}</span>
          <span className="badge badge-assessment" style={{ fontSize: 10 }}>{r.adapter}</span>
        </div>
        {r.notes && (
          <p className="text-sm text-muted" style={{ marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {r.notes}
          </p>
        )}
        {r.warnings?.length > 0 && (
          <p className="text-sm" style={{ color: 'var(--color-warning)', marginTop: 2, fontSize: 11 }}>
            ⚠ {r.warnings[0]}
          </p>
        )}
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 22, color: r.files_would_change > 0 ? 'var(--color-accent-2)' : 'var(--color-text-muted)' }}>
          {r.files_would_change}
        </div>
        <div className="text-sm text-muted">files</div>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function Analysis() {
  const { projectId } = useParams<{ projectId: string }>();
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const workspacePath = sp.get('wp') || '';

  // Analysis state
  const [data, setData]           = useState<any>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const hasFiredAnalysis          = useRef(false);

  // Pipeline state
  const [stage, setStage]         = useState<Stage>('analysis');
  const [profile, setProfile]     = useState<MigrationProfile>('STANDARD');
  const [preview, setPreview]     = useState<DryRunAllResult | null>(null);
  const [dryRunError, setDryRunError] = useState('');
  const [execError, setExecError] = useState('');

  // Integrated Dependency Analysis State
  const [dependencies, setDependencies] = useState<Dependency[]>([]);
  const [dependencyUpdatedFiles, setDependencyUpdatedFiles] = useState<string[]>([]);
  const [dependenciesLoading, setDependenciesLoading] = useState(false);

  // Single-language advanced builder
  const [selectedLang, setSelectedLang]     = useState('');
  const [targetVersion, setTargetVersion]   = useState('');

  // ── Load analysis ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (hasFiredAnalysis.current) return;
    hasFiredAnalysis.current = true;
    if (!projectId) return;
    analyzeRepo(workspacePath, projectId)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(e => { setError(e?.response?.data?.detail || 'Analysis failed'); setLoading(false); });
  }, [projectId, workspacePath]);

  // ── Step 1: Dry-run ALL (Modernization + Dependencies) ──────────────────────
  const handleDryRunAll = async () => {
    if (!projectId) return;
    setStage('dry-run-running');
    setDryRunError('');
    setPreview(null);
    setDependencies([]);
    setDependenciesLoading(true);

    try {
      // Run both codebase modernization dry run and dependency analysis in parallel
      const [modernizationRes, dependencyRes] = await Promise.all([
        dryRunAll(workspacePath, projectId, profile),
        runDependencyAnalysis(workspacePath, projectId, true),
      ]);

      setPreview(modernizationRes.data as DryRunAllResult);
      setDependencies((dependencyRes.data?.dependencies || []) as Dependency[]);
      setStage('dry-run-done');
    } catch (e: any) {
      setDryRunError(e?.response?.data?.detail || 'Dry run failed. Please try again.');
      setStage('analysis');
    } finally {
      setDependenciesLoading(false);
    }
  };

  // ── Step 2: Accept → Execute (Modernization + Dependencies) ─────────────────
  const handleApproveExecute = async () => {
    if (!projectId) return;
    setStage('executing');
    setExecError('');
    try {
      // Execute both code refactoring and dependency upgrades
      const res = await approveAndExecute(workspacePath, projectId, profile);
      const resultId = res.data.result_id;

      // Persist to history
      sessionStorage.setItem(`run_${resultId}`, JSON.stringify({
        resultId,
        projectName: projectId.slice(0, 8),
        language: 'multi-language',
        status: res.data.status,
        filesModified: res.data.statistics?.files_modified ?? 0,
        filesScanned: res.data.statistics?.files_scanned ?? 0,
        completedAt: res.data.completed_at || new Date().toISOString(),
      }));

      setStage('done');
      setTimeout(() => navigate(`/results/${resultId}?wp=${encodeURIComponent(workspacePath)}&mode=all`), 800);
    } catch (e: any) {
      setExecError(e?.response?.data?.detail || 'Execution failed.');
      setStage('dry-run-done'); // let user try again
    }
  };

  // ── Render guards ───────────────────────────────────────────────────────────
  if (loading) return (
    <div className="flex items-center gap-4" style={{ padding: 40 }}>
      <span className="spinner" style={{ width: 28, height: 28 }} />
      <span>Scanning repository and detecting technologies...</span>
    </div>
  );
  if (error) return <div style={{ color: 'var(--color-danger)', padding: 24 }}>Error: {error}</div>;
  if (!data) return null;

  const {
    profile: techProfile, capabilities = [],
    supported_languages = [], unsupported_languages = [],
    target_recommendations = [],
  } = data;

  const availableCapabilities = capabilities.filter((c: any) =>
    c.status === 'AVAILABLE' || c.status === 'PARTIALLY_AVAILABLE'
  );
  const selectedCaps = capabilities.filter((c: any) =>
    c.language?.toLowerCase() === selectedLang.toLowerCase() && c.status === 'AVAILABLE'
  );
  const selectedRec = target_recommendations.find((r: any) =>
    r.language?.toLowerCase() === selectedLang.toLowerCase()
  );

  const isRunning = stage === 'dry-run-running' || stage === 'executing' || stage === 'done';

  // Filter dependencies to show only those that have updates available
  const outdatedDependencies = dependencies.filter(d => d.status === 'UPDATE_AVAILABLE');

  return (
    <div>
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between" style={{ marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1>Application Analysis</h1>
          <p className="text-muted" style={{ marginTop: 8 }}>
            Project: <span className="text-mono">{projectId?.slice(0, 8)}</span>
            &nbsp;·&nbsp;{techProfile?.languages?.length || 0} languages detected
          </p>
        </div>
        <span className={`badge ${supported_languages.length > 0 ? 'badge-available' : 'badge-unavailable'}`}>
          {supported_languages.length > 0 ? `${supported_languages.length} supported` : 'Assessment only'}
        </span>
      </div>

      {/* ── ⚡ AUTOMATED PIPELINE CARD ──────────────────────────────────────── */}
      {supported_languages.length > 0 && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(124,58,237,0.14) 0%, rgba(59,130,246,0.14) 100%)',
          border: '1.5px solid rgba(124,58,237,0.4)',
          borderRadius: 16, padding: '24px 28px', marginBottom: 28,
        }}>
          {/* Title row */}
          <div className="flex items-center justify-between" style={{ marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
            <div>
              <div className="flex items-center gap-2" style={{ marginBottom: 6 }}>
                <span style={{ fontSize: 22 }}>⚡</span>
                <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>Modernize Entire Application</h2>
              </div>
              <p className="text-muted" style={{ margin: 0, fontSize: 13 }}>
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

            {/* Stage indicator */}
            <div className="flex items-center gap-2">
              {(['dry-run-running', 'dry-run-done', 'executing', 'done'] as Stage[]).map((s, i) => {
                const labels = ['Preview', 'Review', 'Execute', 'Done'];
                const active = stage === s || (stage === 'done' && i < 3);
                const past = (['dry-run-done', 'executing', 'done'] as Stage[]).indexOf(stage) > i - 1;
                return (
                  <div key={s} className="flex items-center gap-1">
                    <div style={{
                      width: 24, height: 24, borderRadius: '50%', fontSize: 11, fontWeight: 700,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      background: past || active ? 'var(--color-accent)' : 'rgba(255,255,255,0.08)',
                      color: past || active ? '#fff' : 'var(--color-text-muted)',
                      transition: 'all 0.3s',
                    }}>
                      {past && stage !== s ? '✓' : i + 1}
                    </div>
                    <span style={{ fontSize: 11, color: active ? 'var(--color-accent-2)' : 'var(--color-text-muted)' }}>
                      {labels[i]}
                    </span>
                    {i < 3 && <span style={{ color: 'var(--color-border)', margin: '0 2px' }}>›</span>}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Profile selector — only visible before dry-run */}
          {stage === 'analysis' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10, marginBottom: 20 }}>
              {PROFILES.map(p => (
                <div
                  key={p.value}
                  onClick={() => setProfile(p.value)}
                  style={{
                    padding: '12px 14px', borderRadius: 10, cursor: 'pointer', transition: 'all 0.2s',
                    border: `2px solid ${profile === p.value ? p.color : 'var(--color-border)'}`,
                    background: profile === p.value ? `${p.color}18` : 'rgba(255,255,255,0.04)',
                  }}
                >
                  <p style={{ fontWeight: 600, marginBottom: 4, color: profile === p.value ? p.color : 'var(--color-text)' }}>
                    {p.label}
                  </p>
                  <p className="text-sm text-muted">{p.desc}</p>
                </div>
              ))}
            </div>
          )}

          {/* ── STAGE: DRY-RUN RUNNING ──────────────────────────────────────── */}
          {stage === 'dry-run-running' && (
            <div>
              <div className="flex items-center gap-3" style={{ marginBottom: 16 }}>
                <span className="spinner" style={{ width: 22, height: 22 }} />
                <span style={{ fontWeight: 600 }}>Previewing changes and analyzing packages...</span>
              </div>
              <p className="text-sm text-muted">
                Running codebase dry-run and registry dependency checks in parallel for: {supported_languages.map((l: string) => (
                  <span key={l} style={{ marginRight: 6 }}>{LANG_ICONS[l] || '📦'} {l}</span>
                ))}
              </p>
            </div>
          )}

          {/* ── STAGE: DRY-RUN DONE — show preview tables ───────────────────── */}
          {stage === 'dry-run-done' && preview && (
            <div>
              {/* Summary banner */}
              <div style={{
                background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)',
                borderRadius: 10, padding: '14px 18px', marginBottom: 16,
                display: 'flex', alignItems: 'center', gap: 16,
              }}>
                <span style={{ fontSize: 28 }}>🔍</span>
                <div style={{ flex: 1 }}>
                  <p style={{ fontWeight: 700, marginBottom: 2 }}>Preview Complete — no files were modified yet</p>
                  <p className="text-sm text-muted">
                    {preview.summary} · {outdatedDependencies.length} dependencies have newer stable versions available.
                  </p>
                </div>
                <div style={{ display: 'flex', gap: 20, textAlign: 'right' }}>
                  <div>
                    <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--color-accent-2)' }}>
                      {preview.total_files_would_change}
                    </div>
                    <div className="text-sm text-muted">code files</div>
                  </div>
                  <div style={{ borderLeft: '1px solid var(--color-border)', paddingLeft: 20 }}>
                    <div style={{ fontSize: 28, fontWeight: 800, color: '#f59e0b' }}>
                      {outdatedDependencies.length}
                    </div>
                    <div className="text-sm text-muted">outdated deps</div>
                  </div>
                </div>
              </div>

              {/* Grid: Code modifications and dependency upgrades */}
              <div style={{ display: 'grid', gridTemplateColumns: outdatedDependencies.length > 0 ? '1.2fr 1fr' : '1fr', gap: 20, marginBottom: 20 }}>
                {/* Code files */}
                <div>
                  <h4 style={{ marginBottom: 12, fontSize: 13, textTransform: 'uppercase', color: 'var(--color-text-muted)', letterSpacing: '0.05em' }}>Code Modifications</h4>
                  {preview.per_adapter.map((r) => (
                    <AdapterRow key={r.language} r={r} isRunning={false} />
                  ))}
                </div>

                {/* Dependencies */}
                {outdatedDependencies.length > 0 && (
                  <div>
                    <h4 style={{ marginBottom: 12, fontSize: 13, textTransform: 'uppercase', color: 'var(--color-text-muted)', letterSpacing: '0.05em' }}>Dependency Upgrades</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 320, overflowY: 'auto', paddingRight: 4 }}>
                      {outdatedDependencies.map(dep => (
                        <div key={`${dep.name}-${dep.source_file}`} style={{
                          padding: '10px 14px', borderRadius: 8,
                          background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.2)',
                          display: 'flex', alignItems: 'center', gap: 10, fontSize: 12,
                        }}>
                          <span style={{ fontWeight: 600, flex: 1 }}>{dep.name}</span>
                          <span style={{ fontFamily: 'monospace', color: 'var(--color-text-muted)' }}>{dep.current_version}</span>
                          <span style={{ color: '#f59e0b' }}>→</span>
                          <span style={{ fontFamily: 'monospace', color: '#34d399', fontWeight: 700 }}>{dep.latest_stable_version}</span>
                          <span className="badge badge-assessment" style={{ fontSize: 9 }}>{dep.source_file}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {execError && (
                <div style={{
                  padding: '10px 14px', borderRadius: 8, marginBottom: 14,
                  background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                  color: '#fca5a5', fontSize: 13,
                }}>
                  ❌ {execError}
                </div>
              )}

              {/* Action buttons */}
              <div className="flex gap-3" style={{ flexWrap: 'wrap' }}>
                <button
                  id="btn-approve-execute"
                  className="btn btn-primary"
                  style={{
                    background: 'linear-gradient(135deg,#7c3aed,#3b82f6)', border: 'none',
                    fontSize: '0.95rem', padding: '12px 28px',
                  }}
                  onClick={handleApproveExecute}
                >
                  ✅ Accept & Execute Modernization →
                </button>
                <button
                  className="btn btn-ghost"
                  onClick={() => { setStage('analysis'); setPreview(null); }}
                >
                  ← Change Profile
                </button>
              </div>
            </div>
          )}

          {/* ── STAGE: EXECUTING ───────────────────────────────────────────── */}
          {stage === 'executing' && (
            <div>
              <div className="flex items-center gap-3" style={{ marginBottom: 16 }}>
                <span className="spinner" style={{ width: 22, height: 22 }} />
                <span style={{ fontWeight: 700, fontSize: '1.05rem' }}>Executing modernization in parallel...</span>
              </div>
              {preview && (
                <div>
                  {preview.per_adapter.map((r) => (
                    <AdapterRow key={r.language} r={r} isRunning />
                  ))}
                </div>
              )}
              <p className="text-sm text-muted" style={{ marginTop: 12 }}>
                🔒 Modernization adapters and dependency updates running simultaneously. This may take 30–120 seconds.
              </p>
            </div>
          )}

          {/* ── STAGE: DONE ────────────────────────────────────────────────── */}
          {stage === 'done' && (
            <div className="flex items-center gap-3">
              <span style={{ fontSize: 28 }}>✅</span>
              <div>
                <p style={{ fontWeight: 700 }}>Modernization complete — redirecting to results...</p>
              </div>
            </div>
          )}

          {/* ── Initial CTA buttons ─────────────────────────────────────────── */}
          {stage === 'analysis' && (
            <div className="flex gap-3" style={{ flexWrap: 'wrap' }}>
              {dryRunError && (
                <p style={{ color: 'var(--color-danger)', fontSize: 13, width: '100%', marginBottom: 8 }}>
                  ❌ {dryRunError}
                </p>
              )}
              <button
                id="btn-dry-run-all"
                className="btn btn-primary"
                onClick={handleDryRunAll}
                disabled={isRunning}
                style={{ minWidth: 220, fontSize: '0.95rem', padding: '12px 24px' }}
              >
                🔬 Preview Changes (Dry Run) →
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Technology Fingerprint ──────────────────────────────────────────── */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header"><h3>Technology Fingerprint</h3></div>
        {techProfile?.languages?.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {techProfile.languages.map((lang: any) => {
              // Versions that already start with "." or letters don't need a "v" prefix
              const rawVer: string | undefined = lang.version;
              const versionLabel = rawVer
                ? rawVer.startsWith('.') || rawVer.startsWith('v')
                  ? rawVer
                  : `v${rawVer}`
                : null;
              // For multi-version strings (C# .NET), split them for tag display
              const versionTags = rawVer && rawVer.includes(', ')
                ? rawVer.split(', ').map((v: string) => v.trim())
                : null;
              return (
                <div key={lang.name}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: versionTags ? 8 : 0 }}>
                    <span style={{ fontSize: 18 }}>{LANG_ICONS[lang.name.toLowerCase()] || '📦'}</span>
                    <span style={{ width: 100, fontWeight: 600 }}>{lang.name}</span>
                    {versionLabel && !versionTags && (
                      <span className="text-muted text-mono text-sm">{versionLabel}</span>
                    )}
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
                  {/* Multi-version display: e.g. for C# .NET Framework 4.6.1, 4.7, 4.7.2, .NET 6.0-windows */}
                  {versionTags && (
                    <div style={{ marginLeft: 134, marginBottom: 4 }}>
                      <span style={{
                        fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
                        letterSpacing: '0.08em', color: 'var(--color-text-muted)',
                        marginRight: 8,
                      }}>
                        Detected Targets
                      </span>
                      <span style={{ display: 'inline-flex', flexWrap: 'wrap', gap: 4 }}>
                        {versionTags.map((v: string) => (
                          <span key={v} style={{
                            display: 'inline-block',
                            padding: '2px 8px',
                            borderRadius: 4,
                            fontSize: 11,
                            fontFamily: 'monospace',
                            background: v.includes('Framework')
                              ? 'rgba(99,102,241,0.15)'
                              : v.includes('Core')
                                ? 'rgba(16,185,129,0.12)'
                                : 'rgba(59,130,246,0.12)',
                            color: v.includes('Framework')
                              ? '#a5b4fc'
                              : v.includes('Core')
                                ? '#6ee7b7'
                                : '#93c5fd',
                            border: '1px solid',
                            borderColor: v.includes('Framework')
                              ? 'rgba(99,102,241,0.3)'
                              : v.includes('Core')
                                ? 'rgba(16,185,129,0.3)'
                                : 'rgba(59,130,246,0.3)',
                          }}>
                            {v}
                          </span>
                        ))}
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-muted">No languages detected. Is the workspace path correct?</p>
        )}
      </div>

      {/* ── Frameworks, Build Systems & Test Frameworks ──────────────────────── */}
      {(techProfile?.frameworks?.length > 0 || techProfile?.build_systems?.length > 0 || techProfile?.testing_frameworks?.length > 0) && (

        <div className="card-grid" style={{ marginBottom: 20 }}>
          {techProfile.frameworks?.length > 0 && (
            <div className="card">
              <h3 style={{ marginBottom: 12 }}>🏗️ Frameworks</h3>
              {techProfile.frameworks.map((f: any) => (
                <div key={f.name} className="flex items-center gap-2" style={{ marginBottom: 8 }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: 'var(--color-accent)', display: 'inline-block', flexShrink: 0,
                  }} />
                  <span style={{ fontWeight: 500 }}>{f.name}</span>
                  <span className="text-muted text-sm">({f.language})</span>
                </div>
              ))}
            </div>
          )}
          {techProfile.build_systems?.length > 0 && (
            <div className="card">
              <h3 style={{ marginBottom: 12 }}>⚙️ Build Systems</h3>
              {techProfile.build_systems.map((b: any) => (
                <div key={b.name} className="flex items-center gap-2" style={{ marginBottom: 8 }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: 'var(--color-success)', display: 'inline-block', flexShrink: 0,
                  }} />
                  <span style={{ fontWeight: 500 }}>{b.name}</span>
                  <span className="text-muted text-sm">({b.language})</span>
                </div>
              ))}
            </div>
          )}
          {/* Test Frameworks card — always shown when the outer condition is true */}
          <div className="card">
            <h3 style={{ marginBottom: 12 }}>🧪 Test Frameworks</h3>
            {techProfile.testing_frameworks?.length > 0 ? (
              techProfile.testing_frameworks.map((t: string) => (
                <div key={t} className="flex items-center gap-2" style={{ marginBottom: 8 }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: '#f59e0b', display: 'inline-block', flexShrink: 0,
                  }} />
                  <span style={{ fontWeight: 500 }}>{t}</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted" style={{ marginTop: 4 }}>
                Not detected — no test files or test package references found in this project.
              </p>
            )}
          </div>
        </div>
      )}


      {/* ── Capabilities grid ──────────────────────────────────────────────── */}
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

      {/* ── Advanced: Per-language plan builder ────────────────────────────── */}
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
                {selectedCaps
                  .flatMap((c: any) => c.target_versions || [])
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

      {/* ── Unsupported languages ───────────────────────────────────────────── */}
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
