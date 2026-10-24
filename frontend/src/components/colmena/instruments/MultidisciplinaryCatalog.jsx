import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Brain,
  Activity,
  Users,
  ShieldAlert,
  Flame,
  FileText,
  Search,
  Filter,
  CheckCircle2,
  AlertTriangle,
  Lock,
  Clock,
  Sparkles,
  Link as LinkIcon,
  BookOpen,
  Award,
  Layers,
  ChevronRight,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react';

import {
  listInstruments,
  listDisciplines,
  validateInstrumentVersion,
  linkStudyInstrument,
} from '../../../api/instruments.js';
import { Card } from '../../ui/Card.jsx';
import { Button } from '../../ui/Button.jsx';
import { LoadingState } from '../../ui/LoadingState.jsx';
import { ErrorState } from '../../ui/ErrorState.jsx';
import { EmptyState } from '../../ui/EmptyState.jsx';

const DISCIPLINE_ICONS = {
  PSICOSOCIAL: Brain,
  ERGONOMIA: Activity,
  CLIMA_ORGANIZACIONAL: Users,
  SEGURIDAD_SALUD: ShieldAlert,
  LIDERAZGO_BURNOUT: Flame,
  OTRO: FileText,
};

const STATUS_CONFIG = {
  DRAFT: {
    label: 'Borrador',
    color: 'bg-slate-100 text-slate-700 border-slate-300',
    icon: Clock,
    description: 'Instrumento en diseño preliminar. No autorizado para evaluaciones oficiales.',
  },
  VALIDATING: {
    label: 'En Validación',
    color: 'bg-amber-100 text-amber-800 border-amber-300',
    icon: AlertTriangle,
    description: 'En proceso de auditoría psicométrica y verificación de baremos.',
  },
  TEST: {
    label: 'En Validación',
    color: 'bg-amber-100 text-amber-800 border-amber-300',
    icon: AlertTriangle,
    description: 'En pruebas piloto internas.',
  },
  AUTHORIZED: {
    label: 'Autorizado',
    color: 'bg-emerald-100 text-emerald-800 border-emerald-300',
    icon: CheckCircle2,
    description: 'Marcado como autorizado en el catálogo. Comprueba la documentación metodológica y los permisos de uso.',
  },
  ACTIVE: {
    label: 'Autorizado / Activo',
    color: 'bg-emerald-100 text-emerald-800 border-emerald-300',
    icon: CheckCircle2,
    description: 'Estado activo en la plataforma. Su uso depende de versión autorizada y licenciamiento.',
  },
  LOCKED: {
    label: 'Bloqueado',
    color: 'bg-rose-100 text-rose-800 border-rose-300',
    icon: Lock,
    description: 'Congelado retroactivamente por uso en evaluaciones cerradas o disposición institucional.',
  },
  CLOSED: {
    label: 'Cerrado',
    color: 'bg-rose-100 text-rose-800 border-rose-300',
    icon: Lock,
    description: 'Versión archivada. No admite modificaciones.',
  },
  USED: {
    label: 'Consumido',
    color: 'bg-slate-100 text-slate-800 border-slate-300',
    icon: Lock,
    description: 'Versión utilizada en evaluaciones.',
  },
};

