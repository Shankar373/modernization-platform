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
              <svg width="24" height="24" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ marginRight: 10 }}>
                {/* Top Segment */}
                <path d="M50 15 L85 35 L85 47 L50 27 Z" fill="#2d939a" />
                <path d="M50 15 L15 35 L50 55 L85 35 Z" fill="#3ca6ae" />
                <path d="M15 35 L50 55 L50 67 L15 47 Z" fill="#207f85" />
                {/* Bottom Segment */}
                <path d="M50 48 L85 68 L50 88 L15 68 Z" fill="#3ca6ae" />
                <path d="M50 48 L85 68 L85 80 L50 60 Z" fill="#207f85" />
                <path d="M15 68 L50 88 L50 76 L15 56 Z" fill="#1b6d72" />
                {/* Center Circle */}
                <circle cx="50" cy="51" r="9" fill="#f2bd22" />
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
                <svg width="20" height="20" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ marginRight: 6 }}>
                  {/* Top Segment */}
                  <path d="M50 15 L85 35 L85 47 L50 27 Z" fill="#2d939a" />
                  <path d="M50 15 L15 35 L50 55 L85 35 Z" fill="#3ca6ae" />
                  <path d="M15 35 L50 55 L50 67 L15 47 Z" fill="#207f85" />
                  {/* Bottom Segment */}
                  <path d="M50 48 L85 68 L50 88 L15 68 Z" fill="#3ca6ae" />
                  <path d="M50 48 L85 68 L85 80 L50 60 Z" fill="#207f85" />
                  <path d="M15 68 L50 88 L50 76 L15 56 Z" fill="#1b6d72" />
                  {/* Center Circle */}
                  <circle cx="50" cy="51" r="9" fill="#f2bd22" />
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
