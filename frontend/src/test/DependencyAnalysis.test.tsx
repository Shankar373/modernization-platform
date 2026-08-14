import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import DependencyAnalysisPage from '../pages/DependencyAnalysis';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import * as client from '../api/client';

vi.mock('../api/client', () => {
  return {
    runDependencyAnalysis: vi.fn().mockImplementation(() => Promise.resolve({ data: { dependencies: [], dependency_files: [] } })),
    clearDependencyCache: vi.fn().mockImplementation(() => Promise.resolve({ data: {} })),
    applyDependencyUpdates: vi.fn().mockImplementation(() => Promise.resolve({ data: {} })),
  };
});

const renderWithUrl = (url: string) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[url]}>
        <DependencyAnalysisPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe('DependencyAnalysis Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows empty step when no path provided', () => {
    renderWithUrl('/dependencies');
    expect(screen.getByText(/Dependency Analysis/)).toBeInTheDocument();
    expect(screen.getByText(/No workspace path provided/)).toBeInTheDocument();
  });

  it('runs analysis and renders results when path is provided', async () => {
    const mockDeps = [
      {
        name: 'requests',
        current_version: '2.28.0',
        latest_stable_version: '2.31.0',
        source_file: 'requirements.txt',
        ecosystem: 'python',
        status: 'UPDATE_AVAILABLE',
        update_required: true,
        reason: 'Security vulnerability fix',
      }
    ];

    vi.mocked(client.runDependencyAnalysis).mockResolvedValue({
      status: 200, statusText: 'OK', headers: {}, config: {} as any,
      data: {
        workspace_path: 'C:\\workspace',
        project_id: 'proj-123',
        dependency_files: [{ path: 'requirements.txt', ecosystem: 'python', is_lockfile: false }],
        dependencies: mockDeps,
        up_to_date: [],
        outdated: [mockDeps[0]],
        constraint_blocked: [],
        lookup_failed: [],
        changed_files: [],
        update_plan: { actions: [] },
        validation_results: { build_passed: true },
      }
    });

    renderWithUrl('/dependencies?wp=C:\\workspace&project=proj-123');
    
    // Verify loading and completed state
    await waitFor(() => {
      expect(screen.getByText(/requests/)).toBeInTheDocument();
      expect(screen.getByText('2.28.0')).toBeInTheDocument();
      expect(screen.getByText('2.31.0')).toBeInTheDocument();
    });
  });
});
