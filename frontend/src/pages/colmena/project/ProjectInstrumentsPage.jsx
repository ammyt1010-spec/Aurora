import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, FlaskConical, ShieldCheck, PlusCircle, Sparkles } from 'lucide-react';

import { useActiveProject } from '../../../hooks/useActiveProject.js';
import { useProjectInstruments } from '../../../hooks/useProjectInstruments.js';
import { ApiError } from '../../../api/client.js';
import { getProject } from '../../../api/projects.js';
import { getCensopasPlans, getCensopasReadiness } from '../../../api/instruments.js';

import { PageHeader } from '../../../components/layout/PageHeader.jsx';
import { Card } from '../../../components/ui/Card.jsx';
import { Button } from '../../../components/ui/Button.jsx';
import { LoadingState } from '../../../components/ui/LoadingState.jsx';
import { ErrorState } from '../../../components/ui/ErrorState.jsx';
import { EmptyState } from '../../../components/ui/EmptyState.jsx';
import { ProjectMissingState } from '../../../components/colmena/ProjectMissingState.jsx';
import CensopasReadinessPanel from '../../../components/colmena/instruments/CensopasReadinessPanel.jsx';
import CustomInstrumentModal from '../../../components/colmena/instruments/CustomInstrumentModal.jsx';

const COUNT_BADGES = [
  ['question_count', 'preguntas'],
  ['scored_item_count', 'ítems puntuables'],
  ['dimension_count', 'dimensiones'],
  ['subdimension_count', 'subdimensiones'],
];

function PlanCard({ plan, isCurrent }) {
  const { data: readiness, isLoading: isLoadingReadiness } = useQuery({
    queryKey: ['censopas-readiness', plan.instrument_version_id],
    queryFn: () => getCensopasReadiness(plan.instrument_version_id),
    enabled: Boolean(plan.instrument_version_id),
  });

  return (
    <Card className={isCurrent ? 'border-amber/50 ring-1 ring-amber/20' : ''}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber/10 text-amber">
            <ShieldCheck size={20} />
          </div>
          <div>
            <p className="font-semibold text-dark">{plan.plan_label}</p>
            <p className="mt-1 text-sm text-muted">{plan.plan_description}</p>
          </div>
        </div>
        {isCurrent ? (
          <span className="colmena-badge flex items-center gap-1 bg-turquoise/10 text-turquoise">
            <CheckCircle2 size={13} /> Plan actual
          </span>
        ) : null}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {COUNT_BADGES.map(([key, label]) => (
          <div key={key} className="rounded-xl border border-border bg-background/60 p-2.5 text-center">
            <p className="text-sm font-bold text-dark">{plan[key]}</p>
            <p className="text-[11px] text-muted">{label}</p>
          </div>
        ))}
      </div>

      <div className="mt-4">
        <CensopasReadinessPanel readiness={readiness} isLoading={isLoadingReadiness} />
      </div>

      <div className="mt-4 flex justify-end"><span className="text-xs font-semibold text-muted">{isCurrent ? 'Aprovisionado automáticamente por el backend' : 'Catálogo fijo disponible'}</span></div>
    </Card>
  );
}

function CurrentVersionCard({ versionId, versionCode }) {
  const { data: readiness, isLoading } = useQuery({
    queryKey: ['censopas-readiness', versionId],
    queryFn: () => getCensopasReadiness(versionId),
    enabled: Boolean(versionId),
  });

  const expected = readiness?.expected || {};
  const actual = readiness?.actual || {};
  const badges = [
    ['questions', 'preguntas'],
    ['scored', 'ítems puntuables'],
    ['dimensions', 'dimensiones'],
    ['subdimensions', 'subdimensiones'],
  ];

  return (
    <Card className="border-amber/50 ring-1 ring-amber/20">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber/10 text-amber">
            <FlaskConical size={20} />
          </div>
          <div>
            <p className="font-semibold text-dark">Versión vinculada a este proyecto</p>
            <p className="mt-1 text-sm text-muted">
              {versionCode || 'Versión'} · no forma parte del catálogo de planes oficiales publicados.
            </p>
          </div>
        </div>
        <span className="colmena-badge flex items-center gap-1 bg-turquoise/10 text-turquoise">
          <CheckCircle2 size={13} /> Plan actual
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {badges.map(([key, label]) => (
          <div key={key} className="rounded-xl border border-border bg-background/60 p-2.5 text-center">
            <p className="text-sm font-bold text-dark">{actual[key] ?? '—'} / {expected[key] ?? '—'}</p>
            <p className="text-[11px] text-muted">{label}</p>
          </div>
        ))}
      </div>

      <div className="mt-4">
        <CensopasReadinessPanel readiness={readiness} isLoading={isLoading} />
      </div>
    </Card>
  );
}

