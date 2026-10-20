import {
  BarChart3,
  BookOpen,
  FileBarChart2,
  Gift,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { listProjects } from '../../api/projects.js';
import { BrandLogo } from '../../brand/BrandLogo.jsx';
import { cn } from '../../utils/cn.js';
import { getActiveProjectId, setActiveProjectId } from '../../utils/activeProject.js';
import { ColmenaMenuButton } from './ColmenaMenuButton.jsx';

export function Sidebar({ collapsed = false, onToggle }) {
  const location = useLocation();
  const navigate = useNavigate();

  const match = location.pathname.match(/^\/colmena\/project\/([a-zA-Z0-9-]+)/);
  const routeProjectId = match ? match[1] : null;

  const projectsQuery = useQuery({
    queryKey: ['sidebar-projects'],
    queryFn: () => listProjects({ page: 1, pageSize: 50 }),
  });
  const projects = projectsQuery.data?.items ?? [];

  const fallbackProjectId = projects[0]?.id;
  const activeProjectId = (routeProjectId && routeProjectId !== 'new') ? routeProjectId : (getActiveProjectId() || fallbackProjectId);

  const hasProject = Boolean(activeProjectId);

  const navItems = [
    {
      to: '/colmena',
      label: 'Catálogo de Instrumentos',
      icon: BookOpen,
      active: (p) => p === '/colmena' || p === '/colmena/',
    },
    {
      to: '/colmena/telemetry',
      label: 'Telemetría en Vivo',
      icon: BarChart3,
      active: (p) => p.includes('/telemetry'),
    },
    {
      to: '/colmena/reports',
      label: 'Reporte PDF SUNAFIL',
      icon: FileBarChart2,
      active: (p) => p.includes('/reports'),
    },
  ];

  return (
    <aside
      className={cn(
        'hidden shrink-0 overflow-hidden transition-[width] duration-200 ease-in-out lg:block',
        collapsed ? 'lg:w-0' : 'lg:w-[264px]',
      )}
    >
      <div
        className={cn(
          'sticky top-0 flex h-screen w-[264px] flex-col border-r border-white/70 bg-white/75 shadow-[12px_0_40px_rgba(37,33,80,0.04)] backdrop-blur-2xl transition-opacity duration-150',
          collapsed && 'pointer-events-none opacity-0',
        )}
      >
        <div className="border-b border-slate-200/70 px-5 pb-4 pt-5">
          <div className="flex items-start justify-between gap-2">
            <BrandLogo />
            <ColmenaMenuButton
              onClick={() => onToggle?.()}
              title="Contraer menú"
              className="mt-0.5 rounded-lg p-1.5 hover:bg-[#F5F6F8]"
            />
          </div>
          <p className="mt-2 flex items-center gap-1.5 text-[10px] font-bold tracking-wide text-slate-500">
            <ShieldCheck size={11} className="text-emerald-500" /> Gobierno y analítica laboral
          </p>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 pt-4 space-y-1">
          <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.12em] text-muted/60">
            Centro de control
          </p>
          {navItems.map((item) => {
            const isActive = item.active(location.pathname);
            return (
              <Link
                key={item.label}
                to={item.to}
                className={cn(
                  'group flex h-10 items-center gap-3 rounded-xl px-3 text-[13px] font-medium transition-all duration-150',
                  isActive
                    ? 'bg-gradient-to-r from-violet-500/15 to-cyan-500/10 text-violet-800 font-bold shadow-sm ring-1 ring-violet-300/30'
                    : 'text-muted hover:bg-white/80 hover:text-dark',
                )}
              >
                <item.icon
                  className={cn(
                    'h-[18px] w-[18px] shrink-0 transition-colors',
                    isActive ? 'text-violet-600' : 'text-muted/60 group-hover:text-muted',
                  )}
                  strokeWidth={isActive ? 2.2 : 1.8}
                />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="m-3 rounded-2xl border border-violet-200/60 bg-gradient-to-br from-violet-50 to-cyan-50 p-3.5 text-[11px] text-slate-600 shadow-sm">
          <p className="flex items-center gap-1.5 font-extrabold text-slate-950">
            <Gift size={13} className="text-violet-600" /> Primer informe gratuito
          </p>
          <p className="mt-1 text-[10px] leading-4">Acceso completo para que la empresa valide Aurora antes de escalar.</p>
        </div>
        <div className="border-t border-slate-200/70 px-4 py-3 text-[10px] text-muted">
          <p className="flex items-center gap-1.5 font-bold text-dark">
            <Sparkles size={11} className="text-violet-500" /> Aurora Intelligence
          </p>
          <p className="mt-1">Ley 29783 · R.M. 375-2008-TR</p>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
