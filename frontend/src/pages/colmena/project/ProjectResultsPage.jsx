import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { BarChart3 } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { useActiveProject } from '../../../hooks/useActiveProject.js';
import { getProject } from '../../../api/projects.js';
import { listVariables } from '../../../api/variables.js';
import {
  getDataDictionary,
  getLongDataset,
  getResponseDescriptives,
  getResultsOverview,
  getWideDataset,
  listStudies,
} from '../../../api/studies.js';
import { getAnalyticsMethods, runAnalysis } from '../../../api/analytics.js';

import { PageHeader } from '../../../components/layout/PageHeader.jsx';
import { Card } from '../../../components/ui/Card.jsx';
import { Button } from '../../../components/ui/Button.jsx';
import { EmptyState } from '../../../components/ui/EmptyState.jsx';
import { LoadingState } from '../../../components/ui/LoadingState.jsx';
import { ProjectMissingState } from '../../../components/colmena/ProjectMissingState.jsx';
import StudySelector from '../../../components/colmena/StudySelector.jsx';
import CensopasDimensionsPanel from '../../../components/colmena/results/CensopasDimensionsPanel.jsx';
import DimensionDashboardTab from '../../../components/colmena/results/DimensionDashboardTab.jsx';
import ResponseMatrixTab from '../../../components/colmena/results/ResponseMatrixTab.jsx';
import BaremResultsPanel from '../../../components/colmena/results/BaremResultsPanel.jsx';
import EvolutionPanel from '../../../components/colmena/results/EvolutionPanel.jsx';
import UnitResultsPanel from '../../../components/colmena/results/UnitResultsPanel.jsx';
import NormalityPanel from '../../../components/colmena/results/NormalityPanel.jsx';
import { SegmentationPanel, SpearmanPanel } from '../../../components/colmena/results/SpearmanPanel.jsx';

const TABS = [
  { key: 'comparison', label: 'Comparar variables' },
  { key: 'dimensions', label: 'Dimensiones' },
  { key: 'subdimensions', label: 'Subdimensiones' },
  { key: 'evolution', label: 'Evolución' },
  { key: 'baremos', label: 'Baremos' },
  { key: 'units', label: 'Unidades' },
  { key: 'normality', label: 'Normalidad' },
  { key: 'spearman', label: 'Spearman' },
  { key: 'segmentation', label: 'Segmentación' },
  { key: 'analytics', label: 'Otros análisis' },
  { key: 'dictionary', label: 'Diccionario' },
  { key: 'long', label: 'Dataset largo' },
  { key: 'wide', label: 'Dataset ancho' },
];

const SIMPLE_METHODS = [
  { code: 'describe', label: 'Descriptivos' },
  { code: 'frequencies', label: 'Frecuencias' },
];

