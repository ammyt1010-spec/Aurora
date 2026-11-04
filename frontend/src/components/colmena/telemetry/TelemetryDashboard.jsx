import { useEffect, useState } from 'react';
import { Card } from '../../ui/Card.jsx';
import { EmptyState } from '../../ui/EmptyState.jsx';
import { LoadingState } from '../../ui/LoadingState.jsx';
import ExecutiveDecisionBoard from './ExecutiveDecisionBoard.jsx';
import PremiumBIWorkspace from './PremiumBIWorkspace.jsx';
import TelemetryDimensionsSection from './TelemetryDimensionsSection.jsx';
import TelemetryOverview from './TelemetryOverview.jsx';

/**
 * La vista gerencial es el contenido principal. Los paneles de ingeniería
 * permanecen disponibles, pero sus consultas y gráficos NO se montan
 * hasta que el usuario solicita el detalle explícitamente.
 */
export default function TelemetryDashboard({
  projectId, organizationId, studyId, telemetry, descriptives, isLoadingTelemetry,
  onDetailsVisibilityChange, studies, setStudyId, projectName, onRefresh, isRefreshing,
  projects, onProjectChange,
}) {
  const [technical, setTechnical] = useState('none');
  useEffect(() => setTechnical('none'), [studyId]);
  useEffect(() => {
    onDetailsVisibilityChange?.(technical === 'monitor' || technical === 'questions');
  }, [technical, onDetailsVisibilityChange]);

  if (!studyId) {
    return <Card><EmptyState title="Selecciona una evaluación" description="El diagnóstico se organiza por campaña e instrumento." /></Card>;
  }
  if (isLoadingTelemetry) return <LoadingState label="Cargando diagnóstico…" />;
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <ExecutiveDecisionBoard
        projectId={projectId}
        studyId={studyId}
        telemetry={telemetry}
        studies={studies}
        setStudyId={setStudyId}
        projectName={projectName}
        projects={projects}
        onProjectChange={onProjectChange}
        onRefresh={onRefresh}
        isRefreshing={isRefreshing}
        technicalControl={<select aria-label="Herramientas técnicas" value={technical}
          onChange={(event) => setTechnical(event.target.value)}>
          <option value="none">Explorar datos</option>
          <option value="monitor">Seguimiento de captura</option>
          <option value="questions">Evidencia por pregunta</option>
          <option value="advanced">Explorador avanzado</option>
        </select>}
      />
      {technical !== 'none' && <div className="rounded-xl border border-[#E2E8F0] bg-white p-3 shadow-sm">
          {technical === 'monitor' && <TelemetryOverview telemetry={telemetry} descriptives={descriptives} isLoading={isLoadingTelemetry}/>}
          {technical === 'questions' && <TelemetryDimensionsSection descriptives={descriptives} isLoading={isLoadingTelemetry}/>}
          {technical === 'advanced' && <PremiumBIWorkspace projectId={projectId} organizationId={organizationId}
            studyId={studyId} telemetry={telemetry}/>}
      </div>}
    </div>
  );
}
