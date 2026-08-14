import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import {
  analyzeRepo,
  planDependencyAnalysis,
  applyDependencyUpdates,
  getRecipeRecommendations,
  analyzeRecipeConflicts,
  generateMigrationPlan,
  executeRecipes,
  createGitCheckpoint,
  downloadCheckpointZip,
} from '../api/client';
import type {
  TechnologyProfile,
  DependencyAnalysisResult,
  Recipe,
  RecipeAnalysisResult,
  MigrationPlan,
  GitCheckpointResult,
} from '../types';

type StageKey =
  | 'discovery'
  | 'profile'
  | 'dep-detection'
  | 'version-detection'
  | 'dep-review'
  | 'dep-applying'
  | 'ai-recommending'
  | 'recipe-selection'
  | 'recipe-analyzing'
  | 'conflict-resolution'
  | 'plan'
  | 'checkpointing'
  | 'executing-recipes'
  | 'done';

interface Step {
  key: StageKey;
  number: number;
  title: string;
  icon: string;
  auto: boolean;
}

const STEPS: Step[] = [
  { key: 'discovery',          number: 1,  title: 'Application Discovery',     icon: '🔍', auto: true  },
  { key: 'profile',            number: 2,  title: 'Project Profile',           icon: '📋', auto: true  },
  { key: 'dep-detection',      number: 3,  title: 'Dependency Detection',      icon: '🧩', auto: true  },
  { key: 'version-detection',  number: 4,  title: 'Version Detection',         icon: '🌐', auto: true  },
  { key: 'dep-review',         number: 5,  title: 'Dependency Update Review',  icon: '📝', auto: false },
  { key: 'dep-applying',       number: 6,  title: 'Apply Dependency Updates',  icon: '⚙️', auto: true  },
  { key: 'ai-recommending',    number: 7,  title: 'AI Recommendations',        icon: '🤖', auto: true  },
  { key: 'recipe-selection',   number: 8,  title: 'Recipe Selection',          icon: '🍳', auto: false },
  { key: 'recipe-analyzing',   number: 9,  title: 'Recipe Analysis',           icon: '🔬', auto: true  },
  { key: 'conflict-resolution',number: 10, title: 'Conflict Resolution',       icon: '⚡', auto: false },
  { key: 'plan',               number: 11, title: 'Migration Plan',            icon: '🗺️', auto: false },
  { key: 'checkpointing',      number: 12, title: 'Git Checkpoint',            icon: '🎯', auto: true  },
  { key: 'executing-recipes',  number: 13, title: 'Execute Recipes',           icon: '🛠️', auto: true  },
  { key: 'done',               number: 13, title: 'Execute Recipes',           icon: '✅', auto: true  },
];

const DISPLAY_STEPS = STEPS.filter(s => s.key !== 'done');

const LANG_COLOR: Record<string, string> = {
  python: '#3b82f6', java: '#f59e0b', javascript: '#eab308',
  typescript: '#06b6d4', csharp: '#a855f7', go: '#22d3ee', dotnet: '#a855f7',
};

const CATEGORY_COLOR: Record<string, string> = {
  upgrade: '#6366f1', style: '#10b981', security: '#ef4444', performance: '#f59e0b',
};

const COMPLEXITY_COLOR: Record<string, string> = {
  low: '#10b981', medium: '#f59e0b', high: '#ef4444',
};

const RISK_COLOR: Record<string, string> = {
  LOW: '#10b981', MEDIUM: '#f59e0b', HIGH: '#ef4444',
};

function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', padding: '2px 8px', borderRadius: 99,
      fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
      background: color + '22', color, border: `1px solid ${color}44`,
      whiteSpace: 'nowrap', flexShrink: 0,
    }}>{text}</span>
  );
}

function Spinner({ size = 20 }: { size?: number }) {
  return <span className="spinner" style={{ width: size, height: size, display: 'inline-block' }} />;
}

function InfoCard({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="card animate-fade-in" style={{ textAlign: 'center', padding: '20px 16px' }}>
      <div style={{ fontSize: 28, marginBottom: 8 }}>{icon}</div>
      <div style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>{value}</div>
      <div className="text-muted text-sm">{label}</div>
    </div>
  );
}

// ── Step Content Components ────────────────────────────────────────────────────

function DiscoveryStep({ profile, onContinue }: { profile: TechnologyProfile | null; onContinue: () => void }) {
  if (!profile) return <div style={{ textAlign: 'center', padding: 60 }}><Spinner size={40} /><p style={{ marginTop: 16, color: 'var(--text-muted)' }}>Analysing application stack…</p></div>;

  return (
    <div className="animate-fade-up">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 16, marginBottom: 28 }}>
        <InfoCard icon="🗣️" label="Languages" value={profile.languages.length.toString()} />
        <InfoCard icon="🏗️" label="Frameworks" value={profile.frameworks.length.toString()} />
        <InfoCard icon="🔨" label="Build Systems" value={profile.build_systems.length.toString()} />
        <InfoCard icon="🧪" label="Test Frameworks" value={profile.test_frameworks.length.toString()} />
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 16, fontSize: 13, fontWeight: 700, color: 'var(--color-accent)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>DETECTED LANGUAGES</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {profile.languages.map(l => (
            <div key={l.name} style={{ padding: '12px 16px', borderRadius: 8, background: 'var(--color-surface-2)', border: '1px solid var(--color-border)' }}>
              <div className="flex justify-between items-center" style={{ marginBottom: 8 }}>
                <span style={{ fontWeight: 700, fontSize: 14 }}>{l.name}</span>
                {l.version && <Badge text={l.version} color={LANG_COLOR[l.name.toLowerCase()] || '#6366f1'} />}
              </div>
              <div className="confidence-bar">
                <div className="confidence-fill" style={{ width: `${l.confidence * 100}%`, background: LANG_COLOR[l.name.toLowerCase()] || '#6366f1' }} />
              </div>
            </div>
          ))}
          {profile.languages.length === 0 && <p className="text-muted">No languages detected</p>}
        </div>
      </div>

      {profile.frameworks.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h3 style={{ marginBottom: 16, fontSize: 13, fontWeight: 700, color: 'var(--color-accent)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>DETECTED FRAMEWORKS</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {profile.frameworks.map(f => (
              <div key={f.name} style={{ padding: '8px 16px', borderRadius: 8, background: 'rgba(255,255,255,0.04)', border: '1px solid var(--color-border)' }}>
                <span style={{ fontWeight: 600 }}>{f.name}</span>
                {f.version && <span style={{ marginLeft: 8, color: 'var(--color-text-muted)', fontSize: 13 }}>v{f.version}</span>}
                <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--color-text-muted)' }}>({f.language})</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}>
        <button className="btn btn-primary" onClick={onContinue}>
          Proceed to Project Profile →
        </button>
      </div>
    </div>
  );
}

