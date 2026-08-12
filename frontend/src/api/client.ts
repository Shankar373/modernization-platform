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
