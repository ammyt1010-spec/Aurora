import { useQuery } from '@tanstack/react-query';
import { Bell, LogOut, RefreshCcw, Search, Wifi, WifiOff } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { API_ROOT_URL } from '../../api/client.js';
import { useAuth } from '../../auth/AuthContext.jsx';
import ThemeToggle from '../ui/ThemeToggle.jsx';

async function fetchHealth() {
  const response = await fetch(`${API_ROOT_URL}/health`);
  if (!response.ok) throw new Error('health check failed');
  return response.json();
}

/**
 * Portado de fullProyect/COLMENA/frontend (Topbar.tsx). El buscador y la
 * campana de notificaciones son decorativos (igual que en el original) — el
 * indicador de API sí es real, contra nuestro GET /health.
 */
export function Topbar() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { data, refetch, isFetching } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    retry: 1,
    refetchInterval: 30000,
  });

  const connected = data?.status?.toLowerCase() === 'ok';

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const displayName = user?.first_name || user?.username || user?.email || 'Investigador';
  const initial = displayName.charAt(0).toUpperCase();

  return (
    <div className="sticky top-0 z-10 h-14 border-b border-[#eef0f3] bg-white/90 px-4 backdrop-blur-xl sm:px-5">
      <div className="flex h-full w-full items-center justify-between gap-4">
        <div className="flex min-w-0 flex-1 items-center">
          <div className="group flex h-9 min-w-0 w-full max-w-[520px] items-center gap-2.5 rounded-xl border border-[#eef0f3] bg-[#f8f9fb] px-3 transition-all hover:border-[#dfe2e6] hover:bg-white focus-within:border-amber focus-within:bg-white focus-within:ring-2 focus-within:ring-amber/10">
            <Search className="h-4 w-4 shrink-0 text-muted/50" />
            <input
              className="min-w-0 flex-1 bg-transparent text-sm text-dark placeholder:text-muted/50 outline-none"
              placeholder="Buscar proyectos, formularios o respuestas..."
              type="text"
            />
          </div>
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

          <ThemeToggle />

          <button
            aria-label="Notificaciones"
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#eef0f3] bg-white text-muted transition hover:bg-[#f5f6f8] hover:text-dark"
            type="button"
          >
            <Bell className="h-3.5 w-3.5" />
          </button>

          <div className="mx-1 h-6 w-px bg-[#eef0f3]" />

          <div className="flex items-center gap-2.5 rounded-xl px-2 py-1.5 transition hover:bg-[#f5f6f8]">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-amber to-honey text-xs font-bold text-white">
              {initial}
            </div>
            <div className="text-left hidden lg:block">
              <p className="text-[13px] font-semibold text-dark leading-tight">{displayName}</p>
              <p className="text-[11px] text-muted leading-tight">{user?.email || 'Sin vincular'}</p>
            </div>
          </div>

          {user && (
            <button
              aria-label="Cerrar sesión"
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#eef0f3] bg-white text-muted transition hover:bg-red-50 hover:text-red-500"
              onClick={handleLogout}
              title="Cerrar sesión"
              type="button"
            >
              <LogOut className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default Topbar;