function ProfileStep({ profile, onContinue }: { profile: TechnologyProfile | null; onContinue: () => void }) {
  if (!profile) return null;
  const complexity = profile.languages.length + profile.frameworks.length * 1.5 + profile.build_systems.length;
  const complexityLabel = complexity < 3 ? 'Simple' : complexity < 7 ? 'Moderate' : 'Complex';
  const complexityColor = complexity < 3 ? '#10b981' : complexity < 7 ? '#f59e0b' : '#ef4444';

  return (
    <div className="animate-fade-up">
      <div className="card" style={{ marginBottom: 20, padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Project Technology Profile</h2>
            <p className="text-muted text-sm" style={{ fontFamily: 'monospace' }}>{profile.workspace_path}</p>
          </div>
          <Badge text={complexityLabel} color={complexityColor} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          <ProfileSection title="Languages" items={profile.languages.map(l => `${l.name}${l.version ? ` ${l.version}` : ''}`)} color="#6366f1" />
          <ProfileSection title="Frameworks" items={profile.frameworks.map(f => `${f.name}${f.version ? ` v${f.version}` : ''}`)} color="#06b6d4" />
          <ProfileSection title="Build Systems" items={profile.build_systems} color="#10b981" />
          <ProfileSection title="Test Frameworks" items={profile.test_frameworks} color="#f59e0b" />
        </div>
      </div>

      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}>
        <button className="btn btn-primary" onClick={onContinue}>
          Proceed to Dependency Detection →
        </button>
      </div>
    </div>
  );
}

function ProfileSection({ title, items, color }: { title: string; items: string[]; color: string }) {
  return (
    <div style={{ padding: 16, borderRadius: 8, background: color + '0d', border: `1px solid ${color}22` }}>
      <h4 style={{ fontSize: 12, fontWeight: 600, color, marginBottom: 10, textTransform: 'uppercase' }}>{title}</h4>
      {items.length === 0
        ? <p className="text-muted text-sm">None detected</p>
        : items.map(i => <div key={i} style={{ fontSize: 13, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ color, fontSize: 10 }}>●</span>{i}</div>)
      }
    </div>
  );
}

function DepDetectionStep({ depResult, onContinue }: { depResult: DependencyAnalysisResult | null; onContinue: () => void }) {
  if (!depResult) {
    return <div style={{ textAlign: 'center', padding: 60 }}><Spinner size={40} /><p style={{ marginTop: 16, color: 'var(--text-muted)' }}>Scanning dependency files…</p></div>;
  }
  return (
    <div className="animate-fade-up">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        <InfoCard icon="📦" label="Files Found" value={depResult.dependency_files.length.toString()} />
        <InfoCard icon="🔗" label="Dependencies" value={depResult.dependencies.length.toString()} />
        <InfoCard icon="🔒" label="Lockfiles" value={depResult.dependency_files.filter(f => f.is_lockfile).length.toString()} />
        <InfoCard icon="⚡" label="Ecosystems" value={[...new Set(depResult.dependency_files.map(f => f.ecosystem))].length.toString()} />
      </div>
      <div className="card">
        <h3 style={{ marginBottom: 16, fontSize: 13, fontWeight: 700, color: 'var(--color-accent)', textTransform: 'uppercase' }}>DETECTED DEPENDENCY FILES</h3>
        {depResult.dependency_files.map(f => (
          <div key={f.path} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 18 }}>{f.ecosystem === 'python' ? '🐍' : f.ecosystem === 'node' ? '📦' : f.ecosystem === 'java' ? '☕' : f.ecosystem === 'dotnet' ? '🔷' : '🔧'}</span>
              <span style={{ fontFamily: 'monospace', fontSize: 13 }}>{f.path}</span>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <Badge text={f.ecosystem} color={LANG_COLOR[f.ecosystem] || '#6366f1'} />
              {f.is_lockfile && <Badge text="lockfile" color="#6b7280" />}
            </div>
          </div>
        ))}
        {depResult.dependency_files.length === 0 && <p className="text-muted">No dependency files found in workspace.</p>}
      </div>
      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}>
        <button className="btn btn-primary" onClick={onContinue}>
          Proceed to Version Detection →
        </button>
      </div>
    </div>
  );
}

function VersionDetectionStep({ depResult, onContinue }: { depResult: DependencyAnalysisResult | null; onContinue: () => void }) {
  if (!depResult) return null;
  const statusConfig = {
    UP_TO_DATE:         { icon: '✓', color: '#10b981', label: 'Up to date' },
    UPDATE_AVAILABLE:   { icon: '↑', color: '#6366f1', label: 'Update available' },
    CONSTRAINT_BLOCKED: { icon: '⛔', color: '#f59e0b', label: 'Constraint blocked' },
    LOOKUP_FAILED:      { icon: '?', color: '#6b7280', label: 'Lookup failed' },
    INVALID_VERSION:    { icon: '!', color: '#ef4444', label: 'Invalid version' },
  };

  return (
    <div className="animate-fade-up">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        <InfoCard icon="✓" label="Up to date" value={depResult.up_to_date.length.toString()} />
        <InfoCard icon="↑" label="Update available" value={depResult.outdated.length.toString()} />
        <InfoCard icon="⛔" label="Blocked" value={depResult.constraint_blocked.length.toString()} />
      </div>
      <div className="card">
        <h3 style={{ marginBottom: 16, fontSize: 13, fontWeight: 700, color: 'var(--color-accent)', textTransform: 'uppercase' }}>ALL DEPENDENCIES ({depResult.dependencies.length})</h3>
        <div style={{ maxHeight: 380, overflowY: 'auto' }}>
          {depResult.dependencies.slice(0, 50).map(d => {
            const cfg = statusConfig[d.status as keyof typeof statusConfig] || statusConfig.LOOKUP_FAILED;
            return (
              <div key={`${d.name}-${d.source_file}`} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0', borderBottom: '1px solid rgba(0,0,0,0.04)', fontSize: 13 }}>
                <span style={{ color: cfg.color, width: 16, textAlign: 'center', fontWeight: 700 }}>{cfg.icon}</span>
                <span style={{ flex: 1, fontFamily: 'monospace' }}>{d.name}</span>
                <span style={{ color: 'var(--color-text-muted)', width: 90, textAlign: 'right', fontFamily: 'monospace' }}>{d.current_version || 'unconstrained'}</span>
                <span style={{ color: 'var(--color-text-muted)' }}>→</span>
                <span style={{ color: d.status === 'UPDATE_AVAILABLE' ? '#6366f1' : 'var(--color-text-muted)', width: 90, fontFamily: 'monospace' }}>{d.latest_stable_version || '—'}</span>
              </div>
            );
          })}
          {depResult.dependencies.length > 50 && <p className="text-muted text-sm" style={{ marginTop: 8 }}>…and {depResult.dependencies.length - 50} more</p>}
        </div>
      </div>
      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}>
        <button className="btn btn-primary" onClick={onContinue}>
          Proceed to Dependency Review →
        </button>
      </div>
    </div>
  );
}

