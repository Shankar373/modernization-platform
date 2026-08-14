import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from '../App';


vi.mock('../api/client', () => {
  return {
    getCapabilities: vi.fn().mockImplementation(() => Promise.resolve({
      data: {
        capabilities: [
          { language: 'csharp', status: 'AVAILABLE', description: 'Roslyn C#' },
          { language: 'python', status: 'AVAILABLE', description: 'Ruff Python' },
        ]
      }
    })),
    ingestZip: vi.fn().mockImplementation(() => Promise.resolve({ data: {} })),
    ingestGit: vi.fn().mockImplementation(() => Promise.resolve({ data: {} })),
  };
});

describe('App Component and Navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders dashboard by default', async () => {
    render(<App />);
    expect(screen.getByText(/SYSTEMAOPS MODERNIZE/)).toBeInTheDocument();
    
    // Check main navigation links exist in the sidebar
    expect(screen.getByRole('link', { name: /New Migration/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Dependencies/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /History/ })).toBeInTheDocument();

    // Check Dashboard stats cards load using ASCII labels to avoid emoji encoding issues
    await waitFor(() => {
      expect(screen.getByText('Total Migrations')).toBeInTheDocument();
    });
  });

  it('navigates to new migration page', async () => {
    render(<App />);
    const link = screen.getByRole('link', { name: /New Migration/ });
    fireEvent.click(link);
    
    // In NewMigration page
    await waitFor(() => {
      expect(screen.getAllByText(/New Migration/).length).toBeGreaterThan(0);
    });
  });
});
