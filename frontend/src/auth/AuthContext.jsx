import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Navigate, useLocation } from 'react-router-dom';

import { demoLoginUser, fetchCurrentUser, loginUser, logoutUser, registerUser } from '../api/auth.js';
import { clearStoredToken } from '../api/client.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | authenticated | anonymous
  const authRequestVersion = useRef(0);
  const logoutPromise = useRef(null);

  const loadCurrentUser = useCallback(async () => {
    // Ignore late /auth/me responses from a previous login/logout transition.
    const version = ++authRequestVersion.current;
    try {
      const currentUser = await fetchCurrentUser();
      if (version === authRequestVersion.current) {
        setUser(currentUser);
        setStatus('authenticated');
      }
      return currentUser;
    } catch (error) {
      if (version === authRequestVersion.current) {
        clearStoredToken();
        queryClient.clear();
        setUser(null);
        setStatus('anonymous');
      }
      throw error;
    }
  }, [queryClient]);

  useEffect(() => {
    // The initial check may fail when the user is not logged in.
    loadCurrentUser().catch(() => {});
  }, [loadCurrentUser]);

  const login = useCallback(
    async ({ email, password }) => {
      await loginUser({ email, password });
      clearStoredToken();
      queryClient.clear();
      await loadCurrentUser();
    },
    [loadCurrentUser, queryClient],
  );

  const demoLogin = useCallback(async () => {
    await demoLoginUser();
    clearStoredToken();
    queryClient.clear();
    await loadCurrentUser();
  }, [loadCurrentUser, queryClient]);

  const signup = useCallback(async (payload) => {
    await registerUser(payload);
  }, []);

  const logout = useCallback(async () => {
    if (logoutPromise.current) return logoutPromise.current;

    // Do not announce logout or clear client state until the API confirms it.
    authRequestVersion.current += 1;
    const operation = (async () => {
      await logoutUser();
      clearStoredToken();
      queryClient.clear(); // Do not retain another business's cached data after logout.
      setUser(null);
      setStatus('anonymous');
    })();
    logoutPromise.current = operation;
    try {
      await operation;
    } finally {
      logoutPromise.current = null;
    }
  }, [queryClient]);

  const value = useMemo(
    () => ({ user, status, login, demoLogin, signup, logout }),
    [user, status, login, demoLogin, signup, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe usarse dentro de un <AuthProvider>');
  }
  return context;
}

export function ProtectedRoute({ children }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="colmena-card px-8 py-6 text-sm text-muted">Cargando…</div>
      </div>
    );
  }

  if (status === 'anonymous') {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