function GenericTable({ columns, rows }) {
  if (rows.length === 0) {
    return (
      <div className="p-4">
        <EmptyState title="Sin datos todavía" description="Esta vista se llenará cuando el estudio tenga respuestas." />
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="bg-surfaceSoft">
            {columns.map((col) => (
              <th
                key={col}
                className="border-b border-r border-border px-4 py-2.5 text-[11px] font-bold uppercase tracking-[0.06em] text-muted last:border-r-0"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="transition hover:bg-[#fafbfc]">
              {columns.map((col) => (
                <td key={col} className="border-b border-r border-border px-4 py-2.5 font-mono text-xs text-dark last:border-r-0">
                  {String(row[col] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function VariableComparisonPanel({ projectId }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['variableResultsComparison', projectId],
    queryFn: async () => {
      const studiesPage = await listStudies(projectId, { page: 1, pageSize: 100 });
      return Promise.all(
        (studiesPage?.items || [])
          .filter((study) => study.instrument_version_id)
          .map((study) => getResultsOverview(study.id)),
      );
    },
    enabled: Boolean(projectId),
  });

  if (isLoading) return <LoadingState label="Comparando variables..." />;
  if (isError) return <div className="p-4 text-sm font-medium text-danger">No se pudo construir la comparación.</div>;

  const variableResults = (data || []).flatMap((overview) =>
    (overview.results || [])
      .filter((result) => result.parent_id === null && !result.suppressed && result.mean_score !== null)
      .map((result) => ({
        variableKey: `${overview.instrument_version_id || overview.instrument_id || overview.study_id}:${result.construct_id}`,
        code: result.construct_code,
        name: result.construct_name,
        instrumentName: overview.instrument_name || 'Cuestionario del proyecto',
        nValid: result.n_valid,
        weightedScore: result.mean_score * result.n_valid,
      })),
  );

  const grouped = [...variableResults.reduce((groups, result) => {
    const current = groups.get(result.variableKey) || {
      variableKey: result.variableKey,
      code: result.code,
      name: result.name,
      instrumentName: result.instrumentName,
      applications: 0,
      nValid: 0,
      weightedScore: 0,
    };
    current.applications += 1;
    current.nValid += result.nValid;
    current.weightedScore += result.weightedScore;
    groups.set(result.variableKey, current);
    return groups;
  }, new Map()).values()].map((group) => ({
    ...group,
    chartLabel: `${group.name} (${group.code})`,
    meanScore: group.nValid ? Number((group.weightedScore / group.nValid).toFixed(2)) : null,
  }));
  const chartData = grouped.filter((group) => group.meanScore !== null);

  if (!data?.length) {
    return (
      <div className="p-4">
        <EmptyState title="Aún no hay estudios para comparar" description="Crea una aplicación y calcula sus resultados." />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 p-4">
      <div>
        <p className="text-sm font-semibold text-dark">Comparación de variables del proyecto</p>
        <p className="mt-1 text-xs text-muted">
          Cada barra representa una variable raíz en escala 0–100. Sus dimensiones se conservan como desglose y no se mezclan como variables independientes.
        </p>
      </div>

      {chartData.length ? (
        <div className="h-72 w-full rounded-2xl border border-border p-3">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.25)" />
              <XAxis dataKey="chartLabel" tick={{ fontSize: 12 }} interval={0} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(value) => [`${Number(value).toFixed(1)} / 100`, 'Puntaje de variable']} />
              <Bar dataKey="meanScore" name="Puntaje de variable" fill="#F5B21A" radius={[7, 7, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <EmptyState title="Faltan variables calculadas" description="Ejecuta el cálculo; sólo se comparan las variables raíz con resultados publicables." />
      )}

      <div className="overflow-x-auto rounded-2xl border border-border">
        <table className="w-full text-left text-sm">
          <thead className="bg-surfaceSoft">
            <tr>
              {['Variable', 'Código', 'Cuestionario', 'Aplicaciones', 'Respuestas válidas', 'Puntaje'].map((label) => (
                <th key={label} className="px-4 py-3 text-xs font-semibold text-muted">{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grouped.map((group) => (
              <tr key={group.variableKey} className="border-t border-border">
                <td className="px-4 py-3 font-medium text-dark">{group.name}</td>
                <td className="px-4 py-3 font-mono text-xs">{group.code}</td>
                <td className="px-4 py-3">{group.instrumentName}</td>
                <td className="px-4 py-3">{group.applications}</td>
                <td className="px-4 py-3">{group.nValid}</td>
                <td className="px-4 py-3 font-semibold text-dark">
                  {group.meanScore === null ? 'Sin cálculo' : `${group.meanScore.toFixed(1)} / 100`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AnalyticsTab({ projectId, studyId }) {
  const [method, setMethod] = useState('describe');
  const [selectedVariables, setSelectedVariables] = useState([]);

  const { data: variablesData } = useQuery({
    queryKey: ['variables', projectId],
    queryFn: () => listVariables(projectId, { page: 1, pageSize: 100 }),
    enabled: Boolean(projectId),
  });
  const variables = variablesData?.items ?? [];

  useQuery({ queryKey: ['analyticsMethods'], queryFn: getAnalyticsMethods });

  const runMutation = useMutation({
    mutationFn: () => runAnalysis(method, studyId, { variable_ids: selectedVariables }),
  });

  const toggleVariable = (id) => {
    setSelectedVariables((prev) => (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]));
  };

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-[220px_minmax(0,1fr)]">
        <label className="flex flex-col gap-2">
          <span className="colmena-label">Método</span>
          <select className="colmena-input h-10 px-4 text-sm text-dark" value={method} onChange={(event) => setMethod(event.target.value)}>
            {SIMPLE_METHODS.map((m) => (
              <option key={m.code} value={m.code}>
                {m.label}
              </option>
            ))}
          </select>
        </label>

        <div>
          <p className="colmena-label mb-2">Variables</p>
          <div className="flex flex-wrap gap-2">
            {variables.map((variable) => (
              <button
                key={variable.id}
                type="button"
                onClick={() => toggleVariable(variable.id)}
                className={`colmena-badge cursor-pointer ${
                  selectedVariables.includes(variable.id) ? 'bg-amber text-white' : 'bg-amber/10 text-yellowDark'
                }`}
              >
                {variable.code}
              </button>
            ))}
          </div>
        </div>
      </div>

      <Button
        variant="primary"
        size="sm"
        onClick={() => runMutation.mutate()}
        loading={runMutation.isPending}
        disabled={selectedVariables.length === 0}
        className="w-40"
      >
        Ejecutar
      </Button>

      {runMutation.isError ? <p className="text-sm font-medium text-danger">No se pudo ejecutar el análisis.</p> : null}

      {runMutation.data ? (
        <div className="-mx-6 -mb-6 border-t border-border">
          <GenericTable
            columns={['result_code', 'n_valid', 'numeric_value', 'statistic_value', 'p_value']}
            rows={runMutation.data.results.map((r) => ({
              result_code: r.result_code || r.result_type,
              n_valid: r.n_valid ?? '—',
              numeric_value: r.numeric_value ?? '—',
              statistic_value: r.statistic_value ?? '—',
              p_value: r.p_value ?? '—',
            }))}
          />
        </div>
      ) : null}
    </div>
  );
}

export default function ProjectResultsPage() {
  const { projectId } = useParams();
  const [studyId, setStudyId] = useState(null);
  const [tab, setTab] = useState('comparison');
  useActiveProject(projectId);

  const { data: project, isLoading: isLoadingProject } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });

  const { data: dictionary } = useQuery({
    queryKey: ['dataDictionary', studyId],
    queryFn: () => getDataDictionary(studyId),
    enabled: Boolean(studyId) && tab === 'dictionary',
  });
  const { data: longDataset } = useQuery({
    queryKey: ['longDataset', studyId],
    queryFn: () => getLongDataset(studyId),
    enabled: Boolean(studyId) && tab === 'long',
  });
  const { data: wideDataset, isLoading: isLoadingWideDataset } = useQuery({
    queryKey: ['wideDataset', studyId],
    queryFn: () => getWideDataset(studyId),
    enabled: Boolean(studyId) && tab === 'wide',
  });
  const { data: overview } = useQuery({
    queryKey: ['resultsOverview', studyId],
    queryFn: () => getResultsOverview(studyId),
    enabled: Boolean(studyId) && tab === 'segmentation',
  });
  const { data: descriptives, isLoading: isLoadingDescriptives } = useQuery({
    queryKey: ['responseDescriptives', studyId],
    queryFn: () => getResponseDescriptives(studyId),
    enabled: Boolean(studyId) && tab === 'wide',
  });

  if (isLoadingProject) return <LoadingState label="Cargando..." />;
  if (!project) return <ProjectMissingState />;

  return (
    <div className="colmena-page space-y-6">
      <ProjectWorkspaceHeader activeTab="results" />

      <Card>
        <StudySelector projectId={projectId} studyId={studyId} onStudyChange={setStudyId} />
      </Card>

      <Card padded={false} className="rounded-none border-x-0">
          <div className="flex gap-2 overflow-x-auto border-b border-border px-4 py-4">
            {TABS.map((t) => (
              <button key={t.key} type="button" onClick={() => setTab(t.key)} className={`colmena-pill-tab ${tab === t.key ? 'active' : ''}`}>
                {t.label}
              </button>
            ))}
          </div>

          {tab === 'comparison' ? <VariableComparisonPanel projectId={Number(projectId)} /> : null}
          {tab === 'evolution' ? <EvolutionPanel projectId={Number(projectId)} /> : null}
          {tab !== 'comparison' && tab !== 'evolution' && !studyId ? (
            <div className="p-4">
              <EmptyState title="Elige una aplicación o estudio." description="Podrás consultar el dataset y ejecutar análisis sobre sus respuestas.">
                <div className="mx-auto flex h-10 w-11 items-center justify-center rounded-2xl bg-amber/10 text-amber">
                  <BarChart3 size={20} />
                </div>
              </EmptyState>
            </div>
          ) : null}
          {studyId && tab === 'dictionary' ? (
            <GenericTable columns={['variable_code', 'label', 'data_type', 'measurement_level', 'role']} rows={dictionary?.entries || []} />
          ) : null}
          {studyId && tab === 'long' ? (
            <GenericTable
              columns={['respondent_public_id', 'variable_code', 'raw_code', 'numeric_value', 'text_value', 'is_missing']}
              rows={longDataset?.rows || []}
            />
          ) : null}
          {studyId && tab === 'wide' ? (
            <ResponseMatrixTab
              dataset={wideDataset}
              descriptives={descriptives}
              isLoading={isLoadingWideDataset || isLoadingDescriptives}
              projectId={Number(projectId)}
            />
          ) : null}
          {studyId && tab === 'analytics' ? <AnalyticsTab projectId={projectId} studyId={studyId} /> : null}
          {studyId && tab === 'dimensions' ? <DimensionDashboardTab projectId={Number(projectId)} studyId={studyId} /> : null}
          {studyId && tab === 'subdimensions' ? (
            <CensopasDimensionsPanel
              studyId={studyId}
              constructType="SUBDIMENSION"
              title="Subdimensiones"
              emptyTitle="Sin subdimensiones"
              emptyDescription="Esta aplicación usa la versión corta (D1-D6) o el instrumento no tiene subdimensiones configuradas."
            />
          ) : null}
          {studyId && tab === 'baremos' ? <BaremResultsPanel studyId={studyId} /> : null}
          {studyId && tab === 'units' ? <UnitResultsPanel studyId={studyId} /> : null}
          {studyId && tab === 'normality' ? <NormalityPanel studyId={studyId} /> : null}
          {studyId && tab === 'spearman' ? <SpearmanPanel projectId={Number(projectId)} studyId={studyId} /> : null}
          {studyId && tab === 'segmentation' ? (
            <SegmentationPanel
              projectId={Number(projectId)}
              studyId={studyId}
              versionId={overview?.instrument_version_id}
              overview={overview}
            />
          ) : null}
      </Card>
    </div>
  );
}
