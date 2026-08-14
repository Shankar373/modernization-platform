import axios from 'axios';
import type { MigrationProfile } from '../types';

const API = axios.create({ baseURL: '/api/v1' });


export const ingestZip = (file: File, projectName: string) => {
  const form = new FormData();
  form.append('file', file);
  form.append('project_name', projectName);
  return API.post('/ingest/zip', form);
};

export const ingestGit = (gitUrl: string, branch: string, projectName: string) =>
  API.post('/ingest/git', { git_url: gitUrl, branch, project_name: projectName });

export const analyzeRepo = (workspacePath: string, projectId: string) =>
  API.post('/analyze', { workspace_path: workspacePath, project_id: projectId });

export const getCapabilities = () => API.get('/capabilities');

export const createPlan = (data: {
  workspace_path: string;
  project_id: string;
  language: string;
  target_version: string;
  migration_profile: string;
}) => API.post('/migration/plan', data);

export const dryRun = (workspacePath: string, planId: string) =>
  API.post('/migration/dry-run', { workspace_path: workspacePath, plan_id: planId });

export const executeMigration = (workspacePath: string, planId: string) =>
  API.post('/migration/execute', { workspace_path: workspacePath, plan_id: planId, approved: true });

/** Run ALL adapters at once — no language selection needed. */
export const migrateAll = (workspacePath: string, projectId: string, profile = 'STANDARD') =>
  API.post('/migration/migrate-all', {
    workspace_path: workspacePath,
    project_id: projectId,
    migration_profile: profile,
  });

/**
 * Step 1 of automated pipeline:
 * Preview what ALL adapters would change — no files are modified.
 * Returns per-adapter breakdown and total files_would_change.
 */
export const dryRunAll = (
  workspacePath: string,
  projectId: string,
  profile: MigrationProfile = 'STANDARD'
) =>
  API.post('/migration/dry-run-all', {
    workspace_path: workspacePath,
    project_id: projectId,
    migration_profile: profile,
  });

/**
 * Step 2 of automated pipeline:
 * User accepted the dry-run preview — execute ALL adapters in parallel.
 * Requires approved=true as an explicit confirmation gate.
 */
export const approveAndExecute = (
  workspacePath: string,
  projectId: string,
  profile: MigrationProfile = 'STANDARD'
) =>
  API.post('/migration/approve-execute', {
    workspace_path: workspacePath,
    project_id: projectId,
    migration_profile: profile,
    approved: true,
  });

/**
 * Run the dependency analysis pipeline on a workspace WITHOUT writing files
 * (plan-only). Detects dependency files, queries registries, compares, and
 * returns the update plan. Actual disk writes happen only via
 * `applyDependencyUpdates`.
 */
export const runDependencyAnalysis = (
  workspacePath: string,
  projectId: string,
  forceRefresh = false,
  planOnly = true
) =>
  API.post('/dependency-analysis', {
    workspace_path: workspacePath,
    project_id: projectId,
    force_refresh: forceRefresh,
    plan_only: planOnly,
  });

/** Clear the cached dependency analysis result for a workspace. */
export const clearDependencyCache = (workspacePath: string) =>
  API.get('/dependency-analysis/cache-clear', { params: { workspace_path: workspacePath } });

export const getResult       = (resultId: string) => API.get(`/migration/result/${resultId}`);
export const getReport       = (resultId: string) => API.get(`/migration/result/${resultId}/report`);
export const getChangedFiles = (resultId: string) => API.get(`/migration/result/${resultId}/files`);

/** Trigger browser download of the modernized workspace as a ZIP. */
export const downloadModernizedZip = (resultId: string) => {
  const link = document.createElement('a');
  link.href = `/api/v1/migration/result/${resultId}/download`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

// ── Dependency Analysis (with plan_only support) ───────────────────────────────

/**
 * Run the dependency analysis in PLAN-ONLY mode:
 * detect + query registries + compare — but do NOT write any files.
 * Use for the "Dependency Update Review" step.
 */
export const planDependencyAnalysis = (workspacePath: string, projectId: string) =>
  API.post('/dependency-analysis', {
    workspace_path: workspacePath,
    project_id: projectId,
    force_refresh: true,
    plan_only: true,
  });

/**
 * Apply approved dependency updates to disk.
 * Runs the full pipeline (detect → compare → apply → validate).
 */
export const applyDependencyUpdates = (workspacePath: string, projectId: string) =>
  API.post('/dependency-analysis', {
    workspace_path: workspacePath,
    project_id: projectId,
    force_refresh: true,
    plan_only: false,
  });

// ── Recipe API ─────────────────────────────────────────────────────────────────

/** Fetch AI-powered recipe recommendations for a project. */
export const getRecipeRecommendations = (data: {
  project_id: string;
  workspace_path: string;
  languages: string[];
  frameworks: string[];
  detected_deps: string[];
  has_tests: boolean;
  has_ci: boolean;
}) => API.post('/recipes/recommend', data);

/** Detect conflicts and compute execution order for selected recipes. */
export const analyzeRecipeConflicts = (selectedRecipeIds: string[]) =>
  API.post('/recipes/conflicts', { selected_recipe_ids: selectedRecipeIds });

/** Generate the final Migration Plan. */
export const generateMigrationPlan = (data: {
  project_id: string;
  workspace_path: string;
  selected_recipe_ids: string[];
  approved_dep_updates: unknown[];
}) => API.post('/recipes/plan', data);

/** Execute selected recipes for real (apply transformations to the workspace). */
export const executeRecipes = (data: {
  project_id: string;
  workspace_path: string;
  recipe_ids: string[];
  dry_run?: boolean;
}) => API.post('/recipes/execute', data);

// ── Git Checkpoint ─────────────────────────────────────────────────────────────

/** Create a git checkpoint (commit) in the workspace. */
export const createGitCheckpoint = (data: {
  workspace_path: string;
  project_id: string;
  message?: string;
}) => API.post('/git/checkpoint', data);

/** Download the checkpointed workspace as a ZIP file. */
export const downloadCheckpointZip = (workspacePath: string, projectId: string) => {
  const link = document.createElement('a');
  link.href = `/api/v1/git/checkpoint/download?workspace_path=${encodeURIComponent(workspacePath)}&project_id=${encodeURIComponent(projectId)}`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

