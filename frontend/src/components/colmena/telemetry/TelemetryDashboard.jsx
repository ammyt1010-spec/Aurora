import { Card } from '../../ui/Card.jsx';
import { EmptyState } from '../../ui/EmptyState.jsx';
import { LoadingState } from '../../ui/LoadingState.jsx';
import TelemetryDimensionsSection from './TelemetryDimensionsSection.jsx';
import TelemetryOverview from './TelemetryOverview.jsx';

/**
 * Telemetría: participación y calidad de captura, con gráficos (embudo,
 * estado de sesiones, evolución, calidad). Debajo, las preguntas y sus
 * respuestas agrupadas por dimensión — la analítica avanzada (segmentación,
 * correlaciones, priorización) vive en Resultados.
 */
export default function TelemetryDashboard({ studyId, telemetry, descriptives, isLoadingTelemetry, isLoadingDescriptives }) {
  if (!studyId) {
    return (
      <Card>
        <EmptyState description="La telemetría se calcula por cada aplicación del instrumento." title="Elige una aplicación o estudio." />
      </Card>
    );
  }
  if (isLoadingTelemetry) return <LoadingState label="Cargando telemetría…" />;
  if (!telemetry) {
    return (
      <Card>
        <EmptyState description="Elige una aplicación con sesiones para ver el resumen." title="Todavía no hay telemetría" />
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <TelemetryOverview descriptives={descriptives} isLoading={isLoadingTelemetry} telemetry={telemetry} />

      <div className="flex flex-col gap-3">
        <div>
          <p className="text-sm font-semibold text-dark">Dimensiones</p>
          <p className="text-xs text-muted">Preguntas y respuestas, agrupadas por dimensión.</p>
        </div>
        <TelemetryDimensionsSection descriptives={descriptives} isLoading={isLoadingDescriptives} />
      </div>
    </div>
  );
}
