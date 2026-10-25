import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  BookOpen,
  ClipboardCheck,
  Layers3,
  RefreshCcw,
  ArrowRight,
  FileText,
  Plus,
  ShieldCheck,
} from 'lucide-react';

import { getCensopasPlans } from '../../api/instruments.js';
import { listProjects } from '../../api/projects.js';
import { setActiveProjectId } from '../../utils/activeProject.js';
import '../../design/PremiumSurfaces.css';
import InstrumentConfirmModal from '../../components/colmena/projects/InstrumentConfirmModal.jsx';
import MultidisciplinaryCatalog from '../../components/colmena/instruments/MultidisciplinaryCatalog.jsx';
import DirectCatalogBatteryPanel from '../../components/colmena/instruments/DirectCatalogBatteryPanel.jsx';
import CatalogCampaignModal from '../../components/colmena/instruments/CatalogCampaignModal.jsx';
import BundleSelectionPanel from '../../components/colmena/instruments/BundleSelectionPanel.jsx';
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
    if (
      !byKind.has(kind) ||
      (plan.ready_for_scoring && !byKind.get(kind).ready_for_scoring)
    ) {
      byKind.set(kind, plan);
    }
  }
  return [...byKind.values()].sort((a, b) =>
    a.version_kind.localeCompare(b.version_kind),
  );
}

/**
 * Inicio corporativo: la selección de empresa y batería por casillas de verificación
 * es el contenido primordial. El catálogo general solo se abre si el usuario desea
 * explorar o si aún no hay proyectos creados.
 */
