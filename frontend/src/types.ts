/** Shared TypeScript types for the modernization platform frontend. */

export interface FileChangeMetadata {
  file: string;
  status: 'MODIFIED' | 'ADDED' | 'DELETED';
  tools: string[];
  diff: string;
  before_content?: string;
  after_content?: string;
  changes?: Array<{ type: string; description: string }>;
  original_content?: string;
  modernized_content?: string;
  optimized_content?: string;
  modernization_diff?: string;
  optimization_diff?: string;
  final_diff?: string;
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

// ── Recipe Types ──────────────────────────────────────────────────────────────

export type RecipeCategory = 'upgrade' | 'style' | 'security' | 'performance';
export type RecipeComplexity = 'low' | 'medium' | 'high';

export interface Recipe {
  id: string;
  name: string;
  description: string;
  language: string;
  category: RecipeCategory;
  complexity: RecipeComplexity;
  tags: string[];
  requires: string[];
  conflicts_with: string[];
  score?: number;
  recommended?: boolean;
}

export interface RecipeConflict {
  recipe_a: string;
  recipe_b: string;
  severity: 'ERROR' | 'WARNING';
  reason: string;
  resolution: string;
}

export interface RecipePhase {
  phase: number;
  label: string;
  recipes: Recipe[];
  parallel: boolean;
}

export interface RecipeAnalysisResult {
  conflicts: RecipeConflict[];
  has_conflicts: boolean;
  ordered_recipes: Recipe[];
  auto_added_recipes: Recipe[];
  execution_phases: RecipePhase[];
}

export interface MigrationPlan {
  id: string;
  project_id: string;
  workspace_path: string;
  created_at: string;
  phases: RecipePhase[];
  selected_recipes: Recipe[];
  dep_updates_count: number;
  approved_dep_updates: DependencyUpdateAction[];
  estimated_files_changed: number;
  complexity_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  git_checkpoint_message: string;
  summary: string;
}

// ── Git Checkpoint Types ───────────────────────────────────────────────────────

export interface GitCheckpointResult {
  status: 'success' | 'nothing_to_commit';
  commit_hash: string | null;
  commit_hash_full?: string;
  commit_message?: string;
  timestamp: string;
  files_committed: number;
  branch: string;
  is_new_repo: boolean;
  stats?: { insertions: number; deletions: number; files: number };
  message?: string;
}


// -- Code Optimization Types ---------------------------------------------------

export interface SkippedFile {
  file: string;
  reason: string;
}

export interface OptimizedFileChange {
  file: string;
  recipe: string;
  optimization: string;
  before_content: string;
  after_content: string;
  diff: string;
  changed: boolean;
  validation_status: 'PASSED' | 'FAILED' | 'SKIPPED';
  original_content?: string;
  modernized_content?: string;
  optimized_content?: string;
  modernization_diff?: string;
  optimization_diff?: string;
  final_diff?: string;
}

export interface OptimizationResult {
  success: boolean;
  dry_run: boolean;
  files_scanned: number;
  files_optimized: number;
  files_changed: number;
  files_unchanged: number;
  files_skipped: number;
  files_failed: number;
  skipped_files: SkippedFile[];
  optimized_files: OptimizedFileChange[];
  build_passed: boolean;
  tests_passed?: boolean;
  build_output: string;
  rolled_back: boolean;
  error?: string;
  summary?: string;
}
