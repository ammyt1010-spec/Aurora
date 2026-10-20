import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ClipboardList, FolderKanban, Gauge, LayoutGrid, ListTree, LockKeyhole, Scale, UserRound } from 'lucide-react';

import { useAuth } from '../../../auth/AuthContext.jsx';
import { useActiveProject } from '../../../hooks/useActiveProject.js';
import { useProjectInstruments } from '../../../hooks/useProjectInstruments.js';
import { ApiError } from '../../../api/client.js';
import { getProject, updateProject } from '../../../api/projects.js';
import {
  createInstrumentVersion,
  createProjectInstrument,
  createItem,
  createLikertScale,
  getCensopasReadiness,
  getConstructMatrix,
  getInstrumentTree,
  getItem,
  listLikertScales,
  updateItem,
  updateLikertScale,
} from '../../../api/instruments.js';
import { createConstruct, createStructureVariable, linkItemToConstruct, updateConstructItem } from '../../../api/constructs.js';

import { PageHeader } from '../../../components/layout/PageHeader.jsx';
import { Card } from '../../../components/ui/Card.jsx';
import { EmptyState } from '../../../components/ui/EmptyState.jsx';
import { LoadingState } from '../../../components/ui/LoadingState.jsx';
import { ErrorState } from '../../../components/ui/ErrorState.jsx';
import { ProjectMissingState } from '../../../components/colmena/ProjectMissingState.jsx';
import InstrumentTreeView from '../../../components/colmena/instruments/InstrumentTreeView.jsx';
import StructureNodeModal from '../../../components/colmena/instruments/StructureNodeModal.jsx';
import InstrumentMatrixView from '../../../components/colmena/instruments/InstrumentMatrixView.jsx';
import ItemEditorDrawer from '../../../components/colmena/instruments/ItemEditorDrawer.jsx';
import LikertScaleManager from '../../../components/colmena/instruments/LikertScaleManager.jsx';
import BaremBuilder from '../../../components/colmena/instruments/BaremBuilder.jsx';
import ProjectCreateModal from '../../../components/colmena/projects/ProjectCreateModal.jsx';
import ExogenousFieldsManager from '../../../components/colmena/variables/ExogenousFieldsManager.jsx';
import CensopasReadinessPanel from '../../../components/colmena/instruments/CensopasReadinessPanel.jsx';

const LOCK_MESSAGES = {
  SYSTEM_INSTRUMENT_LOCKED:
    'CENSOPAS-COPSOQ es un instrumento oficial protegido: dimensiones, preguntas y escalas Likert coinciden con el Manual técnico y no son editables. Los campos adaptables (nivel de instrucción, puesto, área, tipo de contrato, tiempo en el puesto, horario) se administran desde la pestaña Datos exógenos.',
  STUDY_OPEN_STRUCTURAL_LOCK:
    'El estudio de este proyecto ya está abierto y recolectando respuestas, así que su estructura quedó congelada.',
};

function collectConstructCodes(nodes, codes = new Set()) {
  nodes?.forEach((node) => {
    if (node.code) codes.add(node.code);
    collectConstructCodes(node.subdimensions || node.dimensions, codes);
  });
  return codes;
}

function NewProjectStep({ ownerUserId }) {
  const navigate = useNavigate();

  return (
    <div className="colmena-page min-h-[calc(100vh-3.5rem)]">
      <PageHeader title="Nuevo proyecto" description="Configura el espacio donde organizarás variables, dimensiones y preguntas." />
      <Card className="max-w-3xl bg-hero-glow">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber/10 text-amber">
            <FolderKanban size={20} />
          </div>
          <div>
            <p className="font-semibold text-dark">Estructura metodológica de Aurora</p>
            <p className="mt-1 text-sm text-muted">Proyecto → variables → dimensiones o preguntas directas.</p>
          </div>
        </div>
      </Card>
      <ProjectCreateModal
        ownerUserId={ownerUserId}
        onClose={() => navigate('/colmena', { replace: true })}
        onCreated={(project) => navigate(`/colmena/project/${project.id}`, { replace: true })}
      />
    </div>
  );
}

