/**
 * Development User Switcher Component
 *
 * Allows switching between test users for development/testing.
 * Only visible in development mode.
 */

import { useState, useEffect } from 'react';
import './DevUserSwitcher.css';

interface TestUser {
  user_id: string;
  username: string;
  email: string;
  token: string;
}

interface TestUsers {
  host: TestUser;
  participant1: TestUser;
  participant2: TestUser;
  participant3: TestUser;
}

export function DevUserSwitcher() {
  const [isOpen, setIsOpen] = useState(false);
  const [currentUser, setCurrentUser] = useState<string | null>(null);
  const [users, setUsers] = useState<TestUsers | null>(null);

  // Only show in development
  if (import.meta.env.PROD) {
    return null;
  }

  // Load test users from localStorage or fetch from server
  useEffect(() => {
    const loadUsers = async () => {
      try {
        // Try to load from localStorage first
        const storedUsers = localStorage.getItem('test_users');
        if (storedUsers) {
          setUsers(JSON.parse(storedUsers));
        } else {
          // Try to fetch from server (if available)
          const response = await fetch('http://localhost:8000/api/v1/test/users');
          if (response.ok) {
            const data = await response.json();
            setUsers(data);
            localStorage.setItem('test_users', JSON.stringify(data));
          }
        }
      } catch (error) {
        console.warn('Could not load test users:', error);
      }
    };

    loadUsers();

    // Check current user from token
    const token = localStorage.getItem('auth_token');
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        setCurrentUser(payload.username);
      } catch (error) {
        console.warn('Could not decode token:', error);
      }
    }
  }, []);

  const switchUser = (role: keyof TestUsers) => {
    if (!users) return;

    const user = users[role];
    localStorage.setItem('auth_token', user.token);
    setCurrentUser(user.username);
    setIsOpen(false);

    // Reload page to apply new auth
    window.location.reload();
  };

  const clearUser = () => {
    localStorage.removeItem('auth_token');
    setCurrentUser(null);
    setIsOpen(false);
    window.location.reload();
  };

  return (
    <div className="dev-user-switcher">
      <button
        className="dev-switcher-toggle"
        onClick={() => setIsOpen(!isOpen)}
        title="Switch Test User"
      >
        <span className="dev-icon">👤</span>
        <span className="dev-label">
          {currentUser || 'No User'}
        </span>
      </button>

      {isOpen && (
        <div className="dev-switcher-panel">
          <div className="dev-switcher-header">
            <h3>Development User Switcher</h3>
            <button
              className="dev-close-btn"
              onClick={() => setIsOpen(false)}
            >
              ×
            </button>
          </div>

          <div className="dev-switcher-content">
            {users ? (
              <>
                <div className="dev-user-list">
                  <button
                    className={`dev-user-btn ${currentUser === users.host.username ? 'active' : ''}`}
                    onClick={() => switchUser('host')}
                  >
                    <span className="role-badge host">HOST</span>
                    <span className="username">{users.host.username}</span>
                    <span className="email">{users.host.email}</span>
                  </button>

                  <button
                    className={`dev-user-btn ${currentUser === users.participant1.username ? 'active' : ''}`}
                    onClick={() => switchUser('participant1')}
                  >
                    <span className="role-badge participant">PARTICIPANT</span>
                    <span className="username">{users.participant1.username}</span>
                    <span className="email">{users.participant1.email}</span>
                  </button>

                  <button
                    className={`dev-user-btn ${currentUser === users.participant2.username ? 'active' : ''}`}
                    onClick={() => switchUser('participant2')}
                  >
                    <span className="role-badge participant">PARTICIPANT</span>
                    <span className="username">{users.participant2.username}</span>
                    <span className="email">{users.participant2.email}</span>
                  </button>

                  <button
                    className={`dev-user-btn ${currentUser === users.participant3.username ? 'active' : ''}`}
                    onClick={() => switchUser('participant3')}
                  >
                    <span className="role-badge participant">PARTICIPANT</span>
                    <span className="username">{users.participant3.username}</span>
                    <span className="email">{users.participant3.email}</span>
                  </button>
                </div>

                <button
                  className="dev-clear-btn"
                  onClick={clearUser}
                >
                  Clear User (No Auth)
                </button>
              </>
            ) : (
              <div className="dev-no-users">
                <p>No test users loaded.</p>
                <p className="dev-hint">
                  Run <code>python create_test_users.py</code> to generate test users.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
