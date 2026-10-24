import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  BookOpen,
  ClipboardCheck,
  ShieldCheck,
  RefreshCcw,
  Sparkles,
  ArrowRight,
  FileText,
  BarChart3,
  Layers3,
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

export default function DashboardPage() {
  const navigate = useNavigate();
  const [selectedInstrument, setSelectedInstrument] = useState(null);
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
  const cards = availableInstrumentCards(data);

  const { data: existingProjects } = useQuery({
    queryKey: ['aurora-home-projects'],
    queryFn: () => listProjects({ page: 1, pageSize: 50 }),
    retry: false,
  });
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
    <div className="colmena-page aurora-premium-page space-y-6 pb-24">
      {/* 1. Banner Principal de Demostración: Estudio Minero en Vivo */}
      <section className="relative overflow-hidden rounded-2xl border border-teal-500/30 bg-gradient-to-r from-[#0B0F17] via-[#111827] to-[#0D2438] p-5 sm:p-6 text-white shadow-xl">
        <div className="absolute right-0 top-0 -mt-6 -mr-6 h-48 w-48 rounded-full bg-teal-400/10 blur-3xl" />
        <div className="relative flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-teal-500/20 px-3 py-0.5 text-[11px] font-bold text-teal-300 border border-teal-500/30">
              <Sparkles size={12} /> ESTUDIO COMPLETO EN DEMOSTRACIÓN · DATOS SINTÉTICOS
            </div>
            <h1 className="text-lg sm:text-xl font-extrabold text-white tracking-tight">
              Diagnóstico Integral Minero · Unidad Minera San Cristóbal
            </h1>
            <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
              Explora la plataforma de principio a fin con 238 trabajadores evaluados: telemetría en vivo con 7 widgets BI, filtros multidimensionales, generación de informes con firma SHA-256 y batería pública de cuestionarios.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={() => {
                setActiveProjectId(23);
                navigate('/colmena/project/23/telemetry');
              }}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-teal-500 to-teal-600 px-4 py-2.5 text-xs font-bold text-white shadow-md hover:from-teal-600 hover:to-teal-700 transition"
            >
              <BarChart3 size={16} /> Ver Dashboard BI Minera
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveProjectId(23);
                navigate('/colmena/project/23/reports');
              }}
              className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/10 px-3.5 py-2.5 text-xs font-semibold text-white hover:bg-white/20 transition"
            >
              <FileText size={15} /> Ver Informes y PDF
            </button>
            <a
              href="/bateria/83e1755d-af21-4256-bd77-8dd69148e66b"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl border border-teal-400/40 bg-teal-950/40 px-3.5 py-2.5 text-xs font-semibold text-teal-200 hover:bg-teal-900/50 transition"
            >
              📱 Cuestionarios Trabajador
              <ExternalLink size={12} />
            </a>
          </div>
        </div>
      </section>

      {/* 2. Catálogo de Instrumentos y Selección para Batería */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 px-1">
          <div>
            <h2 className="text-base font-extrabold text-dark flex items-center gap-2">
              <Layers3 size={18} className="text-teal-600" />
              Catálogo de Instrumentos para tu Evaluación
            </h2>
            <p className="text-xs text-muted">
              Selecciona los instrumentos que necesitas (como un carrito). Al aceptar, obtendrás un enlace único donde tus colaboradores encontrarán todos los cuestionarios juntos.
            </p>
          </div>
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-white px-3 py-2 text-xs font-bold text-dark shadow-xs disabled:opacity-50"
          >
            <RefreshCcw size={14} className={isFetching ? 'animate-spin' : ''} /> Actualizar catálogo
          </button>
        </div>

        {isLoading ? <LoadingState label="Consultando instrumentos del servidor..." /> : null}
        {isError ? (
          <ErrorState
            title="No se pudo cargar el catálogo"
            message={error?.message || 'Comprueba la conexión con el backend de AURORA.'}
          />
        ) : null}

        {/* CENSOPAS Oficial */}
        {!isLoading && !isError && cards.length > 0 ? (
          <section aria-label="Instrumentos publicados" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {cards.map((plan) => {
              const ready = plan.ready_for_scoring === true;
              const title = VERSION_LABELS[plan.version_kind];
              const planId = `censopas_${plan.version_kind.toLowerCase()}`;
              const isSelected = selectedBundleItems.some((x) => String(x.id) === String(planId));

              return (
                <article
                  key={plan.instrument_version_id}
                  className={cn(
                    'aurora-catalog-card flex flex-col justify-between gap-4 p-4 sm:p-5 transition border',
                    isSelected ? 'border-teal-500 bg-teal-50/20 ring-1 ring-teal-400' : 'border-border'
                  )}
                >
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="rounded-md border border-amber/20 bg-amber/10 px-2 py-0.5 text-xs font-semibold text-dark">
                        {ready ? 'Versión oficial' : 'Requiere validación'}
                      </span>
                      <ShieldCheck size={18} className="text-amber" />
                    </div>
                    <h3 className="text-base font-bold text-dark">{title}</h3>
                    <p className="text-xs text-muted leading-relaxed">
                      {plan.question_count} preguntas, {plan.scored_item_count} ítems puntuables, {plan.dimension_count} dimensiones.
                    </p>
                    <p className="text-[11px] text-muted">Versión: {plan.version_code}. Núcleo CENSOPAS.</p>
                  </div>

                  <div className="flex items-center gap-2 pt-2 border-t border-border/60">
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
                        'flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold transition',
                        isSelected
                          ? 'bg-teal-600 text-white shadow-xs'
                          : 'border border-border bg-white text-dark hover:bg-slate-50'
                      )}
                    >
                      {isSelected ? (
                        <>
                          <Check size={14} /> En tu batería
                        </>
                      ) : (
                        <>+ Agregar a batería</>
                      )}
                    </button>
                    <button
                      type="button"
                      disabled={!ready}
                      onClick={() =>
                        setSelectedInstrument({
                          id: plan.instrument_version_id,
                          title,
                          version: plan.version_kind,
                          items: plan.question_count,
                          duration: 'según el participante',
                          badge: 'Versión configurada en AURORA',
                          description: plan.plan_description || 'Evaluación empresarial individual.',
                        })
                      }
                      className="px-2.5 py-2 rounded-xl border border-border text-[11px] font-medium text-muted hover:text-dark"
                      title="Ver detalles del instrumento"
                    >
                      Detalle
                    </button>
                  </div>
                </article>
              );
            })}
          </section>
        ) : null}

        {/* Otros Instrumentos Multidisciplinarios */}
        <section aria-label="Catálogo multidisciplinario" className="space-y-3 pt-2">
          <div className="aurora-catalog-aux px-4 py-3 border border-border/80 rounded-2xl bg-white shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-dark">Otros instrumentos multidisciplinarios disponibles</h3>
                <p className="text-xs text-muted">
                  Haz clic en "+ Agregar a batería" en cualquiera de estos cuestionarios para sumarlo a tu enlace de evaluación.
                </p>
              </div>
              <button
                type="button"
                className="rounded-lg border border-amber px-3 py-1.5 text-xs font-semibold text-dark hover:bg-amber/10 shrink-0"
                onClick={() => navigate('/colmena/project/new')}
              >
                + Crear nuevo instrumento
              </button>
            </div>
          </div>

          <MultidisciplinaryCatalog
            selectedIds={selectedBundleItems.map((x) => x.id)}
            onSelectInstrument={(inst) =>
              toggleBundleItem({
                id: inst.id,
                name: inst.name,
                discipline: inst.discipline_code || 'Multidisciplinario',
              })
            }
          />
        </section>
      </div>

      {/* 3. Mis Evaluaciones Existentes */}
      {projectItems.length > 0 && (
        <section aria-label="Mis evaluaciones corporativas" className="aurora-catalog-aux space-y-3 p-4 rounded-2xl border border-border bg-white">
          <div>
            <h3 className="text-sm font-extrabold text-[#233c6b]">Mis proyectos y evaluaciones activas</h3>
            <p className="text-xs text-muted">Accede directamente al panel BI o a los informes de cada estudio.</p>
          </div>
          <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
            {projectItems.map((project) => (
              <article key={project.id} className="flex min-w-0 flex-col justify-between gap-3 rounded-xl border border-[#e1e8f4] bg-white p-3.5 shadow-xs">
                <strong className="truncate text-xs text-[#263e66]" title={project.name}>
                  {project.name}
                </strong>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-[11px] font-bold text-[#284c8b] hover:bg-slate-50"
                    onClick={() => {
                      setActiveProjectId(project.id);
                      navigate('/colmena/telemetry');
                    }}
                  >
                    <BarChart3 size={13} /> Telemetría
                  </button>
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-[11px] font-bold text-[#284c8b] hover:bg-slate-50"
                    onClick={() => {
                      setActiveProjectId(project.id);
                      navigate('/colmena/reports');
                    }}
                  >
                    <FileText size={13} /> Informe
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* 4. Barra Flotante / Carrito de Batería de Evaluación */}
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
                onClick={() => setShowBundleModal(true)}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-teal-500 to-teal-600 text-white font-bold text-xs shadow-md hover:from-teal-600 hover:to-teal-700 transition"
              >
                <Sparkles size={15} /> Generar enlace único de evaluación
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 5. Modal de Enlace Único de Batería Generado */}
      {showBundleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded-2xl border border-border bg-white p-6 shadow-2xl space-y-4 animate-scale-in">
            <div className="flex items-start justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-50 text-teal-600">
                  <CheckCircle2 size={24} />
                </div>
                <div>
                  <h3 className="font-extrabold text-dark text-base">Enlace Único de Evaluación Listo</h3>
                  <p className="text-xs text-muted">Todos tus cuestionarios en una sola URL para los colaboradores</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowBundleModal(false)}
                className="text-muted hover:text-dark p-1 rounded-lg"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-3">
              <p className="text-xs text-dark font-medium">
                Cuestionarios que verá el participante al ingresar a este enlace:
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

              {/* Código QR para Móvil */}
              <div className="flex items-center gap-4 rounded-xl border border-border bg-white p-3.5">
                <div className="bg-white p-1 rounded-lg border border-slate-200">
                  <QRCodeSVG value={bundleUrl} size={84} level="M" />
                </div>
                <div className="space-y-1 text-xs">
                  <p className="font-bold text-dark flex items-center gap-1.5">
                    <QrCode size={14} className="text-teal-600" /> Código QR para Celular
                  </p>
                  <p className="text-muted leading-relaxed">
                    Escanea directamente para responder desde tu smartphone. Las preguntas se mostrarán en formato lista rápida.
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
