import { BarChart3, FileText, Home } from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';

/** Navegación inferior consistente en pantallas pequeñas. */
export function MobileJourneyNav() {
  const location = useLocation();
  const routes = [
    { to: '/colmena', label: 'Inicio', Icon: Home, match: (p) => p === '/colmena' || p.endsWith('/instruments') },
    { to: '/colmena/telemetry', label: 'Telemetría', Icon: BarChart3, match: (p) => p.includes('/telemetry') || p.includes('/results') || p.includes('/premium') },
    { to: '/colmena/reports', label: 'Informe', Icon: FileText, match: (p) => p.includes('/reports') },
  ];
  return (
    <nav aria-label="Pantallas principales" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-3 border-t border-border bg-white/95 p-1 pb-[max(0.25rem,env(safe-area-inset-bottom))] shadow-lg backdrop-blur lg:hidden">
      {routes.map(({ to, label, Icon, match }) => {
        const selected = match(location.pathname);
        return (
          <NavLink key={to} to={to} aria-current={selected ? 'page' : undefined}
            className={`flex min-h-12 flex-col items-center justify-center gap-0.5 rounded-lg px-2 py-1 text-[11px] font-semibold ${selected ? 'bg-amber/15 text-dark' : 'text-muted'}`}>
            <Icon size={18} aria-hidden="true" />
            {label}
          </NavLink>
        );
      })}
    </nav>
  );
}
