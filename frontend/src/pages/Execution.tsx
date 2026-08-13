import { useEffect, useRef, useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { executeMigration } from '../api/client';

const STEPS = [
  { label: 'Repository ingested',     icon: '\ud83d\udce6' },
  { label: 'Technology detected',     icon: '\ud83e\uddec' },
  { label: 'Migration plan loaded',   icon: '\ud83d\uddfa\ufe0f' },
  { label: 'User approved plan',      icon: '\u2705' },
  { label: 'Executing migration',     icon: '\u2699\ufe0f' },
  { label: 'Build & test validation', icon: '\ud83e\uddea' },
  { label: 'Report generated',        icon: '\ud83d\udcc4' },
];

export default function Execution() {
  const { planId } = useParams();
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const workspacePath = sp.get('wp') || '';
  const [stepIndex, setStepIndex] = useState(0);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const hasFired = useRef(false);

  useEffect(() => {
    if (hasFired.current) return;
    hasFired.current = true;
    const run = async () => {
      for (let i = 0; i < STEPS.length - 2; i++) {
        setStepIndex(i + 1);
        await new Promise(r => setTimeout(r, 600));
      }
      try {
        const res = await executeMigration(workspacePath, planId!);
        const data = res.data;
        setResult(data);
        setStepIndex(STEPS.length);
        sessionStorage.setItem('result_' + data.result_id, JSON.stringify(data));
        const planMeta = (() => { try { return JSON.parse(sessionStorage.getItem('plan_' + planId) || '{}'); } catch { return {}; } })();
        const language = planMeta?.plan?.targets?.[0]?.language || sp.get('lang') || 'unknown';
        const projectName = planMeta?.plan?.project_id?.slice(0, 8) || planId?.slice(0, 8) || 'unknown';
        sessionStorage.setItem('run_' + data.result_id, JSON.stringify({
          resultId: data.result_id, planId, projectName, language,
          status: data.status, completedAt: data.completed_at || new Date().toISOString(),
          filesModified: data.statistics?.files_modified ?? 0,
          filesScanned:  data.statistics?.files_scanned  ?? 0,
        }));
        setTimeout(() => navigate('/results/' + data.result_id), 1000);
      } catch (e: any) { setError(e?.response?.data?.detail || 'Migration failed'); setStepIndex(-1); }
    };
    run();
  }, [planId]);

  return (
    <div className="animate-fade-up" style={{ maxWidth: 600 }}>
      <h1 style={{ fontSize: 26, marginBottom: 6 }}><span className="text-gradient">Migration Execution</span></h1>
      <p className="text-muted" style={{ fontSize: 13, marginBottom: 32 }}>Plan: {planId?.slice(0, 8)}</p>

      <div className="card">
        <div className="timeline">
          {STEPS.map((step, i) => {
            const done    = i < stepIndex && stepIndex !== -1;
            const running = i === stepIndex && stepIndex !== STEPS.length && stepIndex !== -1;
            const cls = done ? 'done' : running ? 'running' : 'pending';
            return (
              <div className="timeline-item" key={step.label} style={{ opacity: done ? 0.7 : 1, transition: 'opacity 0.3s' }}>
                <div className={'timeline-dot ' + cls}>
                  {done ? '\u2713' : running ? '\u2026' : i + 1}
                </div>
                <div style={{ paddingTop: 2 }}>
                  <span style={{ fontSize: 18, marginRight: 8 }}>{step.icon}</span>
                  <span style={{ fontWeight: running ? 700 : done ? 400 : 500, color: running ? 'var(--color-accent)' : 'var(--color-text-muted)', transition: 'color 0.3s' }}>
                    {step.label}
                  </span>
                  {running && <span className="spinner" style={{ width: 12, height: 12, marginLeft: 10, display: 'inline-block' }} />}
                </div>
              </div>
            );
          })}
        </div>

        {error && (
          <div style={{ marginTop: 20, padding: '12px 16px', borderRadius: 8, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#fca5a5' }}>
            {error}
          </div>
        )}

        {result && (
          <div className="status-banner success" style={{ marginTop: 24 }}>
            <span className="status-icon">\u2705</span>
            <div>
              <strong>Migration {result.status}</strong>
              <p className="text-sm" style={{ marginTop: 4 }}>Redirecting to results...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
