import { Link, useLocation, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { BarChart3, ChevronRight, FileBarChart2, FolderKanban, Link as LinkIcon, Users } from 'lucide-react';

import { getProject } from '../../../api/projects.js';

/**
 * Tres pantallas para el usuario corporativo. La gestión de enlaces y
 * colaboradores permanece accesible como tarea auxiliar del proyecto.
 * projectId explícito cubre las rutas de módulo /colmena/telemetry.
 */
export default function ProjectWorkspaceHeader({ activeTab = 'telemetry', projectId: explicitProjectId, actions }) {
  const { projectId: routeProjectId } = useParams();
  const projectId = explicitProjectId || routeProjectId;
  const location = useLocation();
  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
    enabled: Boolean(projectId),
  });
  const navTabs = [
    { id: 'home', label: '1. Inicio', icon: FolderKanban, path: '/colmena' },
    { id: 'telemetry', label: '2. Telemetría', icon: BarChart3, path: projectId ? `/colmena/project/${projectId}/telemetry` : '/colmena/telemetry' },
    { id: 'reports', label: '3. Informe', icon: FileBarChart2, path: projectId ? `/colmena/project/${projectId}/reports` : '/colmena/reports' },
  ];
  return (
    <header className="mb-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface px-4 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1 text-[11px] text-muted">
            <Link className="hover:text-amber" to="/colmena">Inicio</Link>
            <ChevronRight size={12} />
            <span className="truncate">{project?.name || 'Evaluación'}</span>
          </div>
          <h1 className="mt-1 truncate text-base font-bold text-dark">{project?.name || 'Diagnóstico empresarial'}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {projectId ? (
            <>
              <Link className="rounded-lg border border-border px-3 py-2 text-xs font-semibold text-dark hover:bg-surfaceSoft" to={`/colmena/project/${projectId}/link`}>
                <LinkIcon className="mr-1 inline" size={13} /> Gestionar enlace
              </Link>
              <Link className="rounded-lg border border-border px-3 py-2 text-xs font-semibold text-dark hover:bg-surfaceSoft" to={`/colmena/project/${projectId}/team`}>
                <Users className="mr-1 inline" size={13} /> Equipo
              </Link>
            </>
          ) : null}
          {actions}
        </div>
      </div>
      <nav aria-label="Etapas de evaluación" className="grid grid-cols-3 gap-1 rounded-xl border border-border bg-surface p-1">
        {navTabs.map((tab) => {
          const Icon = tab.icon;
          const selected = tab.id === activeTab || (tab.id === 'reports' && location.pathname.includes('/reports')) || (tab.id === 'telemetry' && location.pathname.includes('/telemetry'));
          return (
            <Link key={tab.id} to={tab.path} aria-current={selected ? 'page' : undefined}
              className={`flex min-w-0 items-center justify-center gap-2 rounded-lg px-2 py-2.5 text-xs font-semibold transition ${selected ? 'bg-amber text-dark shadow-sm' : 'text-muted hover:bg-surfaceSoft hover:text-dark'}`}>
              <Icon size={15} />
              <span className="truncate">{tab.label}</span>
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