function InstrumentTab({ projectId, versionId, isLoadingInstrument, onCreateInstrument, isCreatingInstrument }) {
  const queryClient = useQueryClient();
  const [view, setView] = useState('tree');
  const [itemDrawer, setItemDrawer] = useState(null);
  const [structureModal, setStructureModal] = useState(null);
  const [selectedVariableId, setSelectedVariableId] = useState(null);

  const { data: tree, isLoading: isLoadingTree } = useQuery({
    queryKey: ['instrumentTree', versionId],
    queryFn: () => getInstrumentTree(versionId),
    enabled: Boolean(versionId) && view === 'tree',
  });
  const isLocked = tree ? !tree.editable : false;

  useEffect(() => {
    const variables = tree?.variables || [];
    if (!variables.length) {
      setSelectedVariableId(null);
    } else if (!variables.some((variable) => variable.id === selectedVariableId)) {
      setSelectedVariableId(variables[0].id);
    }
  }, [selectedVariableId, tree]);

  const { data: matrix, isLoading: isLoadingMatrix } = useQuery({
    queryKey: ['constructMatrix', versionId],
    queryFn: () => getConstructMatrix(versionId),
    enabled: Boolean(versionId) && view === 'matrix',
  });

  const { data: likertScales = [] } = useQuery({
    queryKey: ['likertScales', versionId],
    queryFn: () => listLikertScales(versionId),
    enabled: Boolean(versionId),
  });

  const invalidateInstrument = () => {
    queryClient.invalidateQueries({ queryKey: ['instrumentTree', versionId] });
    queryClient.invalidateQueries({ queryKey: ['constructMatrix', versionId] });
    queryClient.invalidateQueries({ queryKey: ['likertScales', versionId] });
  };

  const prepareItemPayload = async (payload, { isCreating }) => {
    const {
      scale_action: scaleAction,
      scale_config: scaleConfig,
      weight,
      scoring_direction: scoringDirection,
      ...questionPayload
    } = payload;

    if (scaleAction === 'UPDATE' && scaleConfig) {
      const updatedScale = await updateLikertScale(questionPayload.option_set_id, scaleConfig);
      questionPayload.option_set_id = updatedScale.id;
      delete questionPayload.option_set;
    } else if (scaleAction === 'CREATE' && scaleConfig) {
      // Para un alta, pregunta y escala se guardan juntas en el backend.
      // Al editar un ítem, se crea una escala reutilizable y luego se vincula.
      if (isCreating && questionPayload.option_set) {
        questionPayload.option_set_id = null;
      } else {
        const createdScale = await createLikertScale(versionId, scaleConfig);
        questionPayload.option_set_id = createdScale.id;
        delete questionPayload.option_set;
      }
    } else {
      delete questionPayload.option_set;
    }

    return { questionPayload, weight, scoringDirection };
  };

  const addVariableMutation = useMutation({
    mutationFn: ({ name, code, role }) => createStructureVariable(versionId, { name, code, role }),
    onSuccess: (variable) => {
      invalidateInstrument();
      setSelectedVariableId(variable.id);
      setStructureModal(null);
    },
  });

  const addDimensionMutation = useMutation({
    mutationFn: ({ parent, name, code }) =>
      createConstruct(versionId, {
        parent_id: parent.id,
        code,
        name,
        construct_type: 'DIMENSION',
        metadata: { node_kind: 'DIMENSION' },
      }),
    onSuccess: () => {
      invalidateInstrument();
      setStructureModal(null);
    },
  });

  const addSubdimensionMutation = useMutation({
    mutationFn: ({ parent, name, code }) =>
      createConstruct(versionId, {
        parent_id: parent.id,
        code,
        name,
        construct_type: 'SUBDIMENSION',
        metadata: { node_kind: 'SUBDIMENSION' },
      }),
    onSuccess: () => {
      invalidateInstrument();
      setStructureModal(null);
    },
  });

  const openStructureModal = (modal) => {
    if (isLocked) return;
    addVariableMutation.reset();
    addDimensionMutation.reset();
    addSubdimensionMutation.reset();
    setStructureModal(modal);
  };

  const createItemMutation = useMutation({
    mutationFn: async ({ constructId, payload }) => {
      const { questionPayload, weight, scoringDirection } = await prepareItemPayload(payload, { isCreating: true });
      const question = await createItem(versionId, questionPayload);
      await linkItemToConstruct(constructId, {
        question_id: question.id,
        weight: weight ?? 1,
        scoring_direction: scoringDirection,
      });
      return question;
    },
    onSuccess: () => {
      invalidateInstrument();
      setItemDrawer(null);
    },
  });

  const updateItemMutation = useMutation({
    mutationFn: async ({ itemId, constructId, payload }) => {
      const { questionPayload, weight, scoringDirection } = await prepareItemPayload(payload, { isCreating: false });
      const question = await updateItem(itemId, {
        code: questionPayload.code,
        question_text: questionPayload.question_text,
        short_label: questionPayload.short_label,
        question_type: questionPayload.question_type,
        is_scored: questionPayload.is_scored,
        option_set_id: questionPayload.option_set_id,
        is_required_default: questionPayload.is_required_default,
        metadata: questionPayload.metadata,
      });
      if (constructId) {
        await updateConstructItem(constructId, itemId, { weight, scoring_direction: scoringDirection });
      }
      return question;
    },
    onSuccess: () => {
      invalidateInstrument();
      setItemDrawer(null);
    },
  });

  const handleEditItem = async (treeItem, construct) => {
    const full = await getItem(treeItem.id);
    setItemDrawer({ mode: 'edit', constructId: construct.id, item: { ...full, weight: treeItem.weight, scoring_direction: treeItem.scoring_direction } });
  };

  if (isLoadingInstrument) return <LoadingState label="Cargando estructura..." />;

  if (!versionId) {
    return (
      <Card className="py-10">
        <EmptyState title="Inicializa el cuestionario del proyecto." description="El instrumento es el contenedor metodológico; dentro organizarás variables, dimensiones y preguntas.">
          <button type="button" onClick={onCreateInstrument} disabled={isCreatingInstrument} className="colmena-button-primary">
            <ClipboardList size={16} className="mr-1" />
            {isCreatingInstrument ? 'Inicializando...' : 'Inicializar cuestionario'}
          </button>
        </EmptyState>
      </Card>
    );
  }

  return (
    <div className="min-w-0">
      {isLocked ? (
        <div className="m-4 flex gap-3 rounded-2xl border border-amber/20 bg-yellowSoft p-4">
          <LockKeyhole size={18} className="mt-0.5 shrink-0 text-yellowDark" />
          <div>
            <p className="text-sm font-semibold text-dark">Instrumento oficial / protegido</p>
            <p className="mt-1 text-xs text-yellowDark">
              {LOCK_MESSAGES[tree?.lock_reason] || 'La estructura de este instrumento está bloqueada en su estado actual.'}
            </p>
          </div>
        </div>
      ) : null}
      <Card padded={false} className="rounded-none border-x-0">
        <div className="flex items-center justify-between border-b border-border px-4 py-4">
          <div>
            <p className="text-sm font-semibold text-dark">Estructura del proyecto</p>
            <p className="mt-0.5 text-xs text-muted">Selecciona una variable y organiza dentro sus dimensiones y preguntas directas.</p>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => setView('tree')} className={`colmena-pill-tab ${view === 'tree' ? 'active' : ''}`}>
              <ListTree size={13} className="mr-1" />
              Árbol
            </button>
            <button type="button" onClick={() => setView('matrix')} className={`colmena-pill-tab ${view === 'matrix' ? 'active' : ''}`}>
              <LayoutGrid size={13} className="mr-1" />
              Matriz
            </button>
          </div>
        </div>

        <div>
          {view === 'tree' ? (
            isLoadingTree || !tree ? (
              <LoadingState label="Cargando árbol..." />
            ) : (
              <InstrumentTreeView
                  tree={tree}
                  readOnly={isLocked}
                  selectedVariableId={selectedVariableId}
                  onSelectVariable={setSelectedVariableId}
                  onAddVariable={() => openStructureModal({ type: 'variable', parent: null })}
                  onAddDimension={(parent) => openStructureModal({ type: 'dimension', parent })}
                  onAddSubdimension={(parent) => openStructureModal({ type: 'subdimension', parent })}
                  onAddItem={(construct) => !isLocked && setItemDrawer({ mode: 'create', constructId: construct.id })}
                  onEditItem={isLocked ? undefined : handleEditItem}
                />
            )
          ) : isLoadingMatrix || !matrix ? (
            <div className="p-4">
              <LoadingState label="Cargando matriz..." />
            </div>
          ) : (
            <InstrumentMatrixView matrix={matrix} />
          )}
        </div>
      </Card>

      {structureModal ? (
        <StructureNodeModal
          type={structureModal.type}
          parent={structureModal.parent}
          usedCodes={Array.from(
            collectConstructCodes(tree?.variables),
          )}
          onClose={() => setStructureModal(null)}
          isSubmitting={
            addVariableMutation.isPending || addDimensionMutation.isPending || addSubdimensionMutation.isPending
          }
          submitError={
            structureModal.type === 'variable' ? addVariableMutation.error
              : structureModal.type === 'dimension' ? addDimensionMutation.error
                : addSubdimensionMutation.error
          }
          onSubmit={(values) => {
            if (structureModal.type === 'variable') {
              addVariableMutation.mutate(values);
            } else if (structureModal.type === 'dimension') {
              addDimensionMutation.mutate({ parent: structureModal.parent, ...values });
            } else {
              addSubdimensionMutation.mutate({ parent: structureModal.parent, ...values });
            }
          }}
        />
      ) : null}

      {itemDrawer ? (
        <ItemEditorDrawer
          item={itemDrawer.mode === 'edit' ? itemDrawer.item : null}
          scales={likertScales}
          onClose={() => setItemDrawer(null)}
          isSubmitting={createItemMutation.isPending || updateItemMutation.isPending}
          submitError={createItemMutation.error || updateItemMutation.error}
          onSubmit={(payload) => {
            if (itemDrawer.mode === 'create') {
              createItemMutation.mutate({ constructId: itemDrawer.constructId, payload });
            } else {
              updateItemMutation.mutate({ itemId: itemDrawer.item.id, constructId: itemDrawer.constructId, payload });
            }
          }}
        />
      ) : null}
    </div>
  );
}

