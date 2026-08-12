import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import './index.css';

import Dashboard from './pages/Dashboard';
import NewMigration from './pages/NewMigration';
import Analysis from './pages/Analysis';
import MigrationPlan from './pages/MigrationPlan';
import Execution from './pages/Execution';
import Results from './pages/Results';
import CodeChanges from './pages/CodeChanges';
import History from './pages/History';
import DependencyAnalysisPage from './pages/DependencyAnalysis';

const queryClient = new QueryClient();

const NAV = [
  { to: '/', label: '⬡ Dashboard', exact: true },
  { to: '/new', label: '＋ New Migration' },
  { to: '/dependencies', label: '🔍 Dependencies' },
  { to: '/history', label: '⟳ History' },
];

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="app-shell">
          <aside className="sidebar">
            <div className="sidebar-logo">
              <span className="logo-icon">⬡</span>
              <span>Modernize</span>
            </div>
            {NAV.map(n => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.exact}
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              >
                {n.label}
              </NavLink>
            ))}
          </aside>
          <main className="main-content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/new" element={<NewMigration />} />
              <Route path="/analyze/:projectId" element={<Analysis />} />
              <Route path="/plan/:projectId" element={<MigrationPlan />} />
              <Route path="/execute/:planId" element={<Execution />} />
              <Route path="/results/:resultId" element={<Results />} />
              <Route path="/results/:resultId/changes" element={<CodeChanges />} />
              <Route path="/history" element={<History />} />
              <Route path="/dependencies" element={<DependencyAnalysisPage />} />
              <Route path="*" element={<Navigate to="/" />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