function DepReviewStep({
  depResult,
  approvedIds,
  setApprovedIds,
  onContinue,
  onSkip,
}: {
  depResult: DependencyAnalysisResult | null;
  approvedIds: Set<string>;
  setApprovedIds: (s: Set<string>) => void;
  onContinue: () => void;
  onSkip: () => void;
}) {
  if (!depResult) return null;
  const updates = depResult.proposed_updates || [];

  const toggle = (key: string) => {
    const next = new Set(approvedIds);
    next.has(key) ? next.delete(key) : next.add(key);
    setApprovedIds(next);
  };

  const allSelected = updates.every(u => approvedIds.has(u.dependency_name + u.source_file));
  const toggleAll = () => {
    if (allSelected) setApprovedIds(new Set());
    else setApprovedIds(new Set(updates.map(u => u.dependency_name + u.source_file)));
  };

  return (
    <div className="animate-fade-up">
      {updates.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>✅</div>
          <h3 style={{ marginBottom: 8 }}>All Dependencies Up to Date</h3>
          <p className="text-muted">No updates required. Proceeding to next step.</p>
          <div style={{ marginTop: 24 }}>
            <button className="btn btn-primary" onClick={onSkip}>Continue →</button>
          </div>
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <div>
              <h3 style={{ marginBottom: 4 }}>{updates.length} Proposed Update{updates.length !== 1 ? 's' : ''}</h3>
              <p className="text-muted text-sm">Select which updates to apply to your dependency files.</p>
            </div>
            <button className="btn btn-ghost" style={{ fontSize: 13 }} onClick={toggleAll}>
              {allSelected ? 'Deselect All' : 'Select All'}
            </button>
          </div>
          <div className="card" style={{ marginBottom: 20 }}>
            {updates.map(u => {
              const key = u.dependency_name + u.source_file;
              const checked = approvedIds.has(key);
              return (
                <div key={key} onClick={() => toggle(key)} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 0', borderBottom: '1px solid rgba(0,0,0,0.06)', cursor: 'pointer', transition: 'opacity 0.15s', flexWrap: 'nowrap' }}>
                  <div style={{ width: 20, height: 20, borderRadius: 4, border: `2px solid ${checked ? 'var(--color-accent)' : 'rgba(0,0,0,0.2)'}`, background: checked ? 'var(--color-accent)' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    {checked && <span style={{ color: '#fff', fontSize: 12, fontWeight: 700 }}>✓</span>}
                  </div>
                  <div style={{ flex: 1, minWidth: 0, display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '4px 10px' }}>
                    <span style={{ fontWeight: 600, fontFamily: 'monospace', whiteSpace: 'nowrap' }}>{u.dependency_name}</span>
                    <span className="text-muted text-sm" style={{ wordBreak: 'break-all' }}>{u.source_file}</span>
                  </div>
                  <span style={{ color: 'var(--color-text-muted)', fontFamily: 'monospace', fontSize: 13, flexShrink: 0 }}>{u.current_version || 'unconstrained'}</span>
                  <span style={{ color: 'var(--color-text-muted)', flexShrink: 0 }}>→</span>
                  <span style={{ color: 'var(--color-accent)', fontFamily: 'monospace', fontSize: 13, fontWeight: 600, flexShrink: 0 }}>{u.proposed_version}</span>
                </div>
              );
            })}
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <button className="btn btn-primary" onClick={onContinue} disabled={approvedIds.size === 0}>
              ⚙️ Apply {approvedIds.size} Update{approvedIds.size !== 1 ? 's' : ''} →
            </button>
            <button className="btn btn-ghost" onClick={onSkip}>Skip (no updates)</button>
          </div>
        </>
      )}
    </div>
  );
}

function DepApplyingStep({ applyResult, onContinue }: { applyResult: DependencyAnalysisResult | null; onContinue: () => void }) {
  if (!applyResult) {
    return <div style={{ textAlign: 'center', padding: 60 }}><Spinner size={40} /><p style={{ marginTop: 16, color: 'var(--text-muted)' }}>Applying dependency updates…</p></div>;
  }
  return (
    <div className="animate-fade-up">
      <div className="card" style={{ marginBottom: 20, padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
          <div style={{ fontSize: 40 }}>{applyResult.validation_status === 'PASSED' ? '✅' : '⚠️'}</div>
          <div>
            <h3 style={{ marginBottom: 4 }}>{applyResult.changed_files.length} Files Updated</h3>
            <p className="text-muted text-sm">Validation: <Badge text={applyResult.validation_status} color={applyResult.validation_status === 'PASSED' ? '#10b981' : '#f59e0b'} /></p>
          </div>
        </div>
        {applyResult.changed_files.length > 0 && (
          <div>
            <h4 style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 12 }}>CHANGED FILES</h4>
            {applyResult.changed_files.map(f => (
              <div key={f} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderBottom: '1px solid rgba(0,0,0,0.06)', fontFamily: 'monospace', fontSize: 13 }}>
                <span style={{ color: '#10b981' }}>✓</span> {f}
              </div>
            ))}
          </div>
        )}
        {applyResult.validation_errors.length > 0 && (
          <div style={{ marginTop: 16, padding: 12, background: 'rgba(239,68,68,0.1)', borderRadius: 8, border: '1px solid rgba(239,68,68,0.3)' }}>
            <h4 style={{ color: '#fca5a5', fontSize: 13, marginBottom: 8 }}>Validation Issues</h4>
            {applyResult.validation_errors.map((e, i) => <div key={i} style={{ color: '#fca5a5', fontSize: 12 }}>{e}</div>)}
          </div>
        )}
      </div>
      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}>
        <button className="btn btn-primary" onClick={onContinue}>
          Proceed to AI Recommendations →
        </button>
      </div>
    </div>
  );
}

function AIRecommendingStep({ recommendations, onContinue }: { recommendations: Recipe[] | null; onContinue: () => void }) {
  if (!recommendations) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <div style={{ fontSize: 48, marginBottom: 20 }}>🤖</div>
        <Spinner size={36} />
        <p style={{ marginTop: 16, color: 'var(--text-muted)' }}>Analysing project profile and generating recipe recommendations…</p>
      </div>
    );
  }

  const recommended = recommendations.filter(r => r.recommended);
  const others = recommendations.filter(r => !r.recommended).slice(0, 5);

  return (
    <div className="animate-fade-up">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        <InfoCard icon="🏆" label="Recommended" value={recommended.length.toString()} />
        <InfoCard icon="📋" label="Available" value={recommendations.length.toString()} />
        <InfoCard icon="🔐" label="Security" value={recommendations.filter(r => r.category === 'security').length.toString()} />
      </div>
      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 16, fontSize: 14, fontWeight: 700, color: 'var(--color-accent)' }}>⭐ TOP RECOMMENDATIONS</h3>
        {recommended.slice(0, 8).map(r => (
          <RecipeRow key={r.id} recipe={r} highlighted />
        ))}
        {recommended.length === 0 && <p className="text-muted">No specific recommendations for this project.</p>}
      </div>
      {others.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h3 style={{ marginBottom: 16, fontSize: 14, fontWeight: 600, color: 'var(--color-text-muted)' }}>OTHER APPLICABLE RECIPES</h3>
          {others.map(r => <RecipeRow key={r.id} recipe={r} />)}
        </div>
      )}
      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}>
        <button className="btn btn-primary" onClick={onContinue}>
          Proceed to Recipe Selection →
        </button>
      </div>
    </div>
  );
}

