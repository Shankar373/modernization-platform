import { useEffect, useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { createPlan, dryRun } from '../api/client';

const PROFILES = [
  { value: 'CONSERVATIVE', label: 'Conservative', desc: 'Only required compatibility/version changes. Lowest risk.' },
  { value: 'STANDARD', label: 'Standard', desc: 'Includes supported cleanup and modernization.' },
  { value: 'AGGRESSIVE', label: 'Aggressive', desc: 'Broader modernization. Highest impact, requires careful review.' },
];

const RISK_COLORS: Record<string, string> = {
  LOW: 'var(--color-success)', MEDIUM: 'var(--color-warning)',
  HIGH: 'var(--color-danger)', CRITICAL: 'var(--color-danger)',
};

export default function MigrationPlan() {
  const { projectId } = useParams();
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const workspacePath = sp.get('wp') || '';
  const language = sp.get('lang') || '';
  const targetVersion = sp.get('target') || '';
  const [profile, setProfile] = useState('CONSERVATIVE');
  const [plan, setPlan] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [dryRunResult, setDryRunResult] = useState<any>(null);
  const [dryRunLoading, setDryRunLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchPlan = async () => {
    setLoading(true); setError(''); setPlan(null);
    try {
      const res = await createPlan({ workspace_path: workspacePath, project_id: projectId!, language, target_version: targetVersion, migration_profile: profile });
      setPlan(res.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Plan creation failed');
    } finally { setLoading(false); }
  };

  useEffect(() => { if (language && targetVersion) fetchPlan(); }, [profile]);

  const handleDryRun = async () => {
    if (!plan) return;
    setDryRunLoading(true); setDryRunResult(null);
    try {
      const res = await dryRun(workspacePath, plan.plan_id);
      setDryRunResult(res.data);
    } catch (e: any) {
      setDryRunResult({ success: false, notes: e?.response?.data?.detail || 'Dry run failed' });
    } finally { setDryRunLoading(false); }
  };

  return (
    <div style={{ maxWidth: 820 }}>
      <div style={{ marginBottom: 32 }}>
        <h1>Migration Plan</h1>
        <p className="text-muted" style={{ marginTop: 8 }}>
          {language} → {targetVersion} · Project {projectId?.slice(0, 8)}
        </p>
      </div>

      {/* Source → Target */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', gap: 24 }}>
          <div>
            <p className="text-muted text-sm" style={{ marginBottom: 4 }}>SOURCE</p>
            <p style={{ fontSize: 22, fontWeight: 700 }}>{language}</p>
            <p className="text-muted">Current version</p>
          </div>
          <div style={{ fontSize: 32, color: 'var(--color-accent)' }}>→</div>
          <div>
            <p className="text-muted text-sm" style={{ marginBottom: 4 }}>TARGET</p>
            <p style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-success)' }}>{language} {targetVersion}</p>
            <p className="text-muted">Modernized version</p>
          </div>
        </div>
      </div>

      {/* Migration profile */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 16 }}>Migration Profile</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {PROFILES.map(p => (
            <div key={p.value}
              onClick={() => setProfile(p.value)}
              style={{
                padding: '14px', borderRadius: 8, cursor: 'pointer',
                border: `2px solid ${profile === p.value ? 'var(--color-accent)' : 'var(--color-border)'}`,
                background: profile === p.value ? 'rgba(99,102,241,0.08)' : 'var(--color-surface-2)',
                transition: 'all 0.2s',
              }}>
              <p style={{ fontWeight: 600, marginBottom: 6, color: profile === p.value ? 'var(--color-accent-2)' : 'var(--color-text)' }}>{p.label}</p>
              <p className="text-sm text-muted">{p.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Plan steps */}
      {loading && <div className="flex items-center gap-4" style={{ padding: 20 }}><span className="spinner" />Generating plan...</div>}
      {error && <div style={{ color: 'var(--color-danger)', marginBottom: 20 }}>{error}</div>}
      {plan && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <h3>Plan Steps ({plan.steps?.length})</h3>
            <span style={{ color: RISK_COLORS[plan.overall_risk] || 'inherit', fontWeight: 600 }}>
              Risk: {plan.overall_risk}
            </span>
          </div>
          <div className="timeline">
            {plan.steps?.map((step: any, i: number) => (
              <div className="timeline-item" key={step.step_id}>
                <div className="timeline-dot pending">{i + 1}</div>
                <div style={{ flex: 1 }}>
                  <p style={{ fontWeight: 600 }}>{step.name}</p>
                  <p className="text-sm text-muted" style={{ marginTop: 4 }}>{step.description}</p>
                  <div className="flex gap-2" style={{ marginTop: 8 }}>
                    <span className={`badge badge-${step.risk === 'LOW' ? 'success' : step.risk === 'MEDIUM' ? 'warning' : 'danger'}`}>
                      {step.risk}
                    </span>
                    {step.is_reversible && <span className="badge badge-available">Reversible</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Dry run result */}
      {dryRunResult && (
        <div className={`status-banner ${dryRunResult.success ? 'success' : 'failed'}`} style={{ marginBottom: 20 }}>
          <span className="status-icon">{dryRunResult.success ? '✅' : '❌'}</span>
          <div>
            <strong>Dry Run {dryRunResult.success ? 'Completed' : 'Failed'}</strong>
            {dryRunResult.notes && <p className="text-sm text-mono" style={{ marginTop: 8, whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto' }}>{dryRunResult.notes}</p>}
          </div>
        </div>
      )}

      <div className="flex gap-4" style={{ flexWrap: 'wrap', alignItems: 'center' }}>
        {plan && !dryRunResult && (
          <button className="btn btn-primary" onClick={handleDryRun} disabled={dryRunLoading} style={{ minWidth: 180 }}>
            {dryRunLoading ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Running preview...</> : '🔬 Preview Changes (Dry Run)'}
          </button>
        )}
        {plan && dryRunResult && !dryRunLoading && (
          <button className="btn btn-ghost" onClick={handleDryRun} disabled={dryRunLoading}>
            🔄 Re-run Preview
          </button>
        )}
        {plan && dryRunResult?.success && (
          <button
            id="btn-approve-execute"
            className="btn btn-success"
            style={{ background: 'linear-gradient(135deg,#059669,#0d9488)', border: 'none', minWidth: 220 }}
            onClick={() => {
              sessionStorage.setItem(`plan_${plan.plan_id}`, JSON.stringify({ plan, workspacePath }));
              navigate(`/execute/${plan.plan_id}?wp=${encodeURIComponent(workspacePath)}`);
            }}
          >
            ✅ Accept & Execute Migration →
          </button>
        )}
        {plan && !dryRunResult && !dryRunLoading && (
          <span className="text-sm text-muted" style={{ paddingLeft: 4 }}>
            ↑ Run a preview first to see what will change
          </span>
        )}
        <button className="btn btn-ghost" onClick={() => navigate(-1)}>← Back</button>
      </div>
    </div>
  );
}
