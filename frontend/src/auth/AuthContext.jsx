import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { demoLoginUser, fetchCurrentUser, loginUser, logoutUser, registerUser } from '../api/auth.js';
import { clearStoredToken } from '../api/client.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | authenticated | anonymous

  const loadCurrentUser = useCallback(async () => {
    try {
      const currentUser = await fetchCurrentUser();
      setUser(currentUser);
      setStatus('authenticated');
    } catch {
      clearStoredToken();
      setUser(null);
      setStatus('anonymous');
    }
  }, []);

  useEffect(() => {
    loadCurrentUser();
  }, [loadCurrentUser]);

  const login = useCallback(
    async ({ email, password }) => {
      await loginUser({ email, password });
      clearStoredToken();
      await loadCurrentUser();
    },
    [loadCurrentUser],
  );

  const demoLogin = useCallback(async () => {
    await demoLoginUser();
    clearStoredToken();
    await loadCurrentUser();
  }, [loadCurrentUser]);

  const signup = useCallback(async (payload) => {
    await registerUser(payload);
  }, []);

  const logout = useCallback(() => {
    logoutUser().catch(() => {});
    clearStoredToken();
    setUser(null);
    setStatus('anonymous');
  }, []);

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