export default function DashboardPage() {
  const navigate = useNavigate();
  const [selectedInstrument, setSelectedInstrument] = useState(null);
  const [catalogInstrument, setCatalogInstrument] = useState(null);
  const [catalog, setCatalog] = useState('censopas');
  const [showProjects, setShowProjects] = useState(false);
  const [showCatalog, setShowCatalog] = useState(false);
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['censopas-plans'],
    queryFn: getCensopasPlans,
    retry: 1,
    staleTime: 60_000,
  });
  const { data: existingProjects, isError: projectsError } = useQuery({
    queryKey: ['aurora-home-projects'],
    queryFn: () => listProjects({ page: 1, pageSize: 50 }),
    retry: false,
  });
  const cards = availableInstrumentCards(data);
  const projectItems = existingProjects?.items || [];
  const catalogVisible = showCatalog || projectItems.length === 0;

  return (
    <div className="colmena-page aurora-premium-page aurora-home-focus !gap-2 !py-2">
      <header className="aurora-suite-hero aurora-home-hero !min-h-0 !py-2.5 !px-4">
        <div className="aurora-suite-hero-copy">
          <span className="!text-[10px]">
            01 / INICIO · AURORA PROFESSIONAL
          </span>
          <h1 className="!my-0.5 !text-base">¿Qué deseas evaluar?</h1>
          <p className="!text-[11px] text-[#c8d5ea]">
            Selecciona la empresa y marca los instrumentos para generar su
            enlace y código QR.
          </p>
        </div>
        <div
          className="aurora-suite-hero-icon !w-10 !h-10 !rounded-xl"
          aria-hidden="true"
        >
          <BookOpen size={18} />
        </div>
      </header>

      <DirectCatalogBatteryPanel projects={projectItems} />
      <details className="rounded-lg border bg-white p-3">
        <summary className="cursor-pointer text-xs font-semibold">
          Enlaces de campañas ya abiertas
        </summary>
        <BundleSelectionPanel projects={projectItems} />
      </details>
      <div className="aurora-home-toolbar">
        {catalogVisible && (
          <div
            role="tablist"
            aria-label="Catálogo de instrumentos"
            className="aurora-home-tabs"
          >
            <button
              type="button"
              role="tab"
              id="aurora-tab-censopas"
              aria-selected={catalog === 'censopas'}
              aria-controls="aurora-catalog-view"
              className={catalog === 'censopas' ? 'is-active' : ''}
              onClick={() => setCatalog('censopas')}
            >
              <ShieldCheck size={15} /> Psicosocial
            </button>
            <button
              type="button"
              role="tab"
              id="aurora-tab-multidisc"
              aria-selected={catalog === 'multidisc'}
              aria-controls="aurora-catalog-view"
              className={catalog === 'multidisc' ? 'is-active' : ''}
              onClick={() => setCatalog('multidisc')}
            >
              <Layers3 size={15} /> Multidisciplinario
            </button>
          </div>
        )}
        <div className="aurora-home-actions">
          {projectItems.length > 0 && (
            <button
              type="button"
              className="aurora-home-action"
              onClick={() => setShowCatalog((value) => !value)}
              aria-expanded={catalogVisible}
            >
              {catalogVisible ? 'Ocultar catálogo' : 'Explorar catálogo'}
            </button>
          )}
          {projectItems.length > 0 && (
            <button
              type="button"
              aria-expanded={showProjects}
              onClick={() => setShowProjects((x) => !x)}
              className="aurora-home-action"
            >
              Mis evaluaciones{' '}
              <span className="aurora-home-counter">{projectItems.length}</span>
            </button>
          )}
          <button
            type="button"
            className="aurora-home-action is-primary"
            onClick={() => navigate('/colmena/project/new')}
          >
            <Plus size={15} /> Nueva evaluación
          </button>
        </div>
      </div>

      {projectsError && (
        <p role="status" className="text-xs text-muted">
          Las evaluaciones guardadas no están disponibles en este momento.
        </p>
      )}

      {showProjects && projectItems.length > 0 && (
        <section
          aria-label="Mis evaluaciones corporativas"
          className="aurora-home-projects"
        >
          <div className="aurora-home-section-head">
            <h2>Evaluaciones existentes</h2>
            <span>Selecciona la pantalla que necesitas</span>
          </div>
          <div className="aurora-home-project-scroll">
            {projectItems.map((project) => (
              <article key={project.id} className="aurora-home-project">
                <strong title={project.name}>{project.name}</strong>
                <div>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveProjectId(project.id);
                      navigate('/colmena/telemetry');
                    }}
                  >
                    <ArrowRight size={12} /> Telemetría
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveProjectId(project.id);
                      navigate('/colmena/reports');
                    }}
                  >
                    <FileText size={12} /> Informe
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {catalogVisible && (
        <section
          id="aurora-catalog-view"
          role="tabpanel"
          aria-labelledby={
            catalog === 'censopas'
              ? 'aurora-tab-censopas'
              : 'aurora-tab-multidisc'
          }
          className="aurora-home-catalog"
          key={catalog}
        >
          {catalog === 'censopas' ? (
            <>
              <div className="aurora-home-section-head">
                <h2>Instrumentos publicados</h2>
                <button
                  type="button"
                  disabled={isFetching}
                  onClick={() => refetch()}
                  aria-label="Actualizar catálogo"
                  className="aurora-home-refresh"
                >
                  <RefreshCcw
                    size={14}
                    className={isFetching ? 'animate-spin' : ''}
                  />{' '}
                  Actualizar
                </button>
              </div>
              {isLoading ? (
                <LoadingState label="Consultando instrumentos del servidor..." />
              ) : null}
              {isError ? (
                <ErrorState
                  title="No se pudo cargar el catálogo"
                  message={
                    error?.message ||
                    'Comprueba la conexión con el backend de AURORA.'
                  }
                />
              ) : null}
              {!isLoading && !isError && !cards.length ? (
                <EmptyState
                  title="No hay instrumentos publicados"
                  description="El administrador debe validar las versiones y su metodología antes de habilitarlas."
                />
              ) : null}
              {!isLoading && !isError && cards.length > 0 && (
                <div className="aurora-home-instrument-grid">
                  {cards.map((plan) => {
                    const ready = plan.ready_for_scoring === true;
                    const title = VERSION_LABELS[plan.version_kind];
                    return (
                      <article
                        key={plan.instrument_version_id}
                        className="aurora-catalog-card aurora-home-instrument"
                      >
                        <div className="aurora-home-instrument-data">
                          <span
                            className={
                              ready
                                ? 'aurora-home-state is-ready'
                                : 'aurora-home-state'
                            }
                          >
                            {ready
                              ? 'Lista para aplicar'
                              : 'Requiere validación'}
                          </span>
                          <h3>{title}</h3>
                          <p>
                            {plan.question_count} preguntas,{' '}
                            {plan.scored_item_count} ítems puntuables ·{' '}
                            {plan.dimension_count} dimensiones ·{' '}
                            {plan.subdimension_count} subdimensiones
                          </p>
                          <small>
                            Versión {plan.version_code} · La clasificación
                            depende del baremo configurado.
                          </small>
                        </div>
                        <button
                          type="button"
                          disabled={!ready}
                          className="aurora-catalog-action aurora-home-start"
                          onClick={() =>
                            setSelectedInstrument({
                              id: plan.instrument_version_id,
                              title,
                              version: plan.version_kind,
                              items: plan.question_count,
                              duration: 'según el participante',
                              badge: 'Versión configurada en AURORA',
                              description:
                                plan.plan_description ||
                                'Evaluación empresarial basada en una versión del instrumento.',
                            })
                          }
                        >
                          <ClipboardCheck size={15} />
                          {ready ? 'Aplicar instrumento' : 'No disponible'}
                        </button>
                      </article>
                    );
                  })}
                </div>
              )}
            </>
          ) : (
            <div className="aurora-home-multidisc">
              <div className="aurora-home-section-head">
                <div>
                  <h2>Evaluaciones multidisciplinarias</h2>
                  <span>
                    Selecciona un método autorizado y vincúlalo a su evaluación
                    empresarial.
                  </span>
                </div>
              </div>
              <MultidisciplinaryCatalog
                simpleMode
                onCreateEvaluation={setCatalogInstrument}
              />
            </div>
          )}
        </section>
      )}
      {catalogInstrument && (
        <CatalogCampaignModal
          instrument={catalogInstrument}
          projects={projectItems}
          onClose={() => setCatalogInstrument(null)}
          onCreated={({ projectId, studyId }) => {
            setCatalogInstrument(null);
            setActiveProjectId(projectId);
            navigate(`/colmena/project/${projectId}/link?studyId=${studyId}`);
          }}
        />
      )}
      {selectedInstrument && (
        <InstrumentConfirmModal
          instrument={selectedInstrument}
          isOpen
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
