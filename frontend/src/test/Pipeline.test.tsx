import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Pipeline from '../pages/Pipeline';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

// @ts-ignore

vi.mock('../api/client', () => {
  const innerProfile = {
    profile: {
      profile_id: 'prof-123',
      workspace_path: 'C:\\workspace',
      languages: [{ name: 'C#', version: 'netcoreapp3.1', confidence: 0.9 }],
      frameworks: [],
      build_systems: [],
      testing_frameworks: [],
    }
  };

  const innerDepResult = {
    dependencies: [],
    dependency_files: [{ path: 'test.csproj', ecosystem: 'dotnet', is_lockfile: false }],
    up_to_date: [],
    outdated: [],
    constraint_blocked: [],
    lookup_failed: [],
    proposed_updates: [],
    changed_files: [],
    validation_status: 'PASSED',
    validation_errors: [],
  };

  const innerRecommendations = {
    recommendations: [
      {
        recipe_id: 'cs-file-scoped-namespace',
        name: 'Convert namespace to file-scoped',
        category: 'style',
        priority: 'HIGH',
        reason: 'Modernizes namespace layout',
        risk: 'LOW',
        capability_status: 'AVAILABLE',
        executable: true,
      }
    ]
  };

  const innerRecipeAnalysis = {
    has_conflicts: false,
    conflicts: [],
    ordered_recipes: [
      {
        id: 'cs-file-scoped-namespace',
        name: 'Convert namespace to file-scoped',
        category: 'style',
      }
    ],
    execution_phases: [
      {
        phase: 1,
        recipes: [
          {
            id: 'cs-file-scoped-namespace',
            name: 'Convert namespace to file-scoped',
            category: 'style',
          }
        ]
      }
    ],
    auto_added_recipes: [],
  };

  const innerMigrationPlan = {
    plan: {
      selected_recipes: ['cs-file-scoped-namespace'],
      phases: [
        {
          phase: 1,
          recipes: [
            {
              id: 'cs-file-scoped-namespace',
              name: 'Convert namespace to file-scoped',
              category: 'style',
            }
          ]
        }
      ],
      dep_updates_count: 0,
      estimated_files_changed: 1,
      git_checkpoint_message: 'git commit pre-migration',
      risk_level: 'LOW',
      summary: 'Upgrade plan for C# block namespace'
    }
  };

  return {
    analyzeRepo: vi.fn().mockImplementation(() => Promise.resolve({ data: innerProfile })),
    planDependencyAnalysis: vi.fn().mockImplementation(() => Promise.resolve({ data: innerDepResult })),
    applyDependencyUpdates: vi.fn().mockImplementation(() => Promise.resolve({ data: innerDepResult })),
    getRecipeRecommendations: vi.fn().mockImplementation(() => Promise.resolve({ data: { recipes: [] } })),
    getLlmRecommendations: vi.fn().mockImplementation(() => Promise.resolve({ data: innerRecommendations })),
    getLlmStatus: vi.fn().mockImplementation(() => Promise.resolve({ data: { provider: 'groq', model: 'llama-3.3-70b-versatile', llm_available: true } })),
    analyzeRecipeConflicts: vi.fn().mockImplementation(() => Promise.resolve({ data: innerRecipeAnalysis })),
    generateMigrationPlan: vi.fn().mockImplementation(() => Promise.resolve({ data: innerMigrationPlan })),
    executeRecipes: vi.fn().mockImplementation(() => Promise.resolve({ data: { recipes_executed: 1, files_changed: 1, findings_count: 0 } })),
    createGitCheckpoint: vi.fn().mockImplementation(() => Promise.resolve({ data: { status: 'success', commit_hash: '123456', branch: 'master', files_committed: 1, timestamp: new Date().toISOString() } })),
    optimizeCode: vi.fn().mockImplementation(() => Promise.resolve({
      data: {
        success: true,
        dry_run: false,
        files_scanned: 1,
        files_optimized: 1,
        files_changed: 1,
        files_unchanged: 0,
        files_skipped: 0,
        files_failed: 0,
        skipped_files: [],
        optimized_files: [
          {
            file: 'src/LegacyFilter.cs',
            recipe: 'dotnet format',
            optimization: 'dotnet format style clean',
            before_content: 'class X {}',
            after_content: 'class X {}',
            diff: '@@ -1 +1 @@\n-class X {}\n+class X {}',
            changed: true,
            validation_status: 'PASSED',
            original_content: 'class X {}',
            modernized_content: 'class X {}',
            optimized_content: 'class X {}',
            modernization_diff: 'diff1',
            optimization_diff: 'diff2',
            final_diff: 'diff3',
          }
        ],
        build_passed: true,
        tests_passed: true,
        build_output: 'Build succeeded',
        rolled_back: false,
      }
    })),
    downloadCheckpointZip: vi.fn().mockImplementation(() => Promise.resolve({})),
  };
});