export default function MultidisciplinaryCatalog({
  projectId,
  currentStudyId,
  currentVersionId,
  onSelectInstrument,
  onCreateEvaluation,
  simpleMode = false,
}) {
  const queryClient = useQueryClient();
  const [selectedDiscipline, setSelectedDiscipline] = useState('ALL');
  const [selectedStatus, setSelectedStatus] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [validationModal, setValidationModal] = useState(null);

  const { data: disciplines = [], isLoading: isLoadingDisciplines } = useQuery({
    queryKey: ['instrument-disciplines'],
    queryFn: () => listDisciplines(),
  });

  const {
    data: instrumentsResponse,
    isLoading: isLoadingInstruments,
    error,
    refetch,
  } = useQuery({
    queryKey: [
      'multidisciplinary-instruments',
      selectedDiscipline,
      selectedStatus,
      searchQuery,
    ],
    queryFn: () =>
      listInstruments({
        discipline: selectedDiscipline !== 'ALL' ? selectedDiscipline : null,
        status: selectedStatus !== 'ALL' ? selectedStatus : null,
        query: searchQuery.trim() || null,
        pageSize: 100,
      }),
  });

  const validateMutation = useMutation({
    mutationFn: (versionId) => validateInstrumentVersion(versionId),
    onSuccess: (data) => {
      setValidationModal(data);
      queryClient.invalidateQueries({ queryKey: ['multidisciplinary-instruments'] });
      queryClient.invalidateQueries({ queryKey: ['censopas-readiness'] });
    },
  });

  const linkMutation = useMutation({
    mutationFn: ({ studyId, versionId }) => linkStudyInstrument(studyId, versionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project'] });
      queryClient.invalidateQueries({ queryKey: ['study'] });
      alert('Instrumento vinculado exitosamente al estudio del proyecto.');
    },
  });

  const instruments = instrumentsResponse?.items || [];

  return (
    <div className={simpleMode ? "space-y-3" : "space-y-6"}>
      {/* Barra de Búsqueda y Filtros de Disciplina */}
      <div className={simpleMode ? "rounded-xl border border-border bg-card p-3 shadow-sm" : "rounded-2xl border border-border bg-card p-4 shadow-sm"}>
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          {/* Campo de búsqueda */}
          <div className="relative flex-1">
            <Search
              size={18}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"
            />
            <input
              type="text"
              placeholder="Buscar por nombre, código o autor del instrumento..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-xl border border-border bg-background py-2 pl-10 pr-4 text-sm text-dark placeholder:text-muted focus:border-amber focus:outline-none focus:ring-1 focus:ring-amber"
            />
          </div>

          {/* Filtro por estado */}
          <div className="flex items-center gap-2">
            <Filter size={16} className="text-muted" />
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="rounded-xl border border-border bg-background px-3 py-2 text-xs font-semibold text-dark focus:border-amber focus:outline-none"
            >
              <option value="ALL">Todos los estados</option>
              <option value="AUTHORIZED">Autorizados</option>
              <option value="VALIDATING">En Validación</option>
              <option value="DRAFT">Borrador</option>
              <option value="LOCKED">Bloqueados</option>
            </select>
          </div>
        </div>

        {/* Píldoras de Disciplina */}
        <div className={simpleMode ? "mt-2 flex flex-wrap gap-1.5" : "mt-4 flex flex-wrap gap-2"}>
          <button
            type="button"
            onClick={() => setSelectedDiscipline('ALL')}
            className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition-colors ${
              selectedDiscipline === 'ALL'
                ? 'bg-amber text-white shadow-sm'
                : 'border border-border bg-background text-muted hover:border-amber/50 hover:text-dark'
            }`}
          >
            Todas las Disciplinas
          </button>
          {disciplines.map((d) => {
            const Icon = DISCIPLINE_ICONS[d.code] || FileText;
            const isSelected = selectedDiscipline === d.code;
            return (
              <button
                key={d.code}
                type="button"
                onClick={() => setSelectedDiscipline(d.code)}
                className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold transition-colors ${
                  isSelected
                    ? 'bg-amber text-white shadow-sm'
                    : 'border border-border bg-background text-muted hover:border-amber/50 hover:text-dark'
                }`}
              >
                <Icon size={14} />
                <span>{d.name.split(' (')[0]}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Listado de Instrumentos */}
      {isLoadingInstruments ? (
        <LoadingState label="Cargando catálogo multidisciplinario..." />
      ) : error ? (
        <ErrorState message="No pudimos cargar los instrumentos del catálogo." />
      ) : instruments.length === 0 ? (
        <Card>
          <EmptyState
            title="No se encontraron instrumentos con estos filtros"
            description="Intenta seleccionar otra disciplina o cambiar los términos de búsqueda."
          />
        </Card>
      ) : (
        <div className={simpleMode ? "grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3" : "grid grid-cols-1 gap-4 md:grid-cols-2"}>
          {instruments.map((inst) => {
            const DisciplineIcon = DISCIPLINE_ICONS[inst.discipline] || FileText;
            const statusInfo = STATUS_CONFIG[inst.status] || STATUS_CONFIG.DRAFT;
            const StatusIcon = statusInfo.icon;
            const isSystem = Boolean(inst.is_system);
            const canConfigure = ['AUTHORIZED', 'ACTIVE'].includes(inst.status);

            return (
              <Card
                key={inst.id}
                className={simpleMode ? "flex flex-col justify-between gap-2 p-3 transition-colors hover:border-[#B9D9EF]" : "flex flex-col justify-between transition-all hover:border-amber/40 hover:shadow-md"}
              >
                <div>
                  {/* Encabezado de la Tarjeta */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber/10 text-amber">
                        <DisciplineIcon size={22} />
                      </div>
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-bold text-dark">{inst.name}</h3>
                          {inst.code ? (
                            <span className="rounded-md bg-muted/10 px-2 py-0.5 font-mono text-[11px] font-bold text-muted">
                              {inst.code}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-1 line-clamp-2 text-xs text-muted">
                          {inst.description || 'Sin descripción metodológica.'}
                        </p>
                      </div>
                    </div>

                    {/* Badge de Estado */}
                    <span
                      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-bold ${statusInfo.color}`}
                      title={statusInfo.description}
                    >
                      <StatusIcon size={12} />
                      {statusInfo.label}
                    </span>
                  </div>

                  {/* Metadatos y Procedencia */}
                  {!simpleMode && <div className="mt-4 flex flex-wrap gap-2 text-[11px]">
                    <span className="rounded-lg border border-border bg-background/80 px-2.5 py-1 font-medium text-dark">
                      Disciplina: <strong className="font-semibold text-amber">{inst.discipline}</strong>
                    </span>
                    {inst.author ? (
                      <span className="rounded-lg border border-border bg-background/80 px-2.5 py-1 text-muted">
                        Autor: <span className="font-medium text-dark">{inst.author}</span>
                      </span>
                    ) : null}
                    {isSystem ? (
                      <span className="flex items-center gap-1 rounded-lg bg-turquoise/10 px-2.5 py-1 font-semibold text-turquoise">
                        <Award size={12} /> Instrumento del sistema AURORA
                      </span>
                    ) : (
                      <span className="rounded-lg bg-slate-100 px-2.5 py-1 text-slate-700">
                        Corporativo Privado
                      </span>
                    )}
                  </div>}

                  {/* Autorizaciones y Restricciones de Reproducción */}
                  {!simpleMode && inst.reproduction_terms ? (
                    <div className="mt-3 rounded-xl border border-border/80 bg-background/50 p-2 text-[11px] text-muted">
                      <span className="font-semibold text-dark">Propiedad & Restricción:</span>{' '}
                      {inst.reproduction_terms}
                    </div>
                  ) : null}
                </div>

                {/* Acciones de la Tarjeta */}
                {simpleMode ? (
                  <div className="mt-2">
                    <button type="button"
                      className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[#173968] px-3 py-2 text-xs font-bold text-white hover:bg-[#29538F]"
                      disabled={!canConfigure || (!onSelectInstrument && !onCreateEvaluation)}
                      onClick={() => {
                        if (onSelectInstrument) onSelectInstrument(inst);
                        else onCreateEvaluation?.(inst);
                      }}>
                      <ChevronRight size={14}/>{canConfigure ? 'Configurar evaluación' : 'Pendiente de autorización'}
                    </button>
                  </div>
                ) : <div className="mt-5 border-t border-border pt-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[11px] font-medium text-muted">
                      Método tarifario:{' '}
                      <code className="text-dark font-mono font-bold">
                        {inst.method_code || 'VINCULADO_VERSION'}
                      </code>
                    </span>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        className="text-xs"
                        onClick={() => {
                          const targetVerId = inst.metadata?.default_version_id;
                          if (targetVerId) validateMutation.mutate(targetVerId);
                        }}
                        disabled={validateMutation.isPending || !inst.metadata?.default_version_id}
                      >
                        <ShieldCheck size={13} className="mr-1 text-amber" /> Auditoría Metodológica
                      </Button>
                      {currentStudyId ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          className="text-xs"
                          onClick={() => {
                            const targetVerId = inst.metadata?.default_version_id;
                            if (targetVerId) linkMutation.mutate({
                              studyId: currentStudyId,
                              versionId: targetVerId,
                            });
                          }}
                          disabled={!inst.metadata?.default_version_id}
                        >
                          <LinkIcon size={13} className="mr-1" /> Vincular a Estudio
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </div>}
              </Card>
            );
          })}
        </div>
      )}

      {/* Modal de Resultado de Validación Metodológica */}
      {validationModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-border bg-card p-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                {validationModal.is_valid ? (
                  <CheckCircle2 size={22} className="text-emerald-600" />
                ) : (
                  <AlertTriangle size={22} className="text-rose-600" />
                )}
                <h3 className="font-bold text-dark">
                  Auditoría Metodológica: {validationModal.version_code}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setValidationModal(null)}
                className="text-muted hover:text-dark text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <div className="rounded-xl border border-border bg-background p-3">
                <p className="font-semibold text-dark">
                  Estado Psicométrico:{' '}
                  <span
                    className={
                      validationModal.is_valid
                        ? 'text-emerald-600 font-bold'
                        : 'text-rose-600 font-bold'
                    }
                  >
                    {validationModal.scoring_status}
                  </span>
                </p>
                <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-muted">
                  <div>Reactivos: {validationModal.metrics?.total_questions ?? 0}</div>
                  <div>Dimensiones: {validationModal.metrics?.dimension_count ?? 0}</div>
                  <div>Puntuables: {validationModal.metrics?.scored_questions ?? 0}</div>
                  <div>Subdimensiones: {validationModal.metrics?.subdimension_count ?? 0}</div>
                </div>
              </div>

              {validationModal.errors?.length > 0 ? (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-rose-800">
                  <p className="font-bold">Observaciones Críticas:</p>
                  <ul className="mt-1 list-disc pl-4 space-y-1">
                    {validationModal.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {validationModal.warnings?.length > 0 ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-amber-800">
                  <p className="font-bold">Advertencias Metodológicas:</p>
                  <ul className="mt-1 list-disc pl-4 space-y-1">
                    {validationModal.warnings.map((warn, i) => (
                      <li key={i}>{warn}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>

            <div className="mt-5 flex justify-end">
              <Button size="sm" onClick={() => setValidationModal(null)}>
                Entendido
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
