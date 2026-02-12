/**
 * AppWithLayout.tsx - Example of App integration with DesktopLayout
 *
 * This demonstrates how to wrap your existing pages with the new
 * 4-column desktop layout. You can choose to:
 * 1. Use the layout globally for all routes
 * 2. Use it selectively for specific routes
 * 3. Toggle sidebars based on the route/context
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { DesktopLayout } from './layouts/DesktopLayout';
import { DiscussionCreate } from './pages/DiscussionCreate';
import { DiscussionLive } from './pages/DiscussionLive';
import { SubmissionPage } from './pages/SubmissionPage';
import DiscussionReport from './pages/DiscussionReport';
import { ApprovalInterface } from './pages/ApprovalInterface/ApprovalInterface';
import './App.css';

function AppWithLayout() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          {/* Home page with full layout */}
          <Route
            path="/"
            element={
              <DesktopLayout>
                <HomePage />
              </DesktopLayout>
            }
          />

          {/* Discussion creation with layout */}
          <Route
            path="/discussions/create"
            element={
              <DesktopLayout>
                <DiscussionCreate />
              </DesktopLayout>
            }
          />

          {/* Live discussion with layout (no right sidebar for focus) */}
          <Route
            path="/discussions/:discussionId/live"
            element={
              <DesktopLayout showRightSidebar={false}>
                <DiscussionLive />
              </DesktopLayout>
            }
          />

          {/* Submission page with layout */}
          <Route
            path="/discussions/:discussionId/submit"
            element={
              <DesktopLayout showRightSidebar={false}>
                <SubmissionPage />
              </DesktopLayout>
            }
          />

          {/* Approval interface with full layout */}
          <Route
            path="/discussions/:discussionId/approve"
            element={
              <DesktopLayout>
                <ApprovalInterface />
              </DesktopLayout>
            }
          />

          {/* Report page with layout */}
          <Route
            path="/discussions/:discussionId/report"
            element={
              <DesktopLayout>
                <DiscussionReport />
              </DesktopLayout>
            }
          />

          {/* 404 - Redirect to home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

// Home page component
function HomePage() {
  return (
    <div className="home-page">
      <div className="welcome-card">
        <h2>Welcome to OpenDiscuss</h2>
        <p>A structured discussion protocol for exploring diverse perspectives</p>
        <div className="home-actions">
          <a href="/discussions/create" className="btn btn-primary">
            Create New Discussion
          </a>
        </div>
      </div>

      {/* Example content showing layout in action */}
      <div style={{ marginTop: '2rem', padding: '1.5rem', background: 'white', borderRadius: '8px' }}>
        <h3 style={{ marginBottom: '1rem' }}>Layout Features</h3>
        <ul style={{ lineHeight: '1.8', color: '#666' }}>
          <li><strong>4-column responsive layout:</strong> Rail (56px) + Sidebar (260px) + Main (flexible) + Right (320px)</li>
          <li><strong>Responsive breakpoints:</strong> Right sidebar hides below 1100px, left sidebar hides below 820px</li>
          <li><strong>Sticky positioning:</strong> Topbar and sidebars stay fixed while content scrolls</li>
          <li><strong>CSS custom properties:</strong> Consistent theming with --bg, --panel, --border, --text, --muted, --accent</li>
          <li><strong>Flexible integration:</strong> Can show/hide any column per route</li>
        </ul>
      </div>
    </div>
  );
}

export default AppWithLayout;
