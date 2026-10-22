import { Card } from '../../ui/Card.jsx';
import { EmptyState } from '../../ui/EmptyState.jsx';
import { LoadingState } from '../../ui/LoadingState.jsx';
import PremiumBIWorkspace from './PremiumBIWorkspace.jsx';
import TelemetryDimensionsSection from './TelemetryDimensionsSection.jsx';
import TelemetryOverview from './TelemetryOverview.jsx';

/**
 * Entrada única a la telemetría corporativa:
 * BI ejecutivo configurable primero; seguimiento y detalle quedan debajo.
 * Cada valor de riesgo se origina en el scoring del servidor.
 */
export default function TelemetryDashboard({ projectId, studyId, telemetry, descriptives, isLoadingTelemetry }) {
  if (!studyId) {
    return <Card><EmptyState title="Selecciona una evaluación" description="El tablero se organiza por campaña e instrumento." /></Card>;
  }
  if (isLoadingTelemetry) return <LoadingState label="Cargando diagnóstico…" />;
  if (!telemetry) {
    return <Card><EmptyState title="Sin datos de seguimiento" description="Selecciona una campaña con respuestas para consultar el diagnóstico." /></Card>;
  }
  return (
    <div className="flex flex-col gap-4">
      <PremiumBIWorkspace projectId={projectId} studyId={studyId} telemetry={telemetry} />
      <details className="rounded-xl border border-border bg-surface shadow-sm">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-dark focus-visible:outline-2 focus-visible:outline-amber">
          Seguimiento de participación y calidad <span aria-hidden="true" className="float-right text-muted">+</span>
        </summary>
        <div className="border-t border-border p-3">
          <TelemetryOverview descriptives={descriptives} isLoading={isLoadingTelemetry} telemetry={telemetry} />
        </div>
      </details>
      <details className="rounded-xl border border-border bg-surface shadow-sm">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-dark focus-visible:outline-2 focus-visible:outline-amber">
          Evidencia por pregunta <span aria-hidden="true" className="float-right text-muted">+</span>
        </summary>
        <div className="border-t border-border p-3">
          <TelemetryDimensionsSection descriptives={descriptives} isLoading={isLoadingTelemetry} />
        </div>
      </details>
    </div>
  );
}