function RecipeRow({ recipe, highlighted = false, selected, onToggle }: { recipe: Recipe; highlighted?: boolean; selected?: boolean; onToggle?: () => void }) {
  return (
    <div
      onClick={onToggle}
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 14,
        padding: '12px 0', borderBottom: '1px solid rgba(0,0,0,0.06)',
        cursor: onToggle ? 'pointer' : 'default',
        opacity: 1,
      }}
    >
      {onToggle && (
        <div style={{ width: 20, height: 20, borderRadius: 4, border: `2px solid ${selected ? 'var(--color-accent)' : 'rgba(0,0,0,0.2)'}`, background: selected ? 'var(--color-accent)' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2 }}>
          {selected && <span style={{ color: '#fff', fontSize: 12, fontWeight: 700 }}>✓</span>}
        </div>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, fontSize: 14, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>{recipe.name}</span>
          {highlighted && recipe.recommended && <Badge text="recommended" color="var(--color-accent)" />}
          <Badge text={recipe.category} color={CATEGORY_COLOR[recipe.category as keyof typeof CATEGORY_COLOR] || '#6366f1'} />
          <Badge text={recipe.complexity} color={COMPLEXITY_COLOR[recipe.complexity as keyof typeof COMPLEXITY_COLOR] || '#6366f1'} />
        </div>
        <p className="text-muted text-sm" style={{ lineHeight: 1.5 }}>{recipe.description}</p>
        {recipe.requires.length > 0 && <p style={{ fontSize: 11, color: '#f59e0b', marginTop: 4 }}>Requires: {recipe.requires.join(', ')}</p>}
      </div>
    </div>
  );
}

function RecipeSelectionStep({
  recommendations,
  selectedIds,
  setSelectedIds,
  onContinue,
}: {
  recommendations: Recipe[];
  selectedIds: Set<string>;
  setSelectedIds: (s: Set<string>) => void;
  onContinue: () => void;
}) {
  const [filterText, setFilterText] = useState('');
  const toggle = (id: string) => {
    const next = new Set(selectedIds);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelectedIds(next);
  };

  useEffect(() => {
    const recs = recommendations.filter(r => r.recommended).map(r => r.id);
    if (recs.length > 0 && selectedIds.size === 0) {
      setSelectedIds(new Set(recs));
    }
  }, [recommendations]);

  const filtered = recommendations.filter(r =>
    r.name.toLowerCase().includes(filterText.toLowerCase()) ||
    r.description.toLowerCase().includes(filterText.toLowerCase()) ||
    r.language.toLowerCase().includes(filterText.toLowerCase())
  );

  const grouped = filtered.reduce<Record<string, Recipe[]>>((acc, r) => {
    const key = r.language === 'all' ? 'General' : r.language.charAt(0).toUpperCase() + r.language.slice(1);
    if (!acc[key]) acc[key] = [];
    acc[key].push(r);
    return acc;
  }, {});

  const toggleAll = () => {
    const allSelected = recommendations.every(r => selectedIds.has(r.id));
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(recommendations.map(r => r.id)));
    }
  };

  const allSelected = recommendations.length > 0 && recommendations.every(r => selectedIds.has(r.id));

  return (
    <div className="animate-fade-up">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h3 style={{ marginBottom: 4 }}>Select Migration Recipes</h3>
          <p className="text-muted text-sm">{selectedIds.size} recipe{selectedIds.size !== 1 ? 's' : ''} selected.</p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button className="btn btn-ghost" style={{ fontSize: 13 }} onClick={toggleAll}>
            {allSelected ? 'Deselect All' : 'Select All'}
          </button>
          <button className="btn btn-primary" onClick={onContinue} disabled={selectedIds.size === 0}>
            Analyse {selectedIds.size} Recipe{selectedIds.size !== 1 ? 's' : ''} →
          </button>
        </div>
      </div>

      <div style={{ marginBottom: 20 }}>
        <input
          className="input"
          placeholder="Filter recipes by name, description, or language..."
          value={filterText}
          onChange={e => setFilterText(e.target.value)}
        />
      </div>

      {Object.entries(grouped).map(([group, recipes]) => (
        <div key={group} className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ marginBottom: 16, fontSize: 13, fontWeight: 700, color: 'var(--color-accent)', textTransform: 'uppercase' }}>{group.toUpperCase()} ({recipes.length})</h3>
          {recipes.map(r => (
            <RecipeRow key={r.id} recipe={r} selected={selectedIds.has(r.id)} onToggle={() => toggle(r.id)} />
          ))}
        </div>
      ))}
      {filtered.length === 0 && <p className="text-muted text-center" style={{ padding: 24 }}>No recipes match your filter.</p>}
    </div>
  );
}

function RecipeAnalyzingStep({ analysis, onContinue }: { analysis: RecipeAnalysisResult | null; onContinue: () => void }) {
  if (!analysis) {
    return <div style={{ textAlign: 'center', padding: 60 }}><Spinner size={40} /><p style={{ marginTop: 16, color: 'var(--text-muted)' }}>Analysing recipe dependencies and ordering…</p></div>;
  }
  return (
    <div className="animate-fade-up">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        <InfoCard icon="🍳" label="Recipes" value={analysis.ordered_recipes.length.toString()} />
        <InfoCard icon="🔀" label="Phases" value={analysis.execution_phases.length.toString()} />
        <InfoCard icon="⚡" label="Conflicts" value={analysis.conflicts.length.toString()} />
      </div>

      {analysis.auto_added_recipes.length > 0 && (
        <div style={{ padding: '12px 16px', borderRadius: 8, background: 'rgba(29,127,138,0.1)', border: '1px solid rgba(29,127,138,0.3)', marginBottom: 20 }}>
          <p style={{ fontSize: 13, color: 'var(--color-accent)' }}>
            <strong>Auto-added required recipes:</strong> {analysis.auto_added_recipes.map(r => r.name).join(', ')}
          </p>
        </div>
      )}

      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 16, fontSize: 14, fontWeight: 600, color: 'var(--color-accent-2)' }}>EXECUTION ORDER</h3>
        {analysis.execution_phases.map(phase => (
          <div key={phase.phase} style={{ marginBottom: 16 }}>
            <h4 style={{ fontSize: 12, color: 'var(--color-accent)', marginBottom: 8, textTransform: 'uppercase' }}>Phase {phase.phase}</h4>
            {phase.recipes.map(r => (
              <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid rgba(0,0,0,0.04)', fontSize: 13, flexWrap: 'wrap', minWidth: 0 }}>
                <span style={{ color: 'var(--color-accent)', fontSize: 10, flexShrink: 0 }}>●</span>
                <span style={{ fontWeight: 600, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.name}</span>
                <Badge text={r.category} color={CATEGORY_COLOR[r.category as keyof typeof CATEGORY_COLOR] || '#6366f1'} />
              </div>
            ))}
          </div>
        ))}
      </div>

      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}>
        <button className="btn btn-primary" onClick={onContinue}>
          Proceed to Conflict Resolution →
        </button>
      </div>
    </div>
  );
}