export default function ProjectInstrumentsPage() {
  const { projectId } = useParams();
  useActiveProject(projectId);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const { data: project, isLoading: isLoadingProject, error } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
    enabled: Boolean(projectId),
    retry: false,
  });

  const { data: plansResponse, isLoading: isLoadingPlans } = useQuery({
    queryKey: ['censopas-plans'],
    queryFn: () => getCensopasPlans(),
  });
  const plans = plansResponse?.plans || [];

  const { data: projectInstruments = [] } = useProjectInstruments(projectId, project?.metadata);
  const activeInstrument =
    projectInstruments.find(
      (instrument) => instrument.id === Number(project?.metadata?.instrument_id || 0),
    ) || projectInstruments[0] || null;

  if (isLoadingProject) return <LoadingState label="Cargando proyecto..." />;
  if (error instanceof ApiError && error.status === 404) return <ProjectMissingState />;
  if (error) return <ErrorState message="No pudimos cargar el proyecto." />;

  const currentVersionId = Number(project?.metadata?.instrument_version_id || 0);
  const currentVersionInCatalog = plans.some((plan) => plan.instrument_version_id === currentVersionId);
  const showUnlistedCurrentVersion =
    Boolean(currentVersionId) && !currentVersionInCatalog && activeInstrument?.versionId === currentVersionId;

  return (
    <div className="colmena-page">
      <PageHeader
        eyebrow="Instrumentos & Catálogo Metodológico"
        title="Instrumentos de Medición Precargados"
        description="Instrumentos estandarizados CENSOPAS-COPSOQ (Versiones corta y media) precargados y listos para la evaluación corporativa. Incluye soporte para nuevos factores extensibles."
        actions={
          <Button onClick={() => setIsModalOpen(true)} size="sm" type="button" className="bg-amber hover:bg-amber-dark">
            <PlusCircle size={15} className="mr-1.5" /> Adaptar / Importar Nuevo Instrumento
          </Button>
        }
      />

      {showUnlistedCurrentVersion ? (
        <CurrentVersionCard versionId={currentVersionId} versionCode={activeInstrument?.versionCode} />
      ) : null}

      {isLoadingPlans ? (
        <LoadingState label="Cargando planes disponibles..." />
      ) : plans.length === 0 ? (
        <Card>
          <EmptyState
            title="Todavía no hay planes oficiales publicados"
            description="El backend no tiene ninguna versión CENSOPAS-COPSOQ activada. Ejecuta scripts/seed_censopas_official.py para publicar el Plan corto."
          />
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {plans.map((plan) => (
            <PlanCard
              key={plan.instrument_version_id}
              plan={plan}
              isCurrent={plan.instrument_version_id === currentVersionId}
            />
          ))}
        </div>
      )}

      {/* Banner de Extensibilidad Corporativa */}
      <Card className="mt-4 border-dashed border-amber/40 bg-amber/5">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber/20 text-amber">
              <Sparkles size={20} />
            </div>
            <div>
              <p className="font-bold text-dark">¿Necesitas medir otros factores de riesgo específicos?</p>
              <p className="text-xs text-muted">
                Colmena 2.0 admite la incorporación de Burnout (MBI), Clima Ergonómico, Ciberestrés y escalas personalizadas.
              </p>
            </div>
          </div>
          <Button size="sm" variant="secondary" onClick={() => setIsModalOpen(true)}>
            Cargar Manifiesto
          </Button>
        </div>
      </Card>

      <CustomInstrumentModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onImportSuccess={(data) => {
          console.log('Instrumento personalizado importado:', data);
        }}
      />
    </div>
  );
}
