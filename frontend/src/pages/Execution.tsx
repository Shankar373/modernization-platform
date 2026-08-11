import { useEffect, useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { executeMigration } from '../api/client';

const STEPS = [
  'Repository ingested',
  'Technology detected',
  'Migration plan loaded',
  'User approved plan',
  'Executing migration',
  'Build & test validation',
  'Report generated',
];

export default function Execution() {
  const { planId } = useParams();
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const workspacePath = sp.get('wp') || '';
  const [stepIndex, setStepIndex] = useState(0);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const run = async () => {
      // Animate steps
      for (let i = 0; i < STEPS.length - 2; i++) {
        setStepIndex(i + 1);
        await new Promise(r => setTimeout(r, 600));
      }
      try {
        const res = await executeMigration(workspacePath, planId!);
        setResult(res.data);
        setStepIndex(STEPS.length);
        sessionStorage.setItem(`result_${res.data.result_id}`, JSON.stringify(res.data));
        setTimeout(() => navigate(`/results/${res.data.result_id}`), 1000);
      } catch (e: any) {
        setError(e?.response?.data?.detail || 'Migration failed');
        setStepIndex(-1);
      }
    };
    run();
  }, [planId]);

  return (
    <div style={{ maxWidth: 600 }}>
      <h1 style={{ marginBottom: 8 }}>Migration Execution</h1>
      <p className="text-muted" style={{ marginBottom: 32 }}>Plan: {planId?.slice(0, 8)}</p>

      <div className="card">
        <div className="timeline">
          {STEPS.map((step, i) => {
            const done = i < stepIndex && stepIndex !== -1;
            const running = i === stepIndex && stepIndex !== STEPS.length && stepIndex !== -1;
            const failed = stepIndex === -1 && i === stepIndex;
            const cls = done ? 'done' : running ? 'running' : failed ? 'failed' : 'pending';
            return (
              <div className="timeline-item" key={step}>
                <div className={`timeline-dot ${cls}`}>
                  {done ? '✓' : running ? '…' : i + 1}
                </div>
                <div style={{ paddingTop: 2 }}>
                  <p style={{ fontWeight: done ? 400 : 600, color: done ? 'var(--color-text-muted)' : running ? 'var(--color-accent-2)' : 'var(--color-text-muted)' }}>
                    {step}
                  </p>
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
            <span className="status-icon">✅</span>
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
