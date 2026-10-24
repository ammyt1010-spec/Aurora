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
  Sparkles,
  BarChart3,
  ExternalLink,
  Copy,
  Check,
  X,
  QrCode,
  CheckCircle2,
} from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';

import { getCensopasPlans } from '../../api/instruments.js';
import { listProjects } from '../../api/projects.js';
import { setActiveProjectId } from '../../utils/activeProject.js';
import { cn } from '../../utils/cn.js';
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
    if (!byKind.has(kind) || (plan.ready_for_scoring && !byKind.get(kind).ready_for_scoring)) {
      byKind.set(kind, plan);
    }
  }
  return [...byKind.values()].sort((a, b) => a.version_kind.localeCompare(b.version_kind));
}

/**
 * Inicio orientado a tareas con arquitectura ejecutiva AURORA Professional.
 * - Solo un catálogo a la vez (Psicosocial / Multidisciplinario).
 * - Expedientes previos mostrados bajo demanda.
 * - Banner spotlight para exploración inmediata del estudio de demostración.
 * - Carrito de batería para combinar instrumentos y generar link público unificado con QR.
 */
export default function DashboardPage() {
  const navigate = useNavigate();
  const [selectedInstrument, setSelectedInstrument] = useState(null);
  const [catalog, setCatalog] = useState('censopas');
  const [showProjects, setShowProjects] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [showBundleModal, setShowBundleModal] = useState(false);

  // Carrito de selección de batería multi-instrumento (iniciado con demo recomendada)
  const [selectedBundleItems, setSelectedBundleItems] = useState([
    { id: 'censopas_medium', name: 'CENSOPAS-COPSOQ (Versión Media)', discipline: 'Psicosocial' },
    { id: 2, name: 'Clima Organizacional y Cultura', discipline: 'Clima' },
  ]);

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

  const toggleBundleItem = (item) => {
    setSelectedBundleItems((prev) => {
      const exists = prev.some((x) => String(x.id) === String(item.id));
      if (exists) {
        return prev.filter((x) => String(x.id) !== String(item.id));
      }
      return [...prev, item];
    });
  };

  const removeBundleItem = (itemId) => {
    setSelectedBundleItems((prev) => prev.filter((x) => String(x.id) !== String(itemId)));
  };

  const bundleUrl = `${window.location.origin}/bateria/83e1755d-af21-4256-bd77-8dd69148e66b`;

  const copyToClipboard = () => {
    navigator.clipboard.writeText(bundleUrl).then(() => {
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2500);
    });
  };

  return (
    <div className="colmena-page aurora-premium-page aurora-home-focus space-y-6 pb-24">
      {/* 1. Encabezado Oficial AURORA Professional */}
      <header className="aurora-suite-hero aurora-home-hero">
        <div className="aurora-suite-hero-copy">
          <span>01 / INICIO · AURORA PROFESSIONAL</span>
          <h1>¿Qué deseas evaluar?</h1>
          <p>Selecciona un instrumento, configura una batería o continúa una evaluación existente.</p>
        </div>
        <div className="aurora-suite-hero-icon" aria-hidden="true"><BookOpen size={27}/></div>
      </header>

      {/* 2. Banner Spotlight Demostración Minera San Cristóbal */}
      <section className="relative overflow-hidden rounded-2xl border border-teal-500/30 bg-gradient-to-r from-[#0B0F17] via-[#111827] to-[#0D2438] p-4 sm:p-5 text-white shadow-xl">
        <div className="absolute right-0 top-0 -mt-6 -mr-6 h-48 w-48 rounded-full bg-teal-400/10 blur-3xl pointer-events-none" />
        <div className="relative flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1.5 max-w-2xl">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-teal-500/20 px-2.5 py-0.5 text-[11px] font-bold text-teal-300 border border-teal-500/30">
              <Sparkles size={12} /> ESTUDIO COMPLETO EN DEMOSTRACIÓN · DATOS SINTÉTICOS
            </div>
            <h2 className="text-sm sm:text-base font-extrabold text-white tracking-tight">
              Diagnóstico Integral Minero · Unidad Minera San Cristóbal (238 evaluados)
            </h2>
            <p className="text-xs text-slate-300 leading-relaxed">
              Explora la plataforma de principio a fin: telemetría en vivo, filtros ejecutivos, generación de informes con firma SHA-256 y cuestionarios en lista continua.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => {
                setActiveProjectId(23);
                navigate('/colmena/project/23/telemetry');
              }}
              className="inline-flex items-center gap-1.5 rounded-xl bg-teal-600 px-3.5 py-2 text-xs font-bold text-white shadow-sm hover:bg-teal-700 transition"
            >
              <BarChart3 size={14} /> Telemetría
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveProjectId(23);
                navigate('/colmena/project/23/reports');
              }}
              className="inline-flex items-center gap-1.5 rounded-xl border border-white/20 bg-white/10 px-3.5 py-2 text-xs font-semibold text-white hover:bg-white/20 transition"
            >
              <FileText size={14} /> Informe
            </button>
            <a
              href="/bateria/83e1755d-af21-4256-bd77-8dd69148e66b"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl border border-teal-400/40 bg-teal-950/40 px-3 py-2 text-xs font-semibold text-teal-200 hover:bg-teal-900/50 transition"
            >
              <span>Cuestionarios</span>
              <ExternalLink size={12} />
            </a>
          </div>
        </div>
      </section>

      {/* 3. Barra de Navegación por Catálogo y Acciones */}
      <div className="aurora-home-toolbar">
        <div role="tablist" aria-label="Catálogo de instrumentos" className="aurora-home-tabs">
          <button
            type="button"
            role="tab"
            id="aurora-tab-censopas"
            aria-selected={catalog === 'censopas'}
            aria-controls="aurora-catalog-view"
            className={catalog === 'censopas' ? 'is-active' : ''}
            onClick={() => setCatalog('censopas')}
          >
            <ShieldCheck size={15}/> Psicosocial
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
            <Layers3 size={15}/> Multidisciplinario
          </button>
        </div>

        <div className="aurora-home-actions">
          {projectItems.length > 0 && (
            <button
              type="button"
              aria-expanded={showProjects}
              onClick={() => setShowProjects((x) => !x)}
              className="aurora-home-action"
            >
              Mis evaluaciones <span className="aurora-home-counter">{projectItems.length}</span>
            </button>
          )}
          <button
            type="button"
            className="aurora-home-action is-primary"
            onClick={() => navigate('/colmena/project/new')}
          >
            <Plus size={15}/> Nueva evaluación
          </button>
        </div>
      </div>

      {projectsError && (
        <p role="status" className="text-xs text-muted">
          Las evaluaciones guardadas no están disponibles en este momento.
        </p>
      )}

      {/* 4. Evaluaciones Previas Bajo Demanda */}
      {showProjects && projectItems.length > 0 && (
        <section aria-label="Mis evaluaciones corporativas" className="aurora-home-projects">
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
                    <ArrowRight size={12}/> Telemetría
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveProjectId(project.id);
                      navigate('/colmena/reports');
                    }}
                  >
                    <FileText size={12}/> Informe
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* 5. Catálogo Activo: Psicosocial o Multidisciplinario */}
      <section
        id="aurora-catalog-view"
        role="tabpanel"
        aria-labelledby={catalog === 'censopas' ? 'aurora-tab-censopas' : 'aurora-tab-multidisc'}
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
                <RefreshCcw size={14} className={isFetching ? 'animate-spin' : ''}/> Actualizar
              </button>
            </div>

            {isLoading ? <LoadingState label="Consultando instrumentos del servidor..." /> : null}
            {isError ? (
              <ErrorState
                title="No se pudo cargar el catálogo"
                message={error?.message || 'Comprueba la conexión con el backend de AURORA.'}
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
                  const planId = `censopas_${plan.version_kind.toLowerCase()}`;
                  const isSelected = selectedBundleItems.some((x) => String(x.id) === String(planId));

                  return (
                    <article key={plan.instrument_version_id} className="aurora-catalog-card aurora-home-instrument">
                      <div className="aurora-home-instrument-data">
                        <span className={ready ? 'aurora-home-state is-ready' : 'aurora-home-state'}>
                          {ready ? 'Lista para aplicar' : 'Requiere validación'}
                        </span>
                        <h3>{title}</h3>
                        <p>
                          {plan.question_count} preguntas, {plan.scored_item_count} ítems puntuables
                          · {plan.dimension_count} dimensiones · {plan.subdimension_count} subdimensiones
                        </p>
                        <small>Versión {plan.version_code} · La clasificación depende del baremo configurado.</small>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border/60">
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
                              description: plan.plan_description || 'Evaluación empresarial basada en una versión del instrumento.',
                            })
                          }
                        >
                          <ClipboardCheck size={15}/>
                          {ready ? 'Aplicar instrumento' : 'No disponible'}
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            toggleBundleItem({
                              id: planId,
                              name: title,
                              discipline: 'Psicosocial',
                            })
                          }
                          className={cn(
                            'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition',
                            isSelected
                              ? 'bg-teal-50 text-teal-800 border border-teal-300'
                              : 'bg-slate-50 text-slate-700 border border-slate-200 hover:bg-slate-100'
                          )}
                        >
                          {isSelected ? (
                            <>
                              <Check size={13} className="text-teal-700" /> En batería
                            </>
                          ) : (
                            <>+ Añadir a batería</>
                          )}
                        </button>
                      </div>
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
                <span>Selecciona un método autorizado y vincúlalo a su evaluación empresarial o añádelo a tu batería.</span>
              </div>
            </div>
            <MultidisciplinaryCatalog
              simpleMode
              onCreateEvaluation={() => navigate('/colmena/project/new')}
              selectedIds={selectedBundleItems.map((x) => x.id)}
              onSelectInstrument={(inst) =>
                toggleBundleItem({
                  id: inst.id,
                  name: inst.name,
                  discipline: inst.discipline_code || 'Multidisciplinario',
                })
              }
            />
          </div>
        )}
      </section>

      {/* 6. Carrito Flotante de Batería de Evaluación */}
      {selectedBundleItems.length > 0 && (
        <div className="fixed bottom-0 inset-x-0 z-40 bg-white/95 border-t border-slate-200 p-3 sm:p-4 shadow-2xl backdrop-blur-md">
          <div className="max-w-6xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="h-10 w-10 shrink-0 rounded-xl bg-teal-500/15 text-teal-700 flex items-center justify-center font-bold text-sm">
                {selectedBundleItems.length}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-dark">
                  Batería de Evaluación ({selectedBundleItems.length} instrumentos seleccionados)
                </p>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {selectedBundleItems.map((item) => (
                    <span
                      key={item.id}
                      className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700"
                    >
                      {item.name}
                      <button
                        type="button"
                        onClick={() => removeBundleItem(item.id)}
                        className="text-slate-400 hover:text-rose-500 font-bold ml-0.5"
                        title="Quitar"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => setSelectedBundleItems([])}
                className="px-3 py-2 text-xs font-medium text-muted hover:text-dark"
              >
                Vaciar
              </button>
              <button
                type="button"
                onClick={() => setShowBundleModal(true)}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-teal-600 to-teal-700 text-white text-xs font-bold shadow-md hover:from-teal-700 hover:to-teal-800 transition"
              >
                <Sparkles size={14} />
                <span>Generar Enlace y QR Batería</span>
                <ArrowRight size={13} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 7. Modal de Enlace Compartido y Código QR */}
      {showBundleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-5 sm:p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 size={20} className="text-teal-600" />
                <h3 className="text-base font-bold text-dark">Enlace Unificado de Batería Generado</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowBundleModal(false)}
                className="rounded-lg p-1 text-muted hover:bg-slate-100 hover:text-dark"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-3 text-sm">
              <p className="text-xs text-muted">
                Tus colaboradores accederán a un solo enlace que contiene todos los cuestionarios seleccionados en una experiencia unificada:
              </p>
              <ul className="space-y-1.5 rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-xs">
                {selectedBundleItems.map((item, idx) => (
                  <li key={item.id} className="flex items-center gap-2 font-medium text-slate-800">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-teal-100 text-[10px] font-bold text-teal-800">
                      {idx + 1}
                    </span>
                    <span>{item.name}</span>
                  </li>
                ))}
              </ul>

              <div className="space-y-2 pt-2">
                <label className="text-xs font-bold text-dark">Enlace público compartido:</label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    readOnly
                    value={bundleUrl}
                    className="flex-1 rounded-xl border border-border bg-slate-50 px-3 py-2 text-xs font-mono text-dark select-all"
                  />
                  <button
                    type="button"
                    onClick={copyToClipboard}
                    className={cn(
                      'inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold transition shadow-xs',
                      copiedLink ? 'bg-emerald-600 text-white' : 'bg-teal-600 text-white hover:bg-teal-700'
                    )}
                  >
                    {copiedLink ? <Check size={14} /> : <Copy size={14} />}
                    {copiedLink ? 'Copiado' : 'Copiar'}
                  </button>
                </div>
              </div>

              {/* Código QR para Celular */}
              <div className="flex items-center gap-4 rounded-xl border border-border bg-white p-3.5">
                <div className="bg-white p-1 rounded-lg border border-slate-200">
                  <QRCodeSVG value={bundleUrl} size={84} level="M" />
                </div>
                <div className="space-y-1 text-xs">
                  <p className="font-bold text-dark flex items-center gap-1.5">
                    <QrCode size={14} className="text-teal-600" /> Código QR para Celular
                  </p>
                  <p className="text-muted leading-relaxed">
                    Escanea directamente para responder desde tu smartphone. Las preguntas se muestran en formato lista continua rápida.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between border-t border-border pt-4">
              <button
                type="button"
                onClick={() => setShowBundleModal(false)}
                className="px-4 py-2 rounded-xl border border-border text-xs font-semibold text-dark hover:bg-slate-50"
              >
                Cerrar
              </button>
              <a
                href={bundleUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-teal-600 text-white text-xs font-bold hover:bg-teal-700 transition"
              >
                <span>Abrir Vista del Colaborador</span>
                <ExternalLink size={13} />
              </a>
            </div>
          </div>
        </div>
      )}

      {/* 8. Modal de confirmación para aplicación individual */}
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
