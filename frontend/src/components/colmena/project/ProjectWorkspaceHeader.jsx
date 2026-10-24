import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronRight, Link as LinkIcon, Users } from 'lucide-react';

import { getProject } from '../../../api/projects.js';

/**
 * La navegación principal Inicio / Telemetría / Informe ya existe en
 * Sidebar y MobileJourneyNav. Evitar duplicarla en cada página del proyecto.
 */
export default function ProjectWorkspaceHeader({ projectId: explicitProjectId, actions }) {
  const { projectId: routeProjectId } = useParams();
  const projectId = explicitProjectId || routeProjectId;
  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
    enabled: Boolean(projectId),
  });

  return (
    <header className="mb-1 flex min-w-0 flex-wrap items-center justify-between gap-2 rounded-xl border border-[#E1E8F2] bg-white px-3 py-2 shadow-sm"
      aria-label="Contexto de evaluación empresarial">
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-1 text-[10px] font-semibold text-[#71829A]">
          <Link to="/colmena" className="hover:text-[#315A99]">Inicio</Link>
          <ChevronRight size={11} aria-hidden="true"/>
          <span className="truncate">Evaluación empresarial</span>
        </div>
        <h1 className="mt-0.5 truncate text-sm font-extrabold text-[#17365C]">
          {project?.name || 'Diagnóstico empresarial'}
        </h1>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {actions}
        {projectId && (
          <details className="group relative">
            <summary className="flex cursor-pointer list-none items-center gap-1 rounded-lg border border-[#D8E3EF] bg-[#F7FAFD] px-3 py-2 text-[11px] font-bold text-[#33547B] hover:bg-[#E9F2FB]">
              Gestionar <ChevronDown size={12} className="transition-transform group-open:rotate-180"/>
            </summary>
            <nav aria-label="Gestión de evaluación"
              className="absolute right-0 top-full z-40 mt-1 min-w-[190px] rounded-xl border border-[#DCE5F0] bg-white p-1.5 shadow-xl">
              <Link className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold text-[#284A70] hover:bg-[#EEF5FB]"
                to={`/colmena/project/${projectId}/link`}>
                <LinkIcon size={13}/> Campaña y enlaces
              </Link>
              <Link className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold text-[#284A70] hover:bg-[#EEF5FB]"
                to={`/colmena/project/${projectId}/team`}>
                <Users size={13}/> Equipo
              </Link>
            </nav>
          </details>
        )}
      </div>
    </header>
  );
}
