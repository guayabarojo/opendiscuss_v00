import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import type { Discussion } from '../types/api';

interface User {
  user_id: string;
  username?: string;
  email?: string;
}

interface AuthContextType {
  user: User | null;
  isHost: (discussion: Discussion) => boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function decodeJWT(token: string): User | null {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );

    const payload = JSON.parse(jsonPayload);

    return {
      user_id: payload.user_id || payload.participant_id || payload.sub,
      username: payload.username,
      email: payload.email,
    };
  } catch (error) {
    console.error('Failed to decode JWT:', error);
    return null;
  }
}

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      const decoded = decodeJWT(token);
      setUser(decoded);
    }
  }, []);

  const login = (token: string) => {
    localStorage.setItem('auth_token', token);
    const decoded = decodeJWT(token);
    setUser(decoded);
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    setUser(null);
  };

  const isHost = (discussion: Discussion): boolean => {
    if (!user || !discussion) return false;
    return user.user_id === discussion.host_user_id;
  };

  return (
    <AuthContext.Provider value={{ user, isHost, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