function ConflictResolutionStep({
  analysis,
  onContinue,
  onSkip,
}: {
  analysis: RecipeAnalysisResult | null;
  onContinue: () => void;
  onSkip: () => void;
}) {
  if (!analysis) return null;

  if (!analysis.has_conflicts) {
    return (
      <div className="animate-fade-up">
        <div className="card" style={{ textAlign: 'center', padding: '32px 48px', marginBottom: 20 }}>
          <div style={{ fontSize: 44, marginBottom: 12 }}>✅</div>
          <h3 style={{ marginBottom: 8 }}>No Conflicts Detected</h3>
          <p className="text-muted" style={{ marginBottom: 24 }}>All selected recipes passed executor verification and are compatible.</p>
          {/* Executor-verified recipe summary table */}
          <div style={{ textAlign: 'left', background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: 10, padding: '16px 20px' }}>
            <p style={{ fontSize: 12, fontWeight: 700, color: '#10b981', textTransform: 'uppercase', marginBottom: 12, letterSpacing: '0.05em' }}>Executor-Verified Recipes ({analysis.ordered_recipes.length})</p>
            <div style={{ display: 'grid', gap: 6 }}>
              {analysis.ordered_recipes.map((r, i) => (
                <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, flexWrap: 'wrap' }}>
                  <span style={{ color: '#10b981', fontWeight: 700, minWidth: 18 }}>{i + 1}.</span>
                  <span style={{ fontWeight: 600, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.name}</span>
                  <Badge text={r.category} color={CATEGORY_COLOR[r.category as keyof typeof CATEGORY_COLOR] || '#6366f1'} />
                  <Badge text="✓ executable" color="#10b981" />
                </div>
              ))}
            </div>
          </div>
        </div>
        <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}>
          <button className="btn btn-primary" onClick={onContinue}>
            Proceed to Migration Plan →
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-up">
      <div className="alert alert-warning" style={{ marginBottom: 20 }}>
        <span>⚠️</span>
        <div style={{ fontWeight: 600 }}>{analysis.conflicts.length} conflict{analysis.conflicts.length !== 1 ? 's' : ''} detected in recipe selection</div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        {analysis.conflicts.map((c, i) => (
          <div key={i} style={{ padding: '16px 0', borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <Badge text={c.severity} color={c.severity === 'ERROR' ? '#ef4444' : '#f59e0b'} />
              <span style={{ fontWeight: 600, fontFamily: 'monospace', fontSize: 13 }}>{c.recipe_a}</span>
              <span style={{ color: 'var(--color-text-muted)' }}>↔</span>
              <span style={{ fontWeight: 600, fontFamily: 'monospace', fontSize: 13 }}>{c.recipe_b}</span>
            </div>
            <p className="text-muted text-sm" style={{ marginBottom: 6 }}>{c.reason}</p>
            <p style={{ fontSize: 13, color: 'var(--color-accent)' }}>Resolution: {c.resolution}</p>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 12 }}>
        <button className="btn btn-ghost" onClick={onSkip}>Proceed Anyway →</button>
        <button className="btn btn-primary" onClick={onContinue}>Resolve & Continue →</button>
      </div>
    </div>
  );
}

function PlanStep({ plan, onContinue }: { plan: MigrationPlan | null; onContinue: () => void }) {
  if (!plan) {
    return <div style={{ textAlign: 'center', padding: 60 }}><Spinner size={40} /><p style={{ marginTop: 16, color: 'var(--text-muted)' }}>Generating migration plan…</p></div>;
  }
  return (
    <div className="animate-fade-up">
      <div className="card" style={{ marginBottom: 20, padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <h2 style={{ marginBottom: 4 }}>Migration Plan</h2>
            <p className="text-muted text-sm">{plan.summary}</p>
          </div>
          <Badge text={`${plan.risk_level} RISK`} color={RISK_COLOR[plan.risk_level as keyof typeof RISK_COLOR] || '#6366f1'} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
          <InfoCard icon="🍳" label="Recipes" value={plan.selected_recipes.length.toString()} />
          <InfoCard icon="🔀" label="Phases" value={plan.phases.length.toString()} />
          <InfoCard icon="📦" label="Dep Updates" value={plan.dep_updates_count.toString()} />
          <InfoCard icon="📁" label="Est. Files" value={`~${plan.estimated_files_changed}`} />
        </div>

        <div style={{ padding: 16, background: 'rgba(29,127,138,0.06)', borderRadius: 8, border: '1px solid rgba(29,127,138,0.2)', marginBottom: 20 }}>
          <h4 style={{ fontSize: 12, color: 'var(--color-accent)', marginBottom: 8, textTransform: 'uppercase' }}>Git Checkpoint Message</h4>
          <code style={{ fontSize: 13, color: 'var(--color-accent-2)' }}>{plan.git_checkpoint_message}</code>
        </div>

        {plan.phases.map(phase => (
          <div key={phase.phase} style={{ marginBottom: 16 }}>
            <h4 style={{ fontSize: 12, color: 'var(--color-text-muted)', textTransform: 'uppercase', marginBottom: 10 }}>Phase {phase.phase}</h4>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {phase.recipes.map(r => (
                <div key={r.id} style={{ padding: '6px 14px', borderRadius: 6, background: 'rgba(0,0,0,0.03)', border: '1px solid var(--color-border)', fontSize: 13 }}>
                  {r.name}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 12 }}>
        <button className="btn btn-primary" onClick={onContinue}>🎯 Create Git Checkpoint →</button>
      </div>
    </div>
  );
}

function CheckingStep({ label, result, error }: { label: string; result: unknown; error: string | null }) {
  if (error) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>⚠️</div>
        <h3 style={{ marginBottom: 12 }}>Step Failed</h3>
        <p style={{ color: '#fca5a5', marginBottom: 16 }}>{error}</p>
      </div>
    );
  }
  if (!result) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <div style={{ fontSize: 48, marginBottom: 20 }}>⚙️</div>
        <Spinner size={36} />
        <p style={{ marginTop: 16, color: 'var(--text-muted)' }}>{label}</p>
      </div>
    );
  }
  return (
    <div style={{ textAlign: 'center', padding: 60 }}>
      <div style={{ fontSize: 48, marginBottom: 20 }}>✅</div>
      <p style={{ marginTop: 16, color: 'var(--text-muted)' }}>Completed.</p>
    </div>
  );
}

function RecipeExecuteStep({ result, error }: { result: any; error: string | null }) {
  if (error) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>⚠️</div>
        <h3 style={{ marginBottom: 12 }}>Recipe Execution Failed</h3>
        <p style={{ color: '#fca5a5', marginBottom: 16 }}>{error}</p>
      </div>
    );
  }
  if (!result) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <div style={{ fontSize: 48, marginBottom: 20 }}>🛠️</div>
        <Spinner size={36} />
        <p style={{ marginTop: 16, color: 'var(--text-muted)' }}>Applying selected recipe transformations to your workspace…</p>
      </div>
    );
  }
  const executed = result.recipes_executed ?? 0;
  const files = result.files_changed ?? 0;
  const findings = result.findings_count ?? 0;
  return (
    <div className="animate-fade-up">
      <div style={{ padding: 24, borderRadius: 12, background: 'linear-gradient(135deg, rgba(16,185,129,0.12), rgba(29,127,138,0.1))', border: '1px solid rgba(16,185,129,0.25)', marginBottom: 24, textAlign: 'center' }}>
        <div style={{ fontSize: 56, marginBottom: 12 }}>🛠️</div>
        <h2 style={{ marginBottom: 8, fontSize: 22 }}>Recipe Transformations Applied</h2>
        <p className="text-muted">Code changes have been written to the workspace.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        <InfoCard icon="✅" label="Recipes Executed" value={executed.toString()} />
        <InfoCard icon="📝" label="Files Changed" value={files.toString()} />
        <InfoCard icon={findings > 0 ? '🔐' : '✅'} label="Security Findings" value={findings.toString()} />
      </div>

      {(result.recipes_not_implemented?.length > 0 || result.recipes_failed?.length > 0) && (
        <div style={{ padding: 12, background: 'rgba(239,68,68,0.08)', borderRadius: 8, marginBottom: 20, border: '1px solid rgba(239,68,68,0.25)' }}>
          <h4 style={{ color: '#fca5a5', fontSize: 13, marginBottom: 6 }}>Some recipes were not applied</h4>
          {result.recipes_not_implemented?.length > 0 && (
            <p className="text-muted text-sm" style={{ fontSize: 13 }}>No handler: {result.recipes_not_implemented.join(', ')}</p>
          )}
          {result.recipes_failed?.length > 0 && (
            <p className="text-muted text-sm" style={{ fontSize: 13 }}>Failed: {result.recipes_failed.join(', ')}</p>
          )}
        </div>
      )}

      {result.recipes?.map((r: any) => (
        <div className="card" style={{ marginBottom: 14 }} key={r.recipe_id}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>{r.recipe_name}</span>
            <Badge text={r.status} color={r.status === 'EXECUTED' ? '#10b981' : r.status === 'FAILED' ? '#ef4444' : '#f59e0b'} />
          </div>
          {r.changed_files?.length > 0 && (
            <div style={{ maxHeight: 160, overflowY: 'auto', border: '1px solid rgba(0,0,0,0.06)', borderRadius: 6 }}>
              {r.changed_files.map((c: any) => (
                <div key={c.file} style={{ padding: '6px 10px', fontFamily: 'monospace', fontSize: 12, borderBottom: '1px solid rgba(0,0,0,0.05)', color: '#10b981' }}>
                  {c.status === 'ADDED' ? '➕' : '✏️'} {c.file}
                </div>
              ))}
            </div>
          )}
          {r.findings?.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <p style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>Security Findings</p>
              {r.findings.map((f: any, i: number) => (
                <div key={i} style={{ display: 'flex', gap: 10, padding: '6px 0', fontSize: 13, alignItems: 'flex-start' }}>
                  <Badge text={f.severity} color={f.severity === 'CRITICAL' || f.severity === 'HIGH' ? '#ef4444' : '#f59e0b'} />
                  <div>
                    <span>{f.message}</span>
                    <div style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2 }}>{f.file}: {f.evidence}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {r.notes?.map((n: string) => (
            <p key={n} style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 6 }}>{n}</p>
          ))}
        </div>
      ))}

      <div style={{ padding: 16, borderRadius: 8, background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', marginBottom: 20 }}>
        <h4 style={{ color: '#10b981', marginBottom: 8, fontSize: 14 }}>✅ Recipe execution complete</h4>
        <p className="text-muted text-sm">
          {result.mode === 'dry-run' ? 'Dry-run preview — no files were modified.' : 'Transformations written to the workspace.'} Review the diffs below and then download the workspace.
        </p>
      </div>
    </div>
  );
}

function CheckpointStep({
  result,
  error,
  workspacePath,
  projectId,
}: {
  result: GitCheckpointResult | null;
  error: string | null;
  workspacePath: string;
  projectId: string;
}) {
  if (!result && !error) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <div style={{ fontSize: 48, marginBottom: 20 }}>🎯</div>
        <Spinner size={36} />
        <p style={{ marginTop: 16, color: 'var(--text-muted)' }}>Creating git checkpoint…</p>
        <p className="text-muted text-sm">Staging all changes and creating a commit.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card animate-fade-up" style={{ padding: 24 }}>
        <div style={{ fontSize: 40, marginBottom: 16 }}>⚠️</div>
        <h3 style={{ marginBottom: 8, color: '#fca5a5' }}>Checkpoint Failed</h3>
        <p style={{ color: '#fca5a5', fontFamily: 'monospace', fontSize: 13 }}>{error}</p>
      </div>
    );
  }

  if (result!.status === 'nothing_to_commit') {
    return (
      <div className="card animate-fade-up" style={{ padding: 24, textAlign: 'center' }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>✅</div>
        <h3 style={{ marginBottom: 8 }}>Working Tree is Clean</h3>
        <p className="text-muted">No changes to commit — checkpoint acknowledged.</p>
        <p className="text-muted text-sm" style={{ marginTop: 8 }}>Branch: <code>{result!.branch}</code></p>
        <div style={{ marginTop: 24 }}>
          <button className="btn btn-primary" onClick={() => downloadCheckpointZip(workspacePath, projectId)}>
            📦 Download Workspace ZIP
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-up">
      <div style={{ padding: 24, borderRadius: 12, background: 'linear-gradient(135deg, rgba(29,127,138,0.15), rgba(16,185,129,0.1))', border: '1px solid rgba(29,127,138,0.25)', marginBottom: 24, textAlign: 'center' }}>
        <div style={{ fontSize: 56, marginBottom: 12 }}>🎯</div>
        <h2 style={{ marginBottom: 8, fontSize: 22 }}>Git Checkpoint Created</h2>
        <p className="text-muted">Pre-migration checkpoint successfully committed to version control.</p>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          <div>
            <p style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>Commit Hash</p>
            <code style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-accent)' }}>{result!.commit_hash}</code>
          </div>
          <div>
            <p style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>Branch</p>
            <code style={{ fontSize: 18, fontWeight: 700 }}>{result!.branch}</code>
          </div>
          <div>
            <p style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>Files Committed</p>
            <span style={{ fontSize: 18, fontWeight: 700 }}>{result!.files_committed}</span>
          </div>
          <div>
            <p style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>Timestamp</p>
            <span style={{ fontSize: 14 }}>{new Date(result!.timestamp).toLocaleString()}</span>
          </div>
        </div>

        {result!.commit_message && (
          <div style={{ marginTop: 20, padding: 12, background: 'rgba(0,0,0,0.03)', borderRadius: 8 }}>
            <p style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 6 }}>COMMIT MESSAGE</p>
            <code style={{ fontSize: 13, color: 'var(--color-accent-2)' }}>{result!.commit_message}</code>
          </div>
        )}

        {result!.stats && (
          <div style={{ marginTop: 16, display: 'flex', gap: 20 }}>
            <div><span style={{ color: '#10b981', fontWeight: 600 }}>+{result!.stats.insertions}</span> <span className="text-muted text-sm">insertions</span></div>
            <div><span style={{ color: '#ef4444', fontWeight: 600 }}>-{result!.stats.deletions}</span> <span className="text-muted text-sm">deletions</span></div>
            <div><span style={{ fontWeight: 600 }}>{result!.stats.files}</span> <span className="text-muted text-sm">files</span></div>
          </div>
        )}

        {result!.is_new_repo && (
          <div style={{ marginTop: 16, padding: '8px 12px', background: 'rgba(29,127,138,0.08)', borderRadius: 6, fontSize: 13, color: 'var(--color-accent)' }}>
            ℹ️ A new git repository was initialized in the workspace.
          </div>
        )}
      </div>

      <div style={{ padding: 16, borderRadius: 8, background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', marginBottom: 20 }}>
        <h4 style={{ color: '#10b981', marginBottom: 8, fontSize: 14 }}>✅ Milestone Complete: Dashboard → Git Checkpoint</h4>
        <p className="text-muted text-sm">
          All steps completed successfully. A git checkpoint has been created before any transformation.
          The next milestone would implement OpenRewrite, Roslyn, or language-specific transformation engines.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 12 }}>
        <button className="btn btn-primary" onClick={() => downloadCheckpointZip(workspacePath, projectId)}>
          📦 Download Workspace ZIP
        </button>
      </div>
    </div>
  );
}

