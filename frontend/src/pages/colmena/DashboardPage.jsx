import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { BookOpen, ClipboardCheck, ShieldCheck, RefreshCcw } from 'lucide-react';

import { getCensopasPlans } from '../../api/instruments.js';
import InstrumentConfirmModal from '../../components/colmena/projects/InstrumentConfirmModal.jsx';
import MultidisciplinaryCatalog from '../../components/colmena/instruments/MultidisciplinaryCatalog.jsx';
import { LoadingState } from '../../components/ui/LoadingState.jsx';
import { ErrorState } from '../../components/ui/ErrorState.jsx';
import { EmptyState } from '../../components/ui/EmptyState.jsx';

const VERSION_LABELS = {
  SHORT: 'CENSOPAS-COPSOQ, versión corta',
  MEDIUM: 'CENSOPAS-COPSOQ, versión media',
};

export function availableInstrumentCards(response) {
  const plans = Array.isArray(response?.plans) ? response.plans : [];
  const byKind = new Map();
  for (const plan of plans) {
    const kind = plan?.version_kind;
    if (!VERSION_LABELS[kind]) continue;
    // Only catalog items published in the database are selectable.
    // The backend reports readiness separately from version status.
    if (!byKind.has(kind) || (plan.ready_for_scoring && !byKind.get(kind).ready_for_scoring)) {
      byKind.set(kind, plan);
    }
  }
  return [...byKind.values()].sort((a, b) => a.version_kind.localeCompare(b.version_kind));
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [selectedInstrument, setSelectedInstrument] = useState(null);
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['censopas-plans'],
    queryFn: getCensopasPlans,
    retry: 1,
    staleTime: 60_000,
  });
  const cards = availableInstrumentCards(data);

  return (
    <div className="colmena-page space-y-5">
      <div className="rounded-xl border border-border bg-surface p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-amber">AURORA Professional · Instrumentos</p>
            <h1 className="mt-1 text-xl font-bold text-dark">Selecciona instrumentos</h1>
            <p className="mt-1 text-sm text-muted">
              Elige la evaluación que deseas aplicar. Los instrumentos deben estar publicados y contar con metodología configurada.
            </p>
          </div>
          <button type="button" onClick={() => refetch()} disabled={isFetching}
            className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-bold text-dark disabled:opacity-50">
            <RefreshCcw size={15} className={isFetching ? 'animate-spin' : ''} /> Actualizar catálogo
          </button>
        </div>
      </div>
      {isLoading ? <LoadingState label="Consultando instrumentos del servidor..." /> : null}
      {isError ? <ErrorState
        title="No se pudo cargar el catálogo"
        message={error?.message || 'Comprueba la conexión con el backend de AURORA.'}
      /> : null}
      {!isLoading && !isError && cards.length === 0 ? (
        <EmptyState
          title="No hay instrumentos publicados"
          description="El administrador debe verificar las versiones y ejecutar el proceso de publicación autorizado. No se mostrarán instrumentos ficticios."
        />
      ) : null}
      {!isLoading && !isError && cards.length > 0 ? (
        <section aria-label="Instrumentos publicados" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {cards.map((plan) => {
            const ready = plan.ready_for_scoring === true;
            const title = VERSION_LABELS[plan.version_kind];
            return (
              <article key={plan.instrument_version_id} className="flex flex-col justify-between gap-4 rounded-xl border border-border bg-surface p-5 shadow-sm">
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded-md border border-amber/20 bg-amber/10 px-2 py-1 text-xs font-semibold text-dark">
                      {ready ? 'Versión publicada' : 'Requiere validación'}
                    </span>
                    <ShieldCheck size={20} className="text-amber" />
                  </div>
                  <h2 className="text-base font-bold text-dark">{title}</h2>
                  <p className="text-sm text-muted">
                    {plan.question_count} preguntas, {plan.scored_item_count} ítems puntuables,
                    {' '}{plan.dimension_count} dimensiones y {plan.subdimension_count} subdimensiones.
                  </p>
                  <p className="text-xs text-muted">Versión: {plan.version_code}. La publicación no constituye acreditación de SUNAFIL.</p>
                </div>
                <button type="button" disabled={!ready} onClick={() => setSelectedInstrument({
                  id: plan.instrument_version_id,
                  title, version: plan.version_kind, items: plan.question_count,
                  duration: 'según el participante',
                  badge: 'Versión configurada en AURORA',
                  description: plan.plan_description || 'Evaluación empresarial basada en una versión del instrumento.',
                })}
                  className="inline-flex items-center justify-center gap-2 rounded-lg bg-amber px-4 py-2.5 text-sm font-bold text-dark disabled:cursor-not-allowed disabled:opacity-40">
                  <ClipboardCheck size={16} /> {ready ? 'Solicitar evaluación' : 'No disponible'}
                </button>
              </article>
            );
          })}
        </section>
      ) : null}
      <div className="rounded-xl border border-dashed border-border bg-surfaceSoft p-4 text-sm text-muted">
        <div className="flex items-start gap-3">
          <BookOpen size={20} className="mt-0.5 shrink-0 text-amber" />
          <p>Para otras evaluaciones multidisciplinarias, crea y valida primero el instrumento dentro del expediente empresarial.
            No se generarán encuestas CENSOPAS bajo el nombre de un método diferente.</p>
        </div>
      </div>
      <section aria-label="Catálogo multidisciplinario" className="space-y-3">
        <div className="rounded-xl border border-border bg-surface px-4 py-3">
          <h2 className="text-base font-bold text-dark">Otros instrumentos disponibles</h2>
          <p className="mt-1 text-xs text-muted">Consulta instrumentos multidisciplinarios. Para aplicarlos, crea una evaluación empresarial y vincula una versión autorizada.</p>
          <button type="button" className="mt-3 rounded-lg border border-amber px-3 py-2 text-xs font-semibold text-dark hover:bg-amber/10"
            onClick={() => navigate('/colmena/project/new')}>Crear evaluación multidisciplinaria</button>
        </div>
        <MultidisciplinaryCatalog />
      </section>
      {selectedInstrument && (
        <InstrumentConfirmModal instrument={selectedInstrument} isOpen
          onClose={() => setSelectedInstrument(null)}
          onCreated={(result) => {
            setSelectedInstrument(null);
            navigate(`/colmena/project/${result.project_id}/telemetry`);
          }}
        />
      )}
    </div>
  );
}
