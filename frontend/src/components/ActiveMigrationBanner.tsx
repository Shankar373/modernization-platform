import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

export interface ActiveMigrationInfo {
  projectId: string;
  workspacePath: string;
  stage: string;
  stepNumber: number;
  stepTitle: string;
  stepIcon: string;
  timestamp: number;
}

export default function ActiveMigrationBanner() {
  const location = useLocation();
  const navigate = useNavigate();
  const [active, setActive] = useState<ActiveMigrationInfo | null>(null);

  const loadActive = () => {
    try {
      const raw = localStorage.getItem('active_migration');
      if (raw) {
        const parsed = JSON.parse(raw);
        // Expiry check: if older than 24 hours, clear it
        if (Date.now() - (parsed.timestamp || 0) < 24 * 60 * 60 * 1000) {
          setActive(parsed);
          return;
        } else {
          localStorage.removeItem('active_migration');
        }
      }
    } catch {
      // ignore
    }
    setActive(null);
  };

  useEffect(() => {
    loadActive();

    const handleUpdate = () => loadActive();
    window.addEventListener('active_migration_updated', handleUpdate);
    window.addEventListener('storage', handleUpdate);

    // Poll every 3 seconds for active status updates
    const interval = setInterval(loadActive, 3000);

    return () => {
      window.removeEventListener('active_migration_updated', handleUpdate);
      window.removeEventListener('storage', handleUpdate);
      clearInterval(interval);
    };
  }, []);

  // Do not show banner if user is currently on the active pipeline page
  if (!active || location.pathname === '/' || location.pathname.startsWith(`/pipeline/`)) {
    return null;
  }

  const handleResume = () => {
    navigate(`/pipeline/${active.projectId}?wp=${encodeURIComponent(active.workspacePath)}&stage=${active.stage}`);
  };

  const handleDismiss = (e: React.MouseEvent) => {
    e.stopPropagation();
    localStorage.removeItem('active_migration');
    setActive(null);
    window.dispatchEvent(new Event('active_migration_updated'));
  };

  return (
    <div
      onClick={handleResume}
      style={{
        margin: '12px 24px 0 24px',
        padding: '10px 18px',
        background: 'linear-gradient(90deg, rgba(99, 102, 241, 0.18), rgba(16, 185, 129, 0.15))',
        border: '1px solid rgba(99, 102, 241, 0.4)',
        borderRadius: 10,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        cursor: 'pointer',
        boxShadow: '0 4px 16px rgba(0, 0, 0, 0.25)',
        backdropFilter: 'blur(8px)',
        transition: 'all 0.2s ease',
        animation: 'fadeInDown 0.3s ease-out'
      }}
      className="active-migration-banner hover-glow"
      title="Click to resume your migration"
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {/* Pulsing live dot */}
        <span style={{ position: 'relative', display: 'flex', width: 10, height: 10 }}>
          <span
            style={{
              position: 'absolute',
              width: '100%',
              height: '100%',
              borderRadius: '50%',
              background: '#10b981',
              opacity: 0.75,
              animation: 'ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite'
            }}
          />
          <span
            style={{
              position: 'relative',
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: '#10b981'
            }}
          />
        </span>

        <span style={{ fontSize: 16 }}>{active.stepIcon || '🚀'}</span>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <strong style={{ color: '#fff', fontSize: 13, letterSpacing: '0.02em' }}>
            Active Migration in Progress:
          </strong>
          <span style={{ color: 'var(--color-text)', fontSize: 13 }}>
            Step {active.stepNumber}/17 — {active.stepTitle}
          </span>
          <span
            style={{
              fontSize: 11,
              padding: '1px 6px',
              borderRadius: 4,
              background: 'rgba(255, 255, 255, 0.1)',
              color: 'var(--color-text-muted)',
              fontWeight: 600
            }}
          >
            📁 {active.workspacePath ? active.workspacePath.split(/[\\/]/).filter(Boolean).pop()?.replace(/^systema_[a-f0-9]+_/, '') : active.projectId.slice(0, 8)}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          onClick={handleResume}
          className="btn btn-primary"
          style={{
            padding: '5px 14px',
            fontSize: 12,
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 6
          }}
        >
          Resume Pipeline ➔
        </button>

        <button
          onClick={handleDismiss}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--color-text-muted)',
            cursor: 'pointer',
            fontSize: 16,
            padding: '2px 6px',
            borderRadius: 4,
            lineHeight: 1
          }}
          title="Dismiss banner"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
