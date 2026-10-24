import { useCallback, useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Pause, Play, RefreshCcw } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import { getProject } from '../../../api/projects.js';
import { getResponseDescriptives, listStudies } from '../../../api/studies.js';
import { getProjectTelemetry } from '../../../api/telemetry.js';
import { useActiveProject } from '../../../hooks/useActiveProject.js';
import { displayLabel } from '../../../utils/labels.js';

import { Button } from '../../../components/ui/Button.jsx';
import { Card } from '../../../components/ui/Card.jsx';
import { EmptyState } from '../../../components/ui/EmptyState.jsx';
import { ErrorState } from '../../../components/ui/ErrorState.jsx';
import { LoadingState } from '../../../components/ui/LoadingState.jsx';
import { ProjectMissingState } from '../../../components/colmena/ProjectMissingState.jsx';
import TelemetryDashboard from '../../../components/colmena/telemetry/TelemetryDashboard.jsx';

function usePageVisibility() {
  const [visible, setVisible] = useState(() => document.visibilityState === 'visible');
  useEffect(() => {
    const update = () => setVisible(document.visibilityState === 'visible');
    document.addEventListener('visibilitychange', update);
    return () => document.removeEventListener('visibilitychange', update);
  }, []);
  return visible;
}

/**
 * Telemetría: participación y calidad de captura de las aplicaciones del
 * instrumento, con gráficos (embudo, estado de sesiones, evolución,
 * calidad de captura) y las preguntas con sus respuestas, agrupadas por
 * dimensión. La analítica avanzada (riesgo, segmentación, relaciones)
 * vive en Resultados, no aquí.
 */
export default function AdaptiveProjectTelemetryPage({ overrideProjectId }) {
  const params = useParams();
  const projectId = overrideProjectId || params.projectId;
  useActiveProject(projectId);
  const [studyId, setStudyId] = useState(null);
  const [paused, setPaused] = useState(false);
  const [technicalDetailsOpen, setTechnicalDetailsOpen] = useState(false);
  const setTechnicalDetailsVisibility = useCallback((visible) => setTechnicalDetailsOpen(visible), []);
  const pageVisible = usePageVisibility();
  const refetchInterval = !paused && pageVisible ? 15000 : false;

  const projectQuery = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });
  const studiesQuery = useQuery({
    queryKey: ['studies', projectId],
    queryFn: () => listStudies(projectId, { page: 1, pageSize: 100 }),
    enabled: Boolean(projectId),
  });
  const studies = studiesQuery.data?.items || [];

  useEffect(() => {
    if (!studyId && studies.length) {
      const preferred = studies.find((s) => s.id === 26 || (s.name && s.name.toLowerCase().includes('minero'))) || studies[0];
      setStudyId(preferred.id);
    }
    if (studyId && studies.length && !studies.some((study) => study.id === studyId)) {
      setStudyId(studies[0].id);
    }
  }, [studies, studyId]);

  const telemetryQuery = useQuery({
    queryKey: ['projectTelemetry', projectId],
    queryFn: () => getProjectTelemetry(projectId),
    enabled: Boolean(projectId),
    refetchInterval,
    refetchIntervalInBackground: false,
  });
  // Alimenta tanto el resumen de faltantes (summary.missing_pct/missing_cells)
  // como el desglose por pregunta de la sección Distribuciones más abajo.
  const descriptivesQuery = useQuery({
    queryKey: ['responseDescriptives', studyId],
    queryFn: () => getResponseDescriptives(studyId),
    enabled: Boolean(studyId && technicalDetailsOpen),
    refetchInterval: technicalDetailsOpen ? refetchInterval : false,
    refetchIntervalInBackground: false,
  });

  const selectedTelemetry = (telemetryQuery.data?.studies || []).find((study) => study.study_id === studyId);
  const isRefreshing = telemetryQuery.isFetching || (technicalDetailsOpen && descriptivesQuery.isFetching);
  const hasDataError = telemetryQuery.isError || (technicalDetailsOpen && descriptivesQuery.isError);

  const refresh = () => {
    telemetryQuery.refetch();
    if (studyId && technicalDetailsOpen) descriptivesQuery.refetch();
  };

  if (projectQuery.isLoading) return <LoadingState label="Cargando proyecto…" />;
  if (!projectQuery.data) return <ProjectMissingState />;

  return (
    <div className="colmena-page !gap-2">
      {hasDataError ? (
        <ErrorState
          message="Conservamos la última información disponible. Usa Actualizar para volver a intentar."
          title="No se pudo actualizar la telemetría"
        />
      ) : null}

      {!studyId && !studiesQuery.isLoading ? (
        <Card>
          <EmptyState title="Todavía no hay aplicaciones" description="Crea un estudio para comenzar a recibir telemetría." />
        </Card>
      ) : null}

      {studyId ? (
        <TelemetryDashboard
          onDetailsVisibilityChange={setTechnicalDetailsVisibility}
          projectId={projectId}
          organizationId={projectQuery.data?.organization_id}
          descriptives={descriptivesQuery.data}
          isLoadingTelemetry={telemetryQuery.isLoading}
          studyId={studyId}
          telemetry={selectedTelemetry}
          studies={studies}
          setStudyId={setStudyId}
          projectName={projectQuery.data?.name}
          onRefresh={refresh}
          isRefreshing={isRefreshing}
        />
      ) : null}
    </div>
  );
}
