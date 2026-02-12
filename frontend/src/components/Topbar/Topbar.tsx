/**
 * Topbar.tsx - Sticky header with search and navigation
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './Topbar.css';

export const Topbar: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      // Placeholder for search functionality
      console.log('Search:', searchQuery);
    }
  };

  return (
    <div className="topbar">
      <div className="topbar__left">
        <button
          className="topbar__logo"
          onClick={() => navigate('/')}
          aria-label="Home"
        >
          <svg
            width="32"
            height="32"
            viewBox="0 0 32 32"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <circle cx="16" cy="16" r="14" fill="var(--accent)" opacity="0.1" />
            <circle cx="16" cy="16" r="10" stroke="var(--accent)" strokeWidth="2" />
            <circle cx="12" cy="14" r="2" fill="var(--accent)" />
            <circle cx="20" cy="14" r="2" fill="var(--accent)" />
            <path
              d="M12 20 Q16 22 20 20"
              stroke="var(--accent)"
              strokeWidth="2"
              strokeLinecap="round"
              fill="none"
            />
          </svg>
          <span className="topbar__logo-text">OpenDiscuss</span>
        </button>
      </div>

      <div className="topbar__center">
        <form className="topbar__search" onSubmit={handleSearch}>
          <svg
            className="topbar__search-icon"
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <circle
              cx="9"
              cy="9"
              r="6"
              stroke="currentColor"
              strokeWidth="2"
            />
            <path
              d="M14 14L18 18"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
          <input
            type="search"
            className="topbar__search-input"
            placeholder="Search discussions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search"
          />
        </form>
      </div>

      <div className="topbar__right">
        <button
          className="topbar__action"
          onClick={() => navigate('/discussions/create')}
          aria-label="Create discussion"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M10 4V16M4 10H16"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>

        <button
          className="topbar__action"
          aria-label="Notifications"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M10 2C8 2 6 4 6 6V10L4 12V14H16V12L14 10V6C14 4 12 2 10 2Z"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinejoin="round"
            />
            <path
              d="M8 14V15C8 16.1046 8.89543 17 10 17C11.1046 17 12 16.1046 12 15V14"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>

        <button
          className="topbar__avatar"
          aria-label="User menu"
        >
          <svg
            width="32"
            height="32"
            viewBox="0 0 32 32"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <circle cx="16" cy="16" r="14" fill="var(--accent)" opacity="0.1" />
            <circle cx="16" cy="13" r="5" fill="var(--accent)" />
            <path
              d="M6 26C6 21 10 18 16 18C22 18 26 21 26 26"
              stroke="var(--accent)"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default Topbar;