export default function ProjectConstructorPage() {
  const { projectId } = useParams();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState('variables');
  useActiveProject(projectId);

  const { data: project, isLoading, error } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
    enabled: Boolean(projectId),
    retry: false,
  });

  const { data: instruments = [], isLoading: isLoadingInstruments } = useProjectInstruments(
    projectId,
    project?.metadata,
  );

  const preferredInstrumentId = Number(project?.metadata?.instrument_id || 0);
  const activeInstrument =
    instruments.find((instrument) => instrument.id === preferredInstrumentId) || instruments[0] || null;

  const { data: readiness, isFetching: isLoadingReadiness } = useQuery({
    queryKey: ['censopas-readiness', activeInstrument?.versionId],
    queryFn: () => getCensopasReadiness(activeInstrument.versionId),
    enabled: Boolean(activeInstrument?.versionId),
    retry: false,
  });
  // Sólo instrumentos CENSOPAS corta/media resuelven un version_kind conocido;
  // para el resto (proyectos académicos genéricos) el checklist no aplica.
  const showReadinessPanel = Boolean(readiness && readiness.version_kind !== 'UNKNOWN');

  const createInstrumentMutation = useMutation({
    mutationFn: async () => {
      if (activeInstrument && !activeInstrument.versionId) {
        await createInstrumentVersion(activeInstrument.id, { version_code: 'v1', status: 'DRAFT' });
        return activeInstrument;
      }
      const instrument = await createProjectInstrument(projectId, {
        owner_user_id: user.id,
        name: `${project.name} — Cuestionario`,
      });
      const version = await createInstrumentVersion(instrument.id, { version_code: 'v1', status: 'DRAFT' });

      // Los campos singulares se conservan sólo como compatibilidad para
      // clientes anteriores; el catálogo real ya es uno-a-muchos.
      if (!project.metadata?.instrument_id) {
        await updateProject(projectId, {
          metadata: {
            ...(project.metadata || {}),
            instrument_id: instrument.id,
            instrument_version_id: version.id,
          },
        });
      }
      return instrument;
    },
    onSuccess: (instrument) => {
      if (!instrument) return;
      queryClient.invalidateQueries({ queryKey: ['projectInstruments', String(projectId)] });
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
    },
  });

  if (!projectId) {
    return <NewProjectStep ownerUserId={user?.id} />;
  }

  if (isLoading) return <LoadingState label="Cargando proyecto..." />;
  if (error instanceof ApiError && error.status === 404) return <ProjectMissingState />;
  if (error) return <ErrorState message="No pudimos cargar el proyecto." />;

  const sections = [
    {
      key: 'variables',
      label: 'Estructura',
      description: 'Variables, dimensiones y preguntas.',
      icon: ClipboardList,
    },
    {
      key: 'escalas',
      label: 'Escalas Likert',
      description: 'Opciones y valores reutilizables.',
      icon: Scale,
    },
    {
      key: 'exogenas',
      label: 'Datos exógenos',
      description: 'Perfil y segmentación sin scoring.',
      icon: UserRound,
    },
    {
      key: 'baremos',
      label: 'Baremos',
      description: 'Niveles, cortes e interpretación.',
      icon: Gauge,
    },
  ];

  // Si el proyecto deja de ser Académico (o venimos de un tab guardado stale),
  // no te dejes en una pestaña que ya no existe en `sections`.
  const activeTab = sections.some((section) => section.key === tab) ? tab : 'variables';

  return (
    <div className="colmena-page">
      <PageHeader
        eyebrow="Constructor"
        title={project.name}
        description="Organiza la medición en variables con dimensiones y preguntas directas. El cuestionario funciona sólo como contenedor metodológico."

      />

      {showReadinessPanel ? (
        <CensopasReadinessPanel readiness={readiness} isLoading={isLoadingReadiness} />
      ) : null}

      <div className="grid min-h-0 flex-1 grid-cols-1 overflow-hidden rounded-2xl border border-border lg:grid-cols-[210px_minmax(0,1fr)]">
        <nav className="flex flex-row gap-2 overflow-x-auto border-b border-border bg-white p-2 lg:flex-col lg:border-b-0 lg:border-r">
          {sections.map((section) => {
            const Icon = section.icon;
            const isActive = activeTab === section.key;
            return (
              <button
                key={section.key}
                type="button"
                onClick={() => setTab(section.key)}
                className={`flex min-w-40 flex-1 items-start gap-2.5 rounded-xl border px-3 py-2.5 text-left transition lg:min-w-0 lg:flex-none ${
                  isActive
                    ? 'border-amber/40 bg-gradient-to-br from-amber/10 to-amber/5 shadow-sm'
                    : 'border-border bg-white hover:border-amber/30 hover:bg-[#fafbfc]'
                }`}
              >
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                    isActive ? 'bg-amber text-white' : 'bg-amber/10 text-amber'
                  }`}
                >
                  <Icon size={16} />
                </div>
                <div className="hidden sm:block">
                  <p className="text-sm font-semibold text-dark">{section.label}</p>
                  <p className="mt-0.5 text-xs text-muted">{section.description}</p>
                </div>
              </button>
            );
          })}
        </nav>

        <section className="min-w-0 overflow-hidden bg-white">
          {activeTab === 'variables' ? (
            <InstrumentTab
              projectId={Number(projectId)}
              versionId={activeInstrument?.versionId}
              isLoadingInstrument={isLoadingInstruments}
              onCreateInstrument={() => createInstrumentMutation.mutate()}
              isCreatingInstrument={createInstrumentMutation.isPending}
            />
          ) : null}
          {activeTab === 'escalas' ? <LikertScaleManager versionId={activeInstrument?.versionId} /> : null}
          {activeTab === 'exogenas' ? <ExogenousFieldsManager projectId={Number(projectId)} versionId={activeInstrument?.versionId} /> : null}
          {activeTab === 'baremos' ? <BaremBuilder versionId={activeInstrument?.versionId} projectId={Number(projectId)} /> : null}
        </section>
      </div>
    </div>
  );
}
