import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { LogOut, RefreshCcw, Settings2, Wifi, WifiOff, BarChart3, FileBarChart2, Home, Sparkles } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { API_ROOT_URL } from '../../api/client.js';
import { useAuth } from '../../auth/AuthContext.jsx';
import { setActiveProjectId } from '../../utils/activeProject.js';
import ThemeToggle from '../ui/ThemeToggle.jsx';
import { BrandMark } from '../../brand/BrandMark.jsx';
import { cn } from '../../utils/cn.js';

async function fetchHealth() {
  const response = await fetch(`${API_ROOT_URL}/health`);
  if (!response.ok) throw new Error('health check failed');
  return response.json();
}

/** Barra superior: identidad, conexión real al backend, configuración y sesión. */
export function Topbar() {
  const navigate = useNavigate();
  const location = useLocation();
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

  const isInicio = location.pathname === '/colmena' || location.pathname === '/colmena/' || location.pathname.endsWith('/instruments');
  const isTelemetry = location.pathname.includes('/telemetry') || location.pathname.includes('/results') || location.pathname.includes('/premium') || location.pathname.includes('/dashboard');
  const isReports = location.pathname.includes('/reports');

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
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-dark">AURORA Professional</p>
          <p className="text-[11px] text-muted hidden sm:block">Diagnóstico y evaluaciones corporativas</p>
        </div>

        {/* Navegación permanente en cabecera a las 3 pantallas */}
        <nav aria-label="Navegación principal" className="flex items-center gap-1">
          <Link
            to="/colmena"
            className={cn(
              "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition",
              isInicio ? "bg-amber/15 text-dark font-bold shadow-xs" : "text-muted hover:text-dark hover:bg-slate-100"
            )}
          >
            <Home size={14} />
            <span className="hidden sm:inline">1. Inicio</span>
          </Link>
          <Link
            to="/colmena/telemetry"
            className={cn(
              "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition",
              isTelemetry ? "bg-amber/15 text-dark font-bold shadow-xs" : "text-muted hover:text-dark hover:bg-slate-100"
            )}
          >
            <BarChart3 size={14} />
            <span className="hidden sm:inline">2. Telemetría</span>
            <span className="sm:hidden">BI</span>
          </Link>
          <Link
            to="/colmena/reports"
            className={cn(
              "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition",
              isReports ? "bg-amber/15 text-dark font-bold shadow-xs" : "text-muted hover:text-dark hover:bg-slate-100"
            )}
          >
            <FileBarChart2 size={14} />
            <span className="hidden sm:inline">3. Informe</span>
          </Link>
          <button
            type="button"
            onClick={() => {
              setActiveProjectId(23);
              navigate('/colmena/project/23/telemetry');
            }}
            className="ml-1 hidden md:inline-flex items-center gap-1.5 rounded-lg border border-[#9EE2EC] bg-[#EDF9FB] px-2.5 py-1 text-xs font-bold text-[#0E7176] hover:bg-[#DCF3F6] transition shadow-xs"
            title="Ver tablero de telemetría de la Unidad Minera San Cristóbal"
          >
            <Sparkles size={13} className="text-[#108B91]" />
            <span>⚡ Demo Minera</span>
          </button>
        </nav>

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
