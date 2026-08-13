import { useEffect, useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { createPlan, dryRun } from '../api/client';

const PROFILES = [
  { value: 'CONSERVATIVE', label: 'Conservative', desc: 'Only required compatibility/version changes. Lowest risk.', icon: '\ud83d\udef0\ufe0f' },
  { value: 'STANDARD',     label: 'Standard',     desc: 'Includes supported cleanup and modernization.',            icon: '\u2696\ufe0f' },
  { value: 'AGGRESSIVE',   label: 'Aggressive',   desc: 'Broader modernization. Highest impact, careful review.',   icon: '\u26a1' },
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
    } catch (e: any) { setError(e?.response?.data?.detail || 'Plan creation failed'); }
    finally { setLoading(false); }
  };

  useEffect(() => { if (language && targetVersion) fetchPlan(); }, [profile]);

  const handleDryRun = async () => {
    if (!plan) return;
    setDryRunLoading(true); setDryRunResult(null);
    try {
      const res = await dryRun(workspacePath, plan.plan_id);
      setDryRunResult(res.data);
    } catch (e: any) { setDryRunResult({ success: false, notes: e?.response?.data?.detail || 'Dry run failed' }); }
    finally { setDryRunLoading(false); }
  };

  return (
    <div className="animate-fade-up" style={{ maxWidth: 820 }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 26, marginBottom: 6 }}><span className="text-gradient">Migration Plan</span></h1>
        <p className="text-muted" style={{ fontSize: 13 }}>{language} &#8594; {targetVersion} &#xB7; Project {projectId?.slice(0, 8)}</p>
      </div>

      {/* Source to Target */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', gap: 24 }}>
          <div>
            <p className="text-muted text-sm" style={{ marginBottom: 4, fontWeight: 600, letterSpacing: '0.08em' }}>SOURCE</p>
            <p style={{ fontSize: 22, fontWeight: 700 }}>{language}</p>
            <p className="text-muted text-sm">Current version</p>
          </div>
          <div style={{ fontSize: 32, color: 'var(--color-accent)', fontWeight: 300 }}>&#8594;</div>
          <div>
            <p className="text-muted text-sm" style={{ marginBottom: 4, fontWeight: 600, letterSpacing: '0.08em' }}>TARGET</p>
            <p style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-success)' }}>{language} {targetVersion}</p>
            <p className="text-muted text-sm">Modernized version</p>
          </div>
        </div>
      </div>

      {/* Migration Profile */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 16 }}>Migration Profile</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {PROFILES.map(p => (
            <div key={p.value} onClick={() => setProfile(p.value)} style={{
              padding: '16px', borderRadius: 10, cursor: 'pointer',
              border: '2px solid ' + (profile === p.value ? 'var(--color-accent)' : 'var(--color-border)'),
              background: profile === p.value ? 'rgba(29,127,138,0.08)' : 'var(--color-surface-2)',
              transition: 'all 0.2s', transform: profile === p.value ? 'scale(1.01)' : 'scale(1)',
            }}>
              <div style={{ fontSize: 22, marginBottom: 8 }}>{p.icon}</div>
              <p style={{ fontWeight: 700, marginBottom: 6, color: profile === p.value ? 'var(--color-accent)' : 'var(--color-text)', fontSize: 14 }}>{p.label}</p>
              <p className="text-sm text-muted" style={{ lineHeight: 1.5 }}>{p.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-3" style={{ padding: '20px 0' }}>
          <span className="spinner" style={{ width: 20, height: 20 }} />
          <span className="text-muted">Generating migration plan...</span>
        </div>
      )}

      {error && (
        <div style={{ padding: '12px 16px', borderRadius: 10, marginBottom: 20, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#fca5a5', fontSize: 13 }}>
          &#10060; {error}
        </div>
      )}

      {plan && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <h3>Plan Steps ({plan.steps?.length})</h3>
            <span style={{ color: RISK_COLORS[plan.overall_risk] || 'inherit', fontWeight: 700, fontSize: 13 }}>
              {plan.overall_risk} RISK
            </span>
          </div>
          <div className="timeline">
            {plan.steps?.map((step: any, i: number) => (
              <div className="timeline-item" key={step.step_id}>
                <div className="timeline-dot pending">{i + 1}</div>
                <div style={{ flex: 1 }}>
                  <p style={{ fontWeight: 600, marginBottom: 4 }}>{step.name}</p>
                  <p className="text-sm text-muted" style={{ marginBottom: 8 }}>{step.description}</p>
                  <div className="flex gap-2">
                    <span className={'badge badge-' + (step.risk === 'LOW' ? 'success' : step.risk === 'MEDIUM' ? 'warning' : 'danger')}>{step.risk}</span>
                    {step.is_reversible && <span className="badge badge-available">Reversible</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {dryRunResult && (
        <div className={'status-banner ' + (dryRunResult.success ? 'success' : 'failed')} style={{ marginBottom: 20 }}>
          <span className="status-icon">{dryRunResult.success ? '\u2705' : '\u274c'}</span>
          <div>
            <strong>Dry Run {dryRunResult.success ? 'Completed' : 'Failed'}</strong>
            {dryRunResult.notes && <p className="text-sm text-mono" style={{ marginTop: 8, whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto' }}>{dryRunResult.notes}</p>}
          </div>
        </div>
      )}

      <div className="flex gap-4" style={{ flexWrap: 'wrap', alignItems: 'center', marginTop: 8 }}>
        {plan && !dryRunResult && (
          <button className="btn btn-primary" onClick={handleDryRun} disabled={dryRunLoading} style={{ minWidth: 200 }}>
            {dryRunLoading ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Running preview...</> : '\ud83d\udd2c Preview Changes (Dry Run)'}
          </button>
        )}
        {plan && dryRunResult && !dryRunLoading && (
          <button className="btn btn-ghost" onClick={handleDryRun} disabled={dryRunLoading}>&#x21ba; Re-run Preview</button>
        )}
        {plan && dryRunResult?.success && (
          <button id="btn-approve-execute" className="btn btn-success"
            style={{ background: 'linear-gradient(135deg,#059669,#0d9488)', border: 'none', minWidth: 240 }}
            onClick={() => { sessionStorage.setItem('plan_' + plan.plan_id, JSON.stringify({ plan, workspacePath })); navigate('/execute/' + plan.plan_id + '?wp=' + encodeURIComponent(workspacePath)); }}
          >
            &#10003; Accept &amp; Execute Migration &#8594;
          </button>
        )}
        {plan && !dryRunResult && !dryRunLoading && (
          <span className="text-sm text-muted">Run a preview first to see what will change</span>
        )}
        <button className="btn btn-ghost" onClick={() => navigate(-1)}>&#8592; Back</button>
      </div>
    </div>
  );
}
