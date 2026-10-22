import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { LogOut, RefreshCcw, Settings2, Wifi, WifiOff } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { API_ROOT_URL } from '../../api/client.js';
import { useAuth } from '../../auth/AuthContext.jsx';
import ThemeToggle from '../ui/ThemeToggle.jsx';
import { BrandMark } from '../../brand/BrandMark.jsx';

async function fetchHealth() {
  const response = await fetch(`${API_ROOT_URL}/health`);
  if (!response.ok) throw new Error('health check failed');
  return response.json();
}

/** Barra superior: identidad, conexión real al backend, configuración y sesión. */
export function Topbar() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState('');
  const { data, refetch, isFetching } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    retry: 1,
    refetchInterval: 30000,
  });

  const connected = data?.status?.toLowerCase() === 'ok';

  const handleLogout = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError('');
    try {
      await logout();
      navigate('/login', { replace: true });
    } catch {
      setLogoutError('No se pudo confirmar el cierre de sesión. Verifica tu conexión e inténtalo nuevamente.');
    } finally {
      setLoggingOut(false);
    }
  };

  const displayName = user?.first_name || user?.username || user?.email || 'Investigador';
  const initial = displayName.charAt(0).toUpperCase();

  return (
    <div className="sticky top-0 z-10 h-14 border-b border-[#eef0f3] bg-white/90 px-4 backdrop-blur-xl sm:px-5">
      {logoutError && (
        <div role="alert" className="absolute right-4 top-full z-30 mt-2 max-w-sm rounded-xl border border-red-200 bg-white p-3 text-sm text-red-700 shadow-lg">
          {logoutError}
        </div>
      )}
      <div className="flex h-full w-full items-center justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-bold text-dark">AURORA Professional</p>
          <p className="text-[11px] text-muted">Diagnóstico y evaluaciones corporativas</p>
        </div>

        <div className="flex items-center gap-2">
          <div
            className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium ${
              connected ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-500'
            }`}
          >
            {connected ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
            {connected ? 'API' : 'Sin API'}
          </div>

          <button
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#eef0f3] bg-white text-muted transition hover:bg-[#f5f6f8] hover:text-dark"
            onClick={() => refetch()}
            title="Refrescar conexión"
            type="button"
          >
            <RefreshCcw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />
          </button>

          <button
            aria-label="Administración"
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#eef0f3] bg-white text-muted transition hover:bg-[#f5f6f8] hover:text-dark"
            onClick={() => navigate('/colmena/settings')}
            title="Administración, tarifas y configuración"
            type="button"
          >
            <Settings2 className="h-4 w-4" />
          </button>

          <ThemeToggle />


          <div className="mx-1 h-6 w-px bg-[#eef0f3]" />

          <div className="flex items-center gap-2.5 rounded-xl px-2 py-1.5 transition hover:bg-[#f5f6f8]">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#00B9CD] to-[#6366F1] text-xs font-bold text-white">
              {initial}
            </div>
            <div className="text-left hidden lg:block">
              <p className="text-[13px] font-semibold text-dark leading-tight">{displayName}</p>
              <p className="text-[11px] text-muted leading-tight">{user?.email || 'Sin vincular'}</p>
            </div>
          </div>

          {user && (
            <button
              aria-label={loggingOut ? 'Cerrando sesión' : 'Cerrar sesión'}
              aria-busy={loggingOut}
              disabled={loggingOut}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#eef0f3] bg-white text-muted transition hover:bg-red-50 hover:text-red-500 disabled:cursor-wait disabled:opacity-50"
              onClick={handleLogout}
              title={loggingOut ? 'Cerrando sesión' : 'Cerrar sesión'}
              type="button"
            >
              <LogOut className={`h-3.5 w-3.5 ${loggingOut ? 'animate-pulse' : ''}`} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default Topbar;