// ── Main Pipeline Page ─────────────────────────────────────────────────────────

export default function Pipeline() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const workspacePath = searchParams.get('wp') || '';

  const [stage, setStage] = useState<StageKey>('discovery');
  const [profile, setProfile] = useState<TechnologyProfile | null>(null);
  const [depResult, setDepResult] = useState<DependencyAnalysisResult | null>(null);
  const [applyResult, setApplyResult] = useState<DependencyAnalysisResult | null>(null);
  const [recommendations, setRecommendations] = useState<Recipe[] | null>(null);
  const [selectedRecipeIds, setSelectedRecipeIds] = useState<Set<string>>(new Set());
  const [approvedDepIds, setApprovedDepIds] = useState<Set<string>>(new Set());
  const [recipeAnalysis, setRecipeAnalysis] = useState<RecipeAnalysisResult | null>(null);
  const [plan, setPlan] = useState<MigrationPlan | null>(null);
  const [checkpointResult, setCheckpointResult] = useState<GitCheckpointResult | null>(null);
  const [checkpointError, setCheckpointError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const hasRun = useRef(false);

  useEffect(() => {
    if (hasRun.current || !projectId || !workspacePath) return;
    hasRun.current = true;

    analyzeRepo(workspacePath, projectId)
      .then(res => {
        const data = res.data;
        const p = data.profile || {};
        const profileData: TechnologyProfile = {
          profile_id: p.profile_id || projectId,
          workspace_path: workspacePath,
          languages: p.languages || [],
          frameworks: p.frameworks || [],
          build_systems: (p.build_systems || []).map((b: any) => b.name || b),
          test_frameworks: p.testing_frameworks || [],
        };
        setProfile(profileData);
      })
      .catch(e => setError(e?.response?.data?.detail || e.message || 'Analysis failed.'));
  }, [projectId, workspacePath]);

  const go = useCallback((next: StageKey) => setStage(next), []);

  useEffect(() => {
    if (stage !== 'dep-detection' || depResult !== null || !workspacePath || !projectId) return;
    planDependencyAnalysis(workspacePath, projectId)
      .then(res => {
        setDepResult(res.data);
        const allIds = new Set<string>((res.data.proposed_updates || []).map((u: any) => u.dependency_name + u.source_file));
        setApprovedDepIds(allIds);
      })
      .catch(e => setError(e?.response?.data?.detail || e.message || 'Dependency detection failed.'));
  }, [stage]);

  useEffect(() => {
    if (stage !== 'dep-applying' || applyResult !== null || !workspacePath || !projectId) return;

    const depUpdates = depResult?.proposed_updates || [];
    if (depUpdates.length === 0 || approvedDepIds.size === 0) {
      setApplyResult(depResult!);
      return;
    }

    applyDependencyUpdates(workspacePath, projectId)
      .then(res => setApplyResult(res.data))
      .catch(e => setError(e?.response?.data?.detail || e.message || 'Apply failed.'));
  }, [stage]);

  useEffect(() => {
    if (stage !== 'ai-recommending' || recommendations !== null || !workspacePath || !projectId || !profile) return;

    const langs = profile.languages.map(l => l.name.toLowerCase());
    const frameworks = profile.frameworks.map(f => f.name.toLowerCase());
    const depNames = (depResult?.dependencies || []).map((d: any) => d.name.toLowerCase());

    getRecipeRecommendations({
      project_id: projectId,
      workspace_path: workspacePath,
      languages: langs,
      frameworks,
      detected_deps: depNames,
      has_tests: profile.test_frameworks.length > 0,
      has_ci: false,
    })
      .then(res => setRecommendations(res.data.recipes || []))
      .catch(e => setError(e?.response?.data?.detail || e.message || 'Recommendation failed.'));
  }, [stage]);

  useEffect(() => {
    if (stage !== 'recipe-analyzing' || recipeAnalysis !== null || selectedRecipeIds.size === 0) return;

    analyzeRecipeConflicts(Array.from(selectedRecipeIds))
      .then(res => setRecipeAnalysis(res.data))
      .catch(e => setError(e?.response?.data?.detail || e.message || 'Recipe analysis failed.'));
  }, [stage]);

  useEffect(() => {
    if (stage !== 'plan' || plan !== null || !workspacePath || !projectId) return;

    const approvedUpdates = (depResult?.proposed_updates || []).filter((u: any) =>
      approvedDepIds.has(u.dependency_name + u.source_file)
    );

    generateMigrationPlan({
      project_id: projectId,
      workspace_path: workspacePath,
      selected_recipe_ids: Array.from(selectedRecipeIds),
      approved_dep_updates: approvedUpdates,
    })
      .then(res => setPlan(res.data.plan))
      .catch(e => setError(e?.response?.data?.detail || e.message || 'Plan generation failed.'));
  }, [stage]);

  useEffect(() => {
    if (stage !== 'checkpointing' || checkpointResult !== null || checkpointError !== null || !workspacePath || !projectId) return;

    createGitCheckpoint({
      workspace_path: workspacePath,
      project_id: projectId,
      message: plan?.git_checkpoint_message,
    })
      .then(res => {
        setCheckpointResult(res.data);
        setTimeout(() => go('executing-recipes'), 1000);
      })
      .catch(e => {
        setCheckpointError(e?.response?.data?.detail || e.message || 'Checkpoint failed.');
      });
  }, [stage]);

  const [recipeRun, setRecipeRun] = useState<any>(null);
  const [recipeRunError, setRecipeRunError] = useState<string | null>(null);

  useEffect(() => {
    if (stage !== 'executing-recipes' || recipeRun !== null || recipeRunError !== null || !workspacePath || !projectId) return;
    executeRecipes({
      project_id: projectId,
      workspace_path: workspacePath,
      recipe_ids: Array.from(selectedRecipeIds),
    })
      .then(res => {
        setRecipeRun(res.data);
        setTimeout(() => go('done'), 1500);
      })
      .catch(e => setRecipeRunError(e?.response?.data?.detail || e.message || 'Recipe execution failed.'));
  }, [stage]);

  const stageOrder: StageKey[] = [
    'discovery', 'profile', 'dep-detection', 'version-detection', 'dep-review',
    'dep-applying', 'ai-recommending', 'recipe-selection', 'recipe-analyzing',
    'conflict-resolution', 'plan', 'checkpointing', 'executing-recipes', 'done',
  ];
  const currentIdx = stageOrder.indexOf(stage);

  const sidebarSteps = DISPLAY_STEPS;
  const getStepStatus = (step: Step): 'done' | 'active' | 'upcoming' => {
    const stepStages: Record<number, StageKey[]> = {
      1: ['discovery'],
      2: ['profile'],
      3: ['dep-detection'],
      4: ['version-detection'],
      5: ['dep-review'],
      6: ['dep-applying'],
      7: ['ai-recommending'],
      8: ['recipe-selection'],
      9: ['recipe-analyzing'],
      10: ['conflict-resolution'],
      11: ['plan'],
      12: ['checkpointing'],
      13: ['executing-recipes', 'done'],
    };
    const stages = stepStages[step.number] || [];
    if (stages.includes(stage)) return 'active';
    const firstStageIdx = stageOrder.indexOf(stages[0]);
    if (firstStageIdx < currentIdx) return 'done';
    return 'upcoming';
  };

  const currentStep = STEPS.find(s => s.key === stage) || STEPS[0];

  const renderContent = () => {
    if (error) {
      return (
        <div style={{ padding: 24 }}>
          <div style={{ padding: 20, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, color: '#fca5a5', marginBottom: 20 }}>
            <strong>Error:</strong> {error}
          </div>
          <button className="btn btn-ghost" onClick={() => navigate('/')}>← Back to Dashboard</button>
        </div>
      );
    }

    switch (stage) {
      case 'discovery':
        return <DiscoveryStep profile={profile} onContinue={() => go('profile')} />;
      case 'profile':
        return <ProfileStep profile={profile} onContinue={() => go('dep-detection')} />;
      case 'dep-detection':
        return <DepDetectionStep depResult={depResult} onContinue={() => go('version-detection')} />;
      case 'version-detection':
        return <VersionDetectionStep depResult={depResult} onContinue={() => go('dep-review')} />;
      case 'dep-review':
        return (
          <DepReviewStep
            depResult={depResult}
            approvedIds={approvedDepIds}
            setApprovedIds={setApprovedDepIds}
            onContinue={() => go('dep-applying')}
            onSkip={() => {
              setApplyResult(depResult!);
              go('ai-recommending');
            }}
          />
        );
      case 'dep-applying':
        return <DepApplyingStep applyResult={applyResult} onContinue={() => go('ai-recommending')} />;
      case 'ai-recommending':
        return <AIRecommendingStep recommendations={recommendations} onContinue={() => go('recipe-selection')} />;
      case 'recipe-selection':
        return (
          <RecipeSelectionStep
            recommendations={recommendations || []}
            selectedIds={selectedRecipeIds}
            setSelectedIds={setSelectedRecipeIds}
            onContinue={() => go('recipe-analyzing')}
          />
        );
      case 'recipe-analyzing':
        return <RecipeAnalyzingStep analysis={recipeAnalysis} onContinue={() => go('conflict-resolution')} />;
      case 'conflict-resolution':
        return (
          <ConflictResolutionStep
            analysis={recipeAnalysis}
            onContinue={() => go('plan')}
            onSkip={() => go('plan')}
          />
        );
      case 'plan':
        return <PlanStep plan={plan} onContinue={() => go('checkpointing')} />;
      case 'checkpointing':
        return (
          <CheckingStep
            label="Creating git checkpoint…"
            result={checkpointResult}
            error={checkpointError}
          />
        );
      case 'executing-recipes':
        return (
          <RecipeExecuteStep
            result={recipeRun}
            error={recipeRunError}
          />
        );
      case 'done':
        return (
          <CheckpointStep
            result={checkpointResult}
            error={checkpointError}
            workspacePath={workspacePath}
            projectId={projectId || ''}
          />
        );
    }
  };

  return (
    <div style={{ display: 'flex', gap: 0, minHeight: 'calc(100vh - 48px)', position: 'relative', background: 'var(--color-bg)', color: 'var(--color-text)' }}>
      {/* Sidebar */}
      <div style={{
        width: 260, flexShrink: 0,
        borderRight: '1px solid var(--color-border)',
        padding: '24px 0',
        background: 'var(--color-surface)',
        position: 'sticky', top: 0, height: 'calc(100vh - 48px)', overflowY: 'auto',
      }}>
        <div style={{ padding: '0 20px 16px', borderBottom: '1px solid var(--color-border)', marginBottom: 8 }}>
          <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-accent)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Migration Pipeline</p>
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'monospace' }}>
            {projectId}
          </p>
        </div>

        {sidebarSteps.map(step => {
          const status = getStepStatus(step);
          return (
            <div key={step.key} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '10px 20px',
              background: status === 'active' ? 'rgba(29, 127, 138, 0.08)' : 'transparent',
              borderLeft: `3px solid ${status === 'active' ? 'var(--color-accent)' : status === 'done' ? 'var(--color-success)' : 'transparent'}`,
              transition: 'all 0.2s',
            }}>
              <div style={{
                width: 26, height: 26, borderRadius: 99, flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700,
                background: status === 'done' ? 'var(--color-success)' : status === 'active' ? 'var(--color-accent)' : 'rgba(0, 0, 0, 0.05)',
                color: status === 'upcoming' ? 'var(--color-text-muted)' : '#fff',
              }}>
                {status === 'done' ? '✓' : step.number}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: 13, fontWeight: status === 'active' ? 600 : 400,
                  color: status === 'active' ? 'var(--color-text)' : status === 'done' ? 'var(--color-success)' : 'var(--color-text-muted)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>{step.title}</div>
              </div>
              {status === 'active' && stage !== 'done' && <Spinner size={14} />}
            </div>
          );
        })}
      </div>

      {/* Main Content Area */}
      <div style={{ flex: 1, padding: '32px 36px', overflowY: 'auto', maxWidth: 900 }}>
        {/* Step Header */}
        <div style={{ marginBottom: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10, background: 'rgba(29, 127, 138, 0.12)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18,
            }}>{currentStep.icon}</div>
            <div>
              <p style={{ fontSize: 12, color: 'var(--color-accent)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Step {currentStep.number} of 12
              </p>
              <h1 style={{ fontSize: 22, fontWeight: 700, marginTop: 2 }}>{currentStep.title}</h1>
            </div>
          </div>
          <div className="progress-bar" style={{ marginTop: 16 }}>
            <div className="progress-fill" style={{ width: `${(Math.min(currentStep.number, 12) / 12) * 100}%` }} />
          </div>
        </div>

        {renderContent()}
      </div>
    </div>
  );
}
