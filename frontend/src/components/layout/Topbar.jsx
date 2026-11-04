import { useState } from 'react';
import { LogOut, Settings2, BarChart3, FileBarChart2, Home } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../../auth/AuthContext.jsx';
import ThemeToggle from '../ui/ThemeToggle.jsx';
import { cn } from '../../utils/cn.js';
import { ColmenaMenuButton } from './ColmenaMenuButton.jsx';

/** Barra superior compacta: identidad, navegación móvil, configuración y sesión. */
export function Topbar({ collapsed = false, onToggleMenu }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState('');
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
    <div className="sticky top-0 z-10 h-11 border-b border-[#eef0f3] bg-white/90 px-3 backdrop-blur-xl sm:px-4">
      {logoutError && (
        <div role="alert" className="absolute right-4 top-full z-30 mt-2 max-w-sm rounded-xl border border-red-200 bg-white p-3 text-sm text-red-700 shadow-lg">
          {logoutError}
        </div>
      )}
      <div className="flex h-full w-full items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          {collapsed && <ColmenaMenuButton onClick={onToggleMenu} title="Mostrar menú" ariaExpanded={false}
            className="hidden rounded-lg border border-[#E6E8EB] bg-white p-2 lg:inline-flex" />}
          <p className="truncate text-sm font-bold text-dark">AURORA Professional</p>
        </div>

        {/* En escritorio la navegación vive en el menú lateral; aquí solo aparece en móvil. */}
        <nav aria-label="Navegación principal" className="flex items-center gap-1 lg:hidden">
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
        </nav>

        <div className="flex items-center gap-2">
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
