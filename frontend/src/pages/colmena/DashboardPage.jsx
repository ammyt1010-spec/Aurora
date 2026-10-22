import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { BookOpen, ClipboardCheck, ShieldCheck, RefreshCcw, Sparkles, ArrowRight, FileText } from 'lucide-react';

import { getCensopasPlans } from '../../api/instruments.js';
import { listProjects } from '../../api/projects.js';
import { setActiveProjectId } from '../../utils/activeProject.js';
import '../../design/PremiumSurfaces.css';
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
  const { data: existingProjects } = useQuery({
    queryKey: ['aurora-home-projects'],
    queryFn: () => listProjects({ page: 1, pageSize: 50 }),
    retry: false,
  });
  const projectItems = existingProjects?.items || [];

  return (
    <div className="colmena-page aurora-premium-page space-y-4">
      <header className="aurora-suite-hero">
        <div className="aurora-suite-hero-copy">
          <span><Sparkles size={14} /> ETAPA 01 · AURORA PROFESSIONAL</span>
          <h1>Inicia tu diagnóstico.</h1>
          <p>Selecciona un instrumento publicado, configura la evaluación y accede al seguimiento visual desde Telemetría.</p>
        </div>
        <div className="aurora-suite-hero-icon" aria-hidden="true"><BookOpen size={34} /></div>
      </header>
      <div className="flex flex-wrap items-center justify-between gap-2 px-1">
        <div><h2 className="text-sm font-extrabold text-dark">Instrumentos disponibles</h2>
          <p className="text-xs text-muted">Versiones autorizadas y configuradas en el servidor.</p></div>
        <button type="button" onClick={() => refetch()} disabled={isFetching}
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-white px-3 py-2 text-xs font-bold text-dark shadow-sm disabled:opacity-50">
          <RefreshCcw size={15} className={isFetching ? 'animate-spin' : ''} /> Actualizar catálogo
        </button>
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
              <article key={plan.instrument_version_id} className="aurora-catalog-card flex flex-col justify-between gap-4 p-4 sm:p-5">
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
                  className="aurora-catalog-action inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm disabled:cursor-not-allowed disabled:opacity-40">
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
        <div className="aurora-catalog-aux px-4 py-3">
          <h2 className="text-base font-bold text-dark">Otros instrumentos disponibles</h2>
          <p className="mt-1 text-xs text-muted">Consulta instrumentos multidisciplinarios. Para aplicarlos, crea una evaluación empresarial y vincula una versión autorizada.</p>
          <button type="button" className="mt-3 rounded-lg border border-amber px-3 py-2 text-xs font-semibold text-dark hover:bg-amber/10"
            onClick={() => navigate('/colmena/project/new')}>Crear evaluación multidisciplinaria</button>
        </div>
        <MultidisciplinaryCatalog />
      </section>
      {projectItems.length > 0 && (
        <section aria-label="Mis evaluaciones corporativas" className="aurora-catalog-aux space-y-3 p-4">
          <div>
            <h2 className="text-sm font-extrabold text-[#233c6b]">Mis evaluaciones</h2>
            <p className="mt-1 text-xs text-muted">Continúa una campaña existente sin repetir su configuración.</p>
          </div>
          <div className="grid max-h-72 gap-2 overflow-y-auto sm:grid-cols-2 xl:grid-cols-3">
            {projectItems.map((project) => (
              <article key={project.id} className="flex min-w-0 flex-col gap-2 rounded-xl border border-[#e1e8f4] bg-white p-3 shadow-sm">
                <strong className="truncate text-xs text-[#263e66]" title={project.name}>{project.name}</strong>
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-2 text-[11px] font-bold text-[#284c8b]"
                    onClick={() => { setActiveProjectId(project.id); navigate('/colmena/telemetry'); }}>
                    <ArrowRight size={12}/> Telemetría
                  </button>
                  <button type="button" className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-2 text-[11px] font-bold text-[#284c8b]"
                    onClick={() => { setActiveProjectId(project.id); navigate('/colmena/reports'); }}>
                    <FileText size={12}/> Informe
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
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
