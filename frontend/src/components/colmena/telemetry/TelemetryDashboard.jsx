import { Card } from '../../ui/Card.jsx';
import { EmptyState } from '../../ui/EmptyState.jsx';
import { LoadingState } from '../../ui/LoadingState.jsx';
import ExecutiveReportDashboard from '../project/ExecutiveReportDashboard.jsx';
import DimensionDashboardTab from '../results/DimensionDashboardTab.jsx';
import TelemetryDimensionsSection from './TelemetryDimensionsSection.jsx';
import TelemetryOverview from './TelemetryOverview.jsx';

/**
 * La lectura principal responde: ¿qué riesgos hay y en qué dimensiones?
 * Los detalles por pregunta y el control de captura permanecen disponibles,
 * sin invadir la primera pantalla gerencial.
 * El backend continúa siendo la única fuente de scoring y clasificaciones.
 */
export default function TelemetryDashboard({ projectId, studyId, telemetry, descriptives, isLoadingTelemetry }) {
  if (!studyId) {
    return <Card><EmptyState title="Selecciona una evaluación" description="El diagnóstico se organiza por campaña e instrumento." /></Card>;
  }
  if (isLoadingTelemetry) return <LoadingState label="Cargando diagnóstico…" />;
  if (!telemetry) {
    return <Card><EmptyState title="Sin datos de seguimiento" description="Selecciona una campaña con respuestas para consultar el diagnóstico." /></Card>;
  }
  return (
    <div className="flex flex-col gap-4">
      <section aria-labelledby="diagnosis-heading" className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="diagnosis-heading" className="text-lg font-bold text-dark">Diagnóstico por dimensiones</h2>
            <p className="text-xs text-muted">Identifica los niveles de riesgo y las áreas prioritarias. Selecciona una dimensión para explorarla.</p>
          </div>
          <span className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-muted">
            {telemetry.valid_count ?? 0} respuestas válidas
          </span>
        </div>
        <ExecutiveReportDashboard studyId={studyId} />
        <Card className="overflow-hidden p-2 sm:p-3">
          <DimensionDashboardTab projectId={projectId} studyId={studyId} />
        </Card>
      </section>

      <details className="group rounded-xl border border-border bg-surface">
        <summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold text-dark focus-visible:outline-2 focus-visible:outline-amber">
          Seguimiento de participación y calidad de datos <span aria-hidden="true" className="float-right text-muted">+</span>
        </summary>
        <div className="border-t border-border p-3">
          <TelemetryOverview descriptives={descriptives} isLoading={isLoadingTelemetry} telemetry={telemetry} />
        </div>
      </details>

      <details className="group rounded-xl border border-border bg-surface">
        <summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold text-dark focus-visible:outline-2 focus-visible:outline-amber">
          Evidencia detallada por pregunta <span aria-hidden="true" className="float-right text-muted">+</span>
        </summary>
        <div className="border-t border-border p-3">
          <TelemetryDimensionsSection descriptives={descriptives} isLoading={isLoadingTelemetry} />
        </div>
      </details>
    </div>
  );
}
