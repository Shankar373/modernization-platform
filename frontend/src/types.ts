/** Shared TypeScript types for the modernization platform frontend. */

export interface FileChangeMetadata {
  file: string;
  status: 'MODIFIED' | 'ADDED' | 'DELETED';
  tools: string[];
  diff: string;
  before_content?: string;
  after_content?: string;
  changes?: Array<{ type: string; description: string }>;
}

export interface MigrationStatistics {
  files_scanned: number;
  files_modified: number;
  files_unchanged: number;
  dependencies_updated?: number;
  capabilities_run?: number;
  tests_total?: number;
  tests_failed?: number;
  tests_passed?: boolean;
  build_passed?: boolean;
}

export type MigrationStatus =
  | 'SUCCESS'
  | 'PARTIALLY_SUCCESSFUL'
  | 'FAILED'
  | 'ASSESSMENT_ONLY'
  | 'NOT_SUPPORTED'
  | 'RUNNING';

export interface MigrationResult {
  result_id: string;
  job_id: string;
  project_id: string;
  plan_id: string;
  status: MigrationStatus;
  statistics: MigrationStatistics;
  changed_files: FileChangeMetadata[];
  warnings?: string[];
  manual_remediation?: string[];
  timeline?: Array<{ step: string; status: string; ts: string }>;
  completed_at?: string;
}

export interface MigrationReport {
  report_id: string;
  generated_at: string;
  adapter: string;
  final_status: MigrationStatus;
  statistics: MigrationStatistics;
  changed_files_count: number;
  build_passed: boolean;
  tests_passed?: boolean;
  warnings?: string[];
  errors?: string[];
  timeline?: Array<{ step: string; status: string; ts: string }>;
}

export interface LanguageProfile {
  name: string;
  version?: string;
  confidence: number;
}

export interface FrameworkProfile {
  name: string;
  language: string;
  version?: string;
}

export interface TechnologyProfile {
  profile_id: string;
  workspace_path: string;
  languages: LanguageProfile[];
  frameworks: FrameworkProfile[];
  build_systems: string[];
  test_frameworks: string[];
}

export interface IngestResponse {
  project_id: string;
  workspace_path: string;
  project_name: string;
  status: string;
}

export type MigrationProfile = 'CONSERVATIVE' | 'STANDARD' | 'AGGRESSIVE';

/** Per-adapter result from the dry-run-all preview. */
export interface AdapterDryRunResult {
  language: string;
  adapter: string;
  files_would_change: number;
  notes: string;
  warnings: string[];
  success: boolean;
}

/** Full response from POST /migration/dry-run-all */
export interface DryRunAllResult {
  success: boolean;
  total_files_would_change: number;
  adapters_found: string[];
  per_adapter: AdapterDryRunResult[];
  workspace_path: string;
  project_id: string;
  migration_profile: string;
  summary: string;
}

// ── Dependency Analysis Types ──────────────────────────────────────────────

export type DependencyStatus =
  | 'UP_TO_DATE'
  | 'UPDATE_AVAILABLE'
  | 'CONSTRAINT_BLOCKED'
  | 'LOOKUP_FAILED'
  | 'INVALID_VERSION';

export type DependencyEcosystem = 'python' | 'node' | 'java' | 'dotnet' | 'unknown';

export interface Dependency {
  name: string;
  current_version: string | null;
  version_constraint: string | null;
  latest_stable_version: string | null;
  source_file: string;
  ecosystem: DependencyEcosystem;
  status: DependencyStatus;
  update_required: boolean;
  reason: string;
  extras: string | null;
  environment_marker: string | null;
}

export interface DependencyFile {
  path: string;
  ecosystem: DependencyEcosystem;
  is_lockfile: boolean;
}

export interface DependencyUpdateAction {
  dependency_name: string;
  source_file: string;
  ecosystem: DependencyEcosystem;
  current_version: string | null;
  proposed_version: string;
  action: string;
  reason: string;
}

export interface DependencyAnalysisResult {
  workspace_path: string;
  project_id: string;
  cached: boolean;
  dependency_files: DependencyFile[];
  dependencies: Dependency[];
  up_to_date: string[];
  outdated: string[];
  constraint_blocked: string[];
  lookup_failed: string[];
  proposed_updates: DependencyUpdateAction[];
  changed_files: string[];
  validation_status: 'PASSED' | 'FAILED' | 'SKIPPED';
  validation_errors: string[];
  warnings: string[];
}