const renderPipelineWithParams = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/pipeline/project-123?wp=C:\\workspace']}>
        <Routes>
          <Route path="/pipeline/:projectId" element={<Pipeline />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe('Pipeline Multi-Step Wizard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('navigates the entire migration workflow successfully from Discovery to Done', async () => {
    renderPipelineWithParams();

    // Verify loading state
    expect(screen.getByText(/Analysing application stack/)).toBeInTheDocument();

    // 1. Verify Discovery completes
    await waitFor(() => {
      expect(screen.getByText('C#')).toBeInTheDocument();
      expect(screen.getByText('netcoreapp3.1')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Proceed to Project Profile/ }));

    // 2. Verify Project Technology Profile
    await waitFor(() => {
      expect(screen.getByText(/Project Technology Profile/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Proceed to Dependency Detection/ }));

    // 3. Verify Dependency Detection
    await waitFor(() => {
      expect(screen.getByText(/DETECTED DEPENDENCY FILES/)).toBeInTheDocument();
      expect(screen.getByText('test.csproj')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Proceed to Version Detection/ }));

    // 4. Verify Version Detection
    await waitFor(() => {
      expect(screen.getByText(/ALL DEPENDENCIES/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Proceed to Dependency Review/ }));

    // 5. Verify Dependency Update Review
    await waitFor(() => {
      expect(screen.getAllByText(/Dependency Update Review/).length).toBeGreaterThan(0);
      expect(screen.getByText(/All Dependencies Up to Date/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Continue/ }));

    // Note: Since there are no updates to apply, step 6 (DepApplying) is skipped 
    // and we jump straight to step 7 (AIRecommendations).

    // 7. Verify AI Recommendations
    await waitFor(() => {
      expect(screen.getByText(/TOP RECOMMENDATIONS/)).toBeInTheDocument();
      expect(screen.getByText(/Convert namespace to file-scoped/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Proceed to Recipe Selection/ }));

    // 8. Verify Recipe Selection
    await waitFor(() => {
      expect(screen.getByText(/Select Migration Recipes/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Analyse .* Recipe/ }));

    // 9. Verify Recipe Analysis
    await waitFor(() => {
      expect(screen.getByText(/EXECUTION ORDER/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Proceed to Conflict Resolution/ }));

    // 10. Verify Conflict Resolution
    await waitFor(() => {
      expect(screen.getByText(/No Conflicts Detected/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Proceed to Migration Plan/ }));

    // 11. Verify Migration Plan
    await waitFor(() => {
      expect(screen.getAllByText(/Migration Plan/).length).toBeGreaterThan(0);
    });
    fireEvent.click(screen.getByRole('button', { name: /Create Git Checkpoint/ }));

    // 12. Wait for automatic transition through checkpointing -> executing -> optimizing -> changed-files
    await waitFor(() => {
      expect(screen.getByText(/Changed Files & Before\/After Diff/)).toBeInTheDocument();
      expect(screen.getByText('src/LegacyFilter.cs')).toBeInTheDocument();
    }, { timeout: 12000 });

    // 13. Finish Migration to go to the final Git Checkpoint results screen
    fireEvent.click(screen.getByRole('button', { name: /Finish Migration/ }));

    // 14. Verify final complete Git Checkpoint screen
    await waitFor(() => {
      expect(screen.getByText('Git Checkpoint Created')).toBeInTheDocument();
      expect(screen.getByText('123456')).toBeInTheDocument();
    }, { timeout: 4000 });
  }, 25000);
});
