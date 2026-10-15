import {
  BarChart3,
  BookOpen,
  FileBarChart2,
  Home,
  LayoutDashboard,
  Sparkles,
  Settings2,
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
      label: 'Informes profesionales',
      icon: FileBarChart2,
      active: (p) => p.includes('/reports'),
    },
    {
      to: '/colmena/settings',
      label: 'Administración y tarifas',
      icon: Settings2,
      active: (p) => p.startsWith('/colmena/settings'),
    },
  ];

  return (
    <aside
      className={cn(
        'hidden shrink-0 overflow-hidden transition-[width] duration-200 ease-in-out lg:block',
        collapsed ? 'lg:w-0' : 'lg:w-[240px]',
      )}
    >
      <div
        className={cn(
          'sticky top-0 flex h-screen w-[240px] flex-col bg-white border-r border-[#E6E8EB] transition-opacity duration-150',
          collapsed && 'pointer-events-none opacity-0',
        )}
      >
        <div className="px-5 pt-5 pb-4 border-b border-[#E6E8EB]/60">
          <div className="flex items-start justify-between gap-2">
            <BrandLogo />
            <ColmenaMenuButton
              onClick={() => onToggle?.()}
              title="Contraer menú"
              className="mt-0.5 rounded-lg p-1.5 hover:bg-[#F5F6F8]"
            />
          </div>
          <p className="mt-1 text-[11px] font-semibold text-amber tracking-wide">
            Evaluaciones empresariales
          </p>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 pt-4 space-y-1">
          <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.12em] text-muted/60">
            Módulos AURORA PRO
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
                    ? 'bg-amber/15 text-dark font-bold shadow-sm ring-1 ring-amber/30'
                    : 'text-muted hover:bg-[#F5F6F8] hover:text-dark',
                )}
              >
                <item.icon
                  className={cn(
                    'h-[18px] w-[18px] shrink-0 transition-colors',
                    isActive ? 'text-amber' : 'text-muted/60 group-hover:text-muted',
                  )}
                  strokeWidth={isActive ? 2.2 : 1.8}
                />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Footer info */}
        <div className="p-4 border-t border-[#E6E8EB] bg-[#FAFAF8] text-[11px] text-muted space-y-1">
          <p className="font-bold text-dark flex items-center gap-1">
            <Sparkles size={12} className="text-amber" /> AURORA PRO v3.0
          </p>
          <p className="text-[10px]">Plataforma web privada · Multidisciplinaria</p>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
