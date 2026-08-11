import axios from 'axios';

const API = axios.create({ baseURL: 'http://localhost:8001/api/v1' });

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

export const getResult = (resultId: string) => API.get(`/migration/result/${resultId}`);
export const getReport = (resultId: string) => API.get(`/migration/result/${resultId}/report`);
export const getChangedFiles = (resultId: string) => API.get(`/migration/result/${resultId}/files`);
