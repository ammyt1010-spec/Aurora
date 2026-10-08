import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { FileBarChart2, BookOpen } from 'lucide-react';

import { listProjects } from '../../api/projects.js';
import { getActiveProjectId } from '../../utils/activeProject.js';
import { LoadingState } from '../../components/ui/LoadingState.jsx';
import { Card } from '../../components/ui/Card.jsx';
import ProjectReportsPage from './project/ProjectReportsPage.jsx';

export default function ReportsModulePage() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ['reports-module-projects'],
    queryFn: () => listProjects({ page: 1, pageSize: 50 }),
  });

  if (isLoading) return <LoadingState label="Cargando módulo de reportes..." />;

  const projects = data?.items ?? [];
  const storedId = getActiveProjectId();
  const activeProject = projects.find((p) => String(p.id) === String(storedId)) || projects[0];

  if (!activeProject) {
    return (
      <div className="colmena-page p-6 text-center space-y-4">
        <Card className="max-w-md mx-auto p-8 space-y-4 shadow-sm">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-amber/10 text-amber">
            <FileBarChart2 size={32} />
          </div>
          <h2 className="text-base font-bold text-dark">No hay informes emitidos aún</h2>
          <p className="text-xs text-muted leading-relaxed">
            Para generar y exportar reportes oficiales SUNAFIL, solicita un instrumento desde el Catálogo de Instrumentos.
          </p>
          <button
            type="button"
            onClick={() => navigate('/colmena')}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-amber text-dark font-bold text-xs shadow-sm transition hover:bg-amber-600"
          >
            <BookOpen size={16} />
            Ver Catálogo de Instrumentos
          </button>
        </Card>
      </div>
    );
  }

  // Render Reports for active project
  return <ProjectReportsPage overrideProjectId={activeProject.id} />;
}
