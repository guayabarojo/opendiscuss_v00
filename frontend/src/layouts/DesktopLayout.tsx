/**
 * DesktopLayout.tsx - 4-column responsive layout
 *
 * Layout structure:
 * - Topbar (sticky header with search)
 * - Rail (56px icon rail - leftmost)
 * - Sidebar (260px navigation - second column)
 * - Main (variable width content area - third column)
 * - RightSidebar (320px widgets - rightmost)
 *
 * Responsive breakpoints:
 * - < 1100px: Hide right sidebar
 * - < 820px: Hide left sidebar
 * - < 600px: Hide rail
 */

import React from 'react';
import { Topbar } from '../components/Topbar/Topbar';
import { CommunityRail } from '../components/CommunityRail/CommunityRail';
import { CommunitySidebar } from '../components/CommunitySidebar/CommunitySidebar';
import { RightSidebar } from '../components/RightSidebar/RightSidebar';
import './DesktopLayout.css';

interface DesktopLayoutProps {
  children: React.ReactNode;
  showRail?: boolean;
  showSidebar?: boolean;
  showRightSidebar?: boolean;
}

export const DesktopLayout: React.FC<DesktopLayoutProps> = ({
  children,
  showRail = true,
  showSidebar = true,
  showRightSidebar = true,
}) => {
  return (
    <div className="desktop-layout">
      {/* Sticky Header with Search */}
      <header className="desktop-layout__topbar">
        <Topbar />
      </header>

      {/* Main Body - 4-column layout */}
      <div className="desktop-layout__body">
        {/* Column 1: Community Rail (56px icon rail) */}
        {showRail && (
          <aside className="desktop-layout__rail">
            <CommunityRail />
          </aside>
        )}

        {/* Column 2: Community Sidebar (260px navigation) */}
        {showSidebar && (
          <aside className="desktop-layout__sidebar">
            <CommunitySidebar />
          </aside>
        )}

        {/* Column 3: Main Content Area (variable width) */}
        <main className="desktop-layout__main">
          {children}
        </main>

        {/* Column 4: Right Sidebar (320px widgets) */}
        {showRightSidebar && (
          <aside className="desktop-layout__right-sidebar">
            <RightSidebar />
          </aside>
        )}
      </div>
    </div>
  );
};

export default DesktopLayout;
