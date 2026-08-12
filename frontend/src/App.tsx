import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import './index.css';

import Dashboard from './pages/Dashboard';
import NewMigration from './pages/NewMigration';
import Analysis from './pages/Analysis';
import Pipeline from './pages/Pipeline';
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
  { to: '/history', label: '⟳ History' },
];


export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="app-layout">
          <header className="top-bar">
            <div className="top-bar-logo">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ marginRight: 10 }}>
                <path d="M19 6H5C3.89 6 3 6.89 3 8V18C3 19.11 3.89 20 5 20H19C20.11 20 21 19.11 21 18V8C21 6.89 20.11 6 19 6Z" fill="#1d7f8a" />
                <circle cx="12" cy="13" r="3.5" fill="#f2bd22" />
                <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="#248888" />
              </svg>
              <span style={{ fontWeight: 700, letterSpacing: '0.06em', color: '#fff', fontSize: 13 }}>
                SYSTEMAOPS MODERNIZE
              </span>
            </div>
            <div className="top-bar-right">
              <span className="user-badge">SystemaOps Discuss Integration</span>
            </div>
          </header>

          <div className="app-shell">
            <aside className="sidebar">
              <div className="sidebar-logo">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ marginRight: 6 }}>
                  <path d="M19 6H5C3.89 6 3 6.89 3 8V18C3 19.11 3.89 20 5 20H19C20.11 20 21 19.11 21 18V8C21 6.89 20.11 6 19 6Z" fill="#248888" />
                  <circle cx="12" cy="13" r="3.5" fill="#f2bd22" />
                  <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="#32a1a1" />
                </svg>
                <span>Platform</span>
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
                <Route path="/pipeline/:projectId" element={<Pipeline />} />
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
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
