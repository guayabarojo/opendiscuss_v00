/**
 * CommunityRail.tsx - 56px icon rail for community/discussion navigation
 */

import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import './CommunityRail.css';

interface RailItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  path?: string;
  onClick?: () => void;
}

export const CommunityRail: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const railItems: RailItem[] = [
    {
      id: 'home',
      label: 'Home',
      path: '/',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M3 9L12 2L21 9V20C21 20.5304 20.7893 21.0391 20.4142 21.4142C20.0391 21.7893 19.5304 22 19 22H5C4.46957 22 3.96086 21.7893 3.58579 21.4142C3.21071 21.0391 3 20.5304 3 20V9Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M9 22V12H15V22" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
    },
    {
      id: 'discussions',
      label: 'Discussions',
      path: '/discussions/create',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
    },
    {
      id: 'reports',
      label: 'Reports',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M3 3H21C21.5523 3 22 3.44772 22 4V20C22 20.5523 21.5523 21 21 21H3C2.44772 21 2 20.5523 2 20V4C2 3.44772 2.44772 3 3 3Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M8 7H16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          <path d="M8 11H16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          <path d="M8 15H12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        </svg>
      ),
    },
  ];

  const handleItemClick = (item: RailItem) => {
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
    <nav className="community-rail" aria-label="Main navigation">
      <ul className="community-rail__list">
        {railItems.map((item) => (
          <li key={item.id} className="community-rail__item">
            <button
              className={`community-rail__button ${isActive(item.path) ? 'community-rail__button--active' : ''}`}
              onClick={() => handleItemClick(item)}
              aria-label={item.label}
              title={item.label}
            >
              <span className="community-rail__icon">
                {item.icon}
              </span>
            </button>
          </li>
        ))}
      </ul>

      {/* Divider */}
      <div className="community-rail__divider" />

      {/* Add Community/Discussion Button */}
      <div className="community-rail__footer">
        <button
          className="community-rail__button community-rail__button--add"
          onClick={() => navigate('/discussions/create')}
          aria-label="Create discussion"
          title="Create discussion"
        >
          <span className="community-rail__icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2"/>
              <path d="M12 8V16M8 12H16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </span>
        </button>
      </div>
    </nav>
  );
};

export default CommunityRail;
