/**
 * RightSidebar.tsx - 320px widget sidebar
 */

import React from 'react';
import './RightSidebar.css';

interface Widget {
  id: string;
  title: string;
  content: React.ReactNode;
}

export const RightSidebar: React.FC = () => {
  const widgets: Widget[] = [
    {
      id: 'active-discussions',
      title: 'Active Discussions',
      content: (
        <div className="right-sidebar__widget-content">
          <p className="right-sidebar__empty-message">
            No active discussions at the moment.
          </p>
        </div>
      ),
    },
    {
      id: 'trending-topics',
      title: 'Trending Topics',
      content: (
        <div className="right-sidebar__widget-content">
          <ul className="right-sidebar__topic-list">
            <li className="right-sidebar__topic-item">
              <span className="right-sidebar__topic-tag">#democracy</span>
              <span className="right-sidebar__topic-count">12 discussions</span>
            </li>
            <li className="right-sidebar__topic-item">
              <span className="right-sidebar__topic-tag">#climate</span>
              <span className="right-sidebar__topic-count">8 discussions</span>
            </li>
            <li className="right-sidebar__topic-item">
              <span className="right-sidebar__topic-tag">#technology</span>
              <span className="right-sidebar__topic-count">15 discussions</span>
            </li>
          </ul>
        </div>
      ),
    },
    {
      id: 'quick-stats',
      title: 'Quick Stats',
      content: (
        <div className="right-sidebar__widget-content">
          <div className="right-sidebar__stats">
            <div className="right-sidebar__stat-item">
              <span className="right-sidebar__stat-value">24</span>
              <span className="right-sidebar__stat-label">Active Discussions</span>
            </div>
            <div className="right-sidebar__stat-item">
              <span className="right-sidebar__stat-value">1.2k</span>
              <span className="right-sidebar__stat-label">Participants</span>
            </div>
            <div className="right-sidebar__stat-item">
              <span className="right-sidebar__stat-value">3.4k</span>
              <span className="right-sidebar__stat-label">Contributions</span>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: 'recent-activity',
      title: 'Recent Activity',
      content: (
        <div className="right-sidebar__widget-content">
          <div className="right-sidebar__activity-list">
            <div className="right-sidebar__activity-item">
              <div className="right-sidebar__activity-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <div className="right-sidebar__activity-content">
                <p className="right-sidebar__activity-text">
                  New discussion created: "Future of AI"
                </p>
                <span className="right-sidebar__activity-time">2 hours ago</span>
              </div>
            </div>
            <div className="right-sidebar__activity-item">
              <div className="right-sidebar__activity-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M20 21V19C20 17.9391 19.5786 16.9217 18.8284 16.1716C18.0783 15.4214 17.0609 15 16 15H8C6.93913 15 5.92172 15.4214 5.17157 16.1716C4.42143 16.9217 4 17.9391 4 19V21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <circle cx="12" cy="7" r="4" stroke="currentColor" strokeWidth="2"/>
                </svg>
              </div>
              <div className="right-sidebar__activity-content">
                <p className="right-sidebar__activity-text">
                  15 new participants joined
                </p>
                <span className="right-sidebar__activity-time">5 hours ago</span>
              </div>
            </div>
          </div>
        </div>
      ),
    },
  ];

  return (
    <aside className="right-sidebar" aria-label="Widgets">
      <div className="right-sidebar__content">
        {widgets.map((widget) => (
          <div key={widget.id} className="right-sidebar__widget">
            <h3 className="right-sidebar__widget-title">
              {widget.title}
            </h3>
            {widget.content}
          </div>
        ))}
      </div>
    </aside>
  );
};

export default RightSidebar;
