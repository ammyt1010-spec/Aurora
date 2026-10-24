import { useState } from 'react';
import { BarChart3, ClipboardList, Activity, ChevronDown } from 'lucide-react';
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
}) {
  const [technical, setTechnical] = useState('none');

  if (!studyId) {
    return <Card><EmptyState title="Selecciona una evaluación" description="El diagnóstico se organiza por campaña e instrumento." /></Card>;
  }
  if (isLoadingTelemetry) return <LoadingState label="Cargando diagnóstico…" />;
  if (!telemetry) {
    return <Card><EmptyState title="Sin datos de seguimiento" description="Selecciona una campaña con respuestas para consultar el diagnóstico." /></Card>;
  }

  const views = [
    { id: 'monitor', label: 'Seguimiento de captura', icon: Activity },
    { id: 'questions', label: 'Evidencia por pregunta', icon: ClipboardList },
    { id: 'advanced', label: 'Explorador avanzado', icon: BarChart3 },
  ];
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <ExecutiveDecisionBoard projectId={projectId} studyId={studyId} telemetry={telemetry} />
      <div className="rounded-xl border border-[#E2E8F0] bg-white px-3 py-2 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 text-[11px] font-bold text-[#536985]">Herramientas técnicas</span>
          {views.map(({ id, label, icon: Icon }) => (
            <button key={id} type="button"
              aria-expanded={technical === id}
              onClick={() => setTechnical(technical === id ? 'none' : id)}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold transition-colors ${technical === id ?
                'border-[#BDDDEC] bg-[#EDF9FC] text-[#134F82]' :
                'border-[#E4EAF2] text-[#546D88] hover:bg-[#F5F9FD]'}`}>
              <Icon size={13}/>{label}<ChevronDown size={12} className={technical === id ? 'rotate-180' : ''}/>
            </button>
          ))}
        </div>
        {technical !== 'none' && <div className="mt-3 border-t border-[#E2E8F0] pt-3">
          {technical === 'monitor' && <TelemetryOverview telemetry={telemetry} descriptives={descriptives} isLoading={isLoadingTelemetry}/>}
          {technical === 'questions' && <TelemetryDimensionsSection descriptives={descriptives} isLoading={isLoadingTelemetry}/>}
          {technical === 'advanced' && <PremiumBIWorkspace projectId={projectId} organizationId={organizationId}
            studyId={studyId} telemetry={telemetry}/>}
        </div>}
      </div>
    </div>
  );
}
