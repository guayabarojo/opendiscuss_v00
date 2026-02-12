/**
 * CommunitySidebar.tsx - 260px navigation sidebar
 */

import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import './CommunitySidebar.css';

interface NavigationSection {
  title: string;
  items: NavigationItem[];
}

interface NavigationItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
  path?: string;
  badge?: string | number;
  onClick?: () => void;
}

export const CommunitySidebar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const sections: NavigationSection[] = [
    {
      title: 'Navigation',
      items: [
        {
          id: 'home',
          label: 'Home',
          path: '/',
          icon: (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M3 9L12 2L21 9V20C21 20.5304 20.7893 21.0391 20.4142 21.4142C20.0391 21.7893 19.5304 22 19 22H5C4.46957 22 3.96086 21.7893 3.58579 21.4142C3.21071 21.0391 3 20.5304 3 20V9Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          ),
        },
        {
          id: 'create',
          label: 'Create Discussion',
          path: '/discussions/create',
          icon: (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 5V19M5 12H19" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          ),
        },
      ],
    },
    {
      title: 'Recent Discussions',
      items: [
        {
          id: 'discussion-1',
          label: 'Sample Discussion',
          badge: 'Live',
          onClick: () => console.log('Navigate to discussion'),
        },
      ],
    },
  ];

  const handleItemClick = (item: NavigationItem) => {
    if (item.onClick) {
      item.onClick();
    } else if (item.path) {
      navigate(item.path);
    }
  };

  const isActive = (path?: string) => {
    if (!path) return false;
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <nav className="community-sidebar" aria-label="Secondary navigation">
      {sections.map((section, index) => (
        <div key={index} className="community-sidebar__section">
          <h2 className="community-sidebar__section-title">
            {section.title}
          </h2>
          <ul className="community-sidebar__list">
            {section.items.map((item) => (
              <li key={item.id} className="community-sidebar__item">
                <button
                  className={`community-sidebar__button ${isActive(item.path) ? 'community-sidebar__button--active' : ''}`}
                  onClick={() => handleItemClick(item)}
                >
                  {item.icon && (
                    <span className="community-sidebar__icon">
                      {item.icon}
                    </span>
                  )}
                  <span className="community-sidebar__label">
                    {item.label}
                  </span>
                  {item.badge && (
                    <span className="community-sidebar__badge">
                      {item.badge}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}

      {/* Footer with additional actions */}
      <div className="community-sidebar__footer">
        <button
          className="community-sidebar__footer-button"
          onClick={() => console.log('Settings')}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2"/>
            <path d="M12 1V3M12 21V23M4.22 4.22L5.64 5.64M18.36 18.36L19.78 19.78M1 12H3M21 12H23M4.22 19.78L5.64 18.36M18.36 5.64L19.78 4.22" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          <span>Settings</span>
        </button>
        <button
          className="community-sidebar__footer-button"
          onClick={() => console.log('Help')}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
            <path d="M9.09 9C9.3251 8.33167 9.78915 7.76811 10.4 7.40913C11.0108 7.05016 11.7289 6.91894 12.4272 7.03871C13.1255 7.15849 13.7588 7.52152 14.2151 8.06353C14.6713 8.60553 14.9211 9.29152 14.92 10C14.92 12 11.92 13 11.92 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            <circle cx="12" cy="17" r="0.5" fill="currentColor" stroke="currentColor"/>
          </svg>
          <span>Help</span>
        </button>
      </div>
    </nav>
  );
};

export default CommunitySidebar;
