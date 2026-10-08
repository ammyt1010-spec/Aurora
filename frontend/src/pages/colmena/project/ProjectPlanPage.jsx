import { Fragment, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, CalendarClock, CheckCircle2, ClipboardList, Clock, Gauge, ListTodo, Plus, Target } from 'lucide-react';

import { useActiveProject } from '../../../hooks/useActiveProject.js';
import { getProject } from '../../../api/projects.js';
import { getResultsOverview } from '../../../api/studies.js';
import {
  addActionPlanItem,
  addKpiMeasurement,
  createActionPlan,
  createKpi,
  listActionPlanItems,
  listActionPlans,
  listKpiMeasurements,
  listKpis,
  updateActionPlanItem,
} from '../../../api/bsc.js';

import { PageHeader } from '../../../components/layout/PageHeader.jsx';
import { Card } from '../../../components/ui/Card.jsx';
import { Button } from '../../../components/ui/Button.jsx';
import { EmptyState } from '../../../components/ui/EmptyState.jsx';
import { LoadingState } from '../../../components/ui/LoadingState.jsx';
import MetricCard from '../../../components/ui/MetricCard.jsx';
import { ProjectMissingState } from '../../../components/colmena/ProjectMissingState.jsx';
import StudySelector from '../../../components/colmena/StudySelector.jsx';
import { formatNumber, formatPercent } from '../../../utils/format.js';
import { dominantBand, unfavorablePct } from '../../../utils/scoringResults.js';

// El backend es la única fuente de verdad del enum de estado — el frontend
// no debe permitir valores fuera de `ACTION_PLAN_ITEM_STATUSES`
// (app/core/action_plan_status.py). OVERDUE nunca se envía: es
// `effective_status`, calculado siempre en backend.
const ITEM_STATUSES = ['PENDING', 'IN_PROGRESS', 'DONE', 'BLOCKED', 'CANCELLED'];
const STATUS_LABELS = {
  PENDING: 'Pendiente',
  IN_PROGRESS: 'En curso',
  DONE: 'Completada',
  BLOCKED: 'Bloqueada',
  CANCELLED: 'Cancelada',
  OVERDUE: 'Vencida',
};
const STATUS_BADGE_CLASS = {
  PENDING: 'bg-surfaceSoft text-muted',
  IN_PROGRESS: 'bg-amber/15 text-yellowDark',
  DONE: 'bg-success/15 text-success',
  BLOCKED: 'bg-danger/15 text-danger',
  CANCELLED: 'bg-surfaceSoft text-muted line-through',
  OVERDUE: 'bg-danger/15 text-danger',
};

const emptyItemForm = {
  title: '',
  finding: '',
  origin_hypothesis: '',
  action_description: '',
  responsible_label: '',
  priority: '',
  due_date: '',
  construct_id: '',
};

const emptyKpiForm = {
  action_plan_item_id: '',
  code: '',
  name: '',
  unit: '',
  baseline_value: '',
  target_value: '',
  frequency: '',
};

function EffectiveStatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ${STATUS_BADGE_CLASS[status] || 'bg-surfaceSoft text-muted'}`}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function PlanSummary({ items }) {
  const total = items.length;
  const pending = items.filter((item) => item.effective_status === 'PENDING').length;
  const inProgress = items.filter((item) => item.effective_status === 'IN_PROGRESS').length;
  const done = items.filter((item) => item.effective_status === 'DONE').length;
  const overdue = items.filter((item) => item.effective_status === 'OVERDUE').length;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      <MetricCard icon={ListTodo} label="Acciones totales" value={total} />
      <MetricCard icon={Clock} label="Pendientes" value={pending} />
      <MetricCard icon={Gauge} label="En progreso" value={inProgress} />
      <MetricCard icon={CheckCircle2} label="Completadas" value={done} />
      <MetricCard icon={AlertTriangle} label="Vencidas" value={overdue} />
    </div>
  );
}

function PrioritiesByConstruct({ dimensions, items }) {
  if (!dimensions.length) return null;
  const countsByConstruct = new Map();
  for (const item of items) {
    if (item.construct_id == null) continue;
    countsByConstruct.set(item.construct_id, (countsByConstruct.get(item.construct_id) || 0) + 1);
  }
  const rows = [...dimensions].sort(
    (a, b) => (a.priority_rank ?? Infinity) - (b.priority_rank ?? Infinity),
  );

  return (
    <Card>
      <p className="text-sm font-semibold text-dark">Prioridades por constructo</p>
      <p className="mb-3 mt-1 text-xs text-muted">
        Clasificación y prioridad calculadas por el backend — no se recalculan aquí.
      </p>
      <div className="divide-y divide-border/70">
        {rows.map((result) => {
          const dominant = dominantBand(result);
          const actionsCount = countsByConstruct.get(result.construct_id) || 0;
          return (
            <div key={result.construct_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <div>
                <p className="text-sm font-medium text-dark">
                  {result.construct_name}
                  {result.suppressed ? <span className="ml-1 text-xs text-muted">(suprimido)</span> : null}
                </p>
                {result.priority_rank ? (
                  <p className="text-xs text-muted">Prioridad #{result.priority_rank}</p>
                ) : null}
              </div>
              <div className="flex items-center gap-2">
                {!result.suppressed && dominant ? (
                  <span
                    className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold text-white"
                    style={{ background: dominant.color_hint || '#6b7280' }}
                  >
                    {dominant.label} · {formatPercent(unfavorablePct(result), { decimals: 0 })}
                  </span>
                ) : null}
                <span className="colmena-badge bg-amber/10 text-yellowDark">
                  {actionsCount} {actionsCount === 1 ? 'acción' : 'acciones'}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function ActionKpis({ item, kpis }) {
  const linked = kpis.filter((kpi) => kpi.action_plan_item_id === item.id);
  if (!linked.length) {
    return <p className="mt-2 text-xs text-muted">Sin KPI vinculado a esta acción todavía.</p>;
  }
  return (
    <div className="mt-2 flex flex-col gap-2">
      {linked.map((kpi) => (
        <div key={kpi.id} className="rounded-xl border border-border p-3 text-xs">
          <p className="font-semibold text-dark">
            {kpi.name} {kpi.code ? <span className="font-mono text-muted">({kpi.code})</span> : null}
          </p>
          <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-muted sm:grid-cols-4">
            <span>Línea base: <span className="font-semibold text-dark">{kpi.baseline_value ?? '—'}</span></span>
            <span>Actual: <span className="font-semibold text-dark">{kpi.current_value ?? '—'}</span></span>
            <span>Meta: <span className="font-semibold text-dark">{kpi.target_value ?? '—'}</span></span>
            <span>Unidad: <span className="font-semibold text-dark">{kpi.unit || '—'}</span></span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ActionPlanSection({ studyId }) {
  const queryClient = useQueryClient();
  const [selectedPlanId, setSelectedPlanId] = useState(null);
  const [newPlanName, setNewPlanName] = useState('');
  const [itemForm, setItemForm] = useState(emptyItemForm);
  const [expandedItemId, setExpandedItemId] = useState(null);

  const { data: plans = [], isLoading: isLoadingPlans } = useQuery({
    queryKey: ['actionPlans', studyId],
    queryFn: () => listActionPlans(studyId),
    enabled: Boolean(studyId),
  });
  const activePlanId = selectedPlanId || plans[0]?.id || null;

  const { data: items = [], isLoading: isLoadingItems } = useQuery({
    queryKey: ['actionPlanItems', activePlanId],
    queryFn: () => listActionPlanItems(activePlanId),
    enabled: Boolean(activePlanId),
  });

  const { data: overview } = useQuery({
    queryKey: ['resultsOverview', studyId],
    queryFn: () => getResultsOverview(studyId),
    enabled: Boolean(studyId),
  });
  const dimensions = (overview?.results || []).filter((r) => r.construct_type === 'DIMENSION');

  const { data: kpis = [] } = useQuery({
    queryKey: ['kpis', studyId],
    queryFn: () => listKpis(studyId),
    enabled: Boolean(studyId),
  });

  const createPlanMutation = useMutation({
    mutationFn: () => createActionPlan(studyId, { name: newPlanName }),
    onSuccess: (plan) => {
      setNewPlanName('');
      queryClient.invalidateQueries({ queryKey: ['actionPlans', studyId] });
      setSelectedPlanId(plan.id);
    },
  });

  const addItemMutation = useMutation({
    mutationFn: () =>
      addActionPlanItem(activePlanId, {
        title: itemForm.title,
        finding: itemForm.finding || null,
        origin_hypothesis: itemForm.origin_hypothesis || null,
        action_description: itemForm.action_description,
        responsible_label: itemForm.responsible_label || null,
        priority: itemForm.priority ? Number(itemForm.priority) : null,
        due_date: itemForm.due_date || null,
        construct_id: itemForm.construct_id ? Number(itemForm.construct_id) : null,
        // Trazabilidad al AnalysisRun canónico que originó la acción — nunca
        // se copian porcentajes/n, solo el ID de la corrida y el constructo.
        analysis_run_id: itemForm.construct_id ? overview?.analysis_run_id ?? null : null,
      }),
    onSuccess: () => {
      setItemForm(emptyItemForm);
      queryClient.invalidateQueries({ queryKey: ['actionPlanItems', activePlanId] });
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ itemId, status }) => updateActionPlanItem(itemId, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['actionPlanItems', activePlanId] }),
  });

  if (!studyId) {
    return (
      <div className="p-4">
        <EmptyState title="Elige una aplicación o estudio." description="El plan preventivo se organiza por cada aplicación del instrumento." />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <Card>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <label className="flex min-w-[240px] flex-1 flex-col gap-2">
            <span className="colmena-label">Plan de acción</span>
            {isLoadingPlans ? (
              <LoadingState label="Cargando planes..." />
            ) : (
              <select
                className="colmena-input h-10 px-3 text-sm"
                value={activePlanId || ''}
                onChange={(event) => setSelectedPlanId(Number(event.target.value))}
              >
                {plans.length === 0 ? <option value="">Sin planes todavía</option> : null}
                {plans.map((plan) => (
                  <option key={plan.id} value={plan.id}>
                    {plan.name} ({plan.status})
                  </option>
                ))}
              </select>
            )}
          </label>
          <div className="flex items-end gap-2">
            <label className="flex flex-col gap-2">
              <span className="colmena-label">Nuevo plan</span>
              <input
                className="colmena-input h-10 px-3 text-sm"
                placeholder="Ej. Plan preventivo 2026"
                value={newPlanName}
                onChange={(event) => setNewPlanName(event.target.value)}
              />
            </label>
            <Button
              variant="secondary"
              onClick={() => createPlanMutation.mutate()}
              disabled={!newPlanName.trim() || createPlanMutation.isPending}
            >
              <Plus size={14} /> Crear plan
            </Button>
          </div>
        </div>
      </Card>

      {!activePlanId ? (
        <EmptyState title="Crea el primer plan de acción" description="Un plan agrupa las acciones preventivas priorizadas a partir de los resultados." />
      ) : (
        <>
          <PlanSummary items={items} />
          <PrioritiesByConstruct dimensions={dimensions} items={items} />

          <Card padded={false}>
            <div className="border-b border-border px-4 py-3">
              <p className="text-sm font-semibold text-dark">Acciones</p>
              <p className="text-xs text-muted">
                Hallazgo, hipótesis de origen y medida se registran por separado — la hipótesis es algo a
                contrastar, no una causa demostrada.
              </p>
            </div>
            {isLoadingItems ? (
              <div className="p-4">
                <LoadingState label="Cargando acciones..." />
              </div>
            ) : items.length === 0 ? (
              <div className="p-4">
                <EmptyState title="Sin acciones todavía" description="Agrega la primera acción preventiva abajo." />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-surfaceSoft text-xs uppercase text-muted">
                    <tr>
                      <th className="px-4 py-3">Hallazgo</th>
                      <th className="px-4 py-3">Hipótesis de origen</th>
                      <th className="px-4 py-3">Medida</th>
                      <th className="px-4 py-3">Responsable</th>
                      <th className="px-4 py-3">Plazo</th>
                      <th className="px-4 py-3">Indicador</th>
                      <th className="px-4 py-3">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => {
                      const dimension = dimensions.find((d) => d.construct_id === item.construct_id);
                      const isExpanded = expandedItemId === item.id;
                      return (
                        <Fragment key={item.id}>
                          <tr className="border-t border-border align-top">
                            <td className="px-4 py-3">
                              <p className="font-medium text-dark">{item.title}</p>
                              {dimension ? <p className="mt-0.5 text-xs text-muted">{dimension.construct_name}</p> : null}
                              {item.finding ? <p className="mt-1 text-xs text-muted">{item.finding}</p> : null}
                            </td>
                            <td className="px-4 py-3 text-xs text-muted">{item.origin_hypothesis || '—'}</td>
                            <td className="px-4 py-3 text-xs">{item.action_description}</td>
                            <td className="px-4 py-3 text-xs">{item.responsible_label || '—'}</td>
                            <td className="px-4 py-3 text-xs">{item.due_date || '—'}</td>
                            <td className="px-4 py-3">
                              <button
                                type="button"
                                className="text-xs font-semibold text-amber underline"
                                onClick={() => setExpandedItemId(isExpanded ? null : item.id)}
                              >
                                {isExpanded ? 'Ocultar KPI' : 'Ver KPI'}
                              </button>
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex flex-col gap-1.5">
                                <EffectiveStatusBadge status={item.effective_status} />
                                <select
                                  className="colmena-input h-8 px-2 text-xs"
                                  value={item.status}
                                  onChange={(event) => updateStatusMutation.mutate({ itemId: item.id, status: event.target.value })}
                                >
                                  {ITEM_STATUSES.map((status) => (
                                    <option key={status} value={status}>
                                      {STATUS_LABELS[status]}
                                    </option>
                                  ))}
                                </select>
                              </div>
                            </td>
                          </tr>
                          {isExpanded ? (
                            <tr className="border-t border-border bg-surfaceSoft/40">
                              <td colSpan={7} className="px-4 py-3">
                                <ActionKpis item={item} kpis={kpis} />
                              </td>
                            </tr>
                          ) : null}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card>
            <p className="mb-3 text-sm font-semibold text-dark">Agregar acción</p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <input className="colmena-input h-10 px-3 text-sm" placeholder="Título de la acción" value={itemForm.title} onChange={(e) => setItemForm((f) => ({ ...f, title: e.target.value }))} />
              <select className="colmena-input h-10 px-3 text-sm" value={itemForm.construct_id} onChange={(e) => setItemForm((f) => ({ ...f, construct_id: e.target.value }))}>
                <option value="">Sin dimensión asociada (medida organizacional genérica)</option>
                {dimensions.map((d) => (
                  <option key={d.construct_id} value={d.construct_id}>
                    {d.construct_name}
                    {d.suppressed ? ' (suprimido)' : ''}
                  </option>
                ))}
              </select>
              <input
                className="colmena-input h-10 px-3 text-sm sm:col-span-2"
                placeholder="Hallazgo (opcional)"
                value={itemForm.finding}
                onChange={(e) => setItemForm((f) => ({ ...f, finding: e.target.value }))}
              />
              <textarea
                className="colmena-input px-3 py-2 text-sm sm:col-span-2"
                rows={2}
                placeholder="Hipótesis de origen (opcional) — algo a contrastar, no una causa demostrada. Ej. carga elevada, plazos cortos o interrupciones."
                value={itemForm.origin_hypothesis}
                onChange={(e) => setItemForm((f) => ({ ...f, origin_hypothesis: e.target.value }))}
              />
              <textarea className="colmena-input px-3 py-2 text-sm sm:col-span-2" rows={2} placeholder="Descripción de la medida preventiva" value={itemForm.action_description} onChange={(e) => setItemForm((f) => ({ ...f, action_description: e.target.value }))} />
              <input className="colmena-input h-10 px-3 text-sm" placeholder="Responsable" value={itemForm.responsible_label} onChange={(e) => setItemForm((f) => ({ ...f, responsible_label: e.target.value }))} />
              <input className="colmena-input h-10 px-3 text-sm" type="number" min="1" placeholder="Prioridad (1 = más alta)" value={itemForm.priority} onChange={(e) => setItemForm((f) => ({ ...f, priority: e.target.value }))} />
              <input className="colmena-input h-10 px-3 text-sm" type="date" value={itemForm.due_date} onChange={(e) => setItemForm((f) => ({ ...f, due_date: e.target.value }))} />
            </div>
            <Button
              variant="primary"
              className="mt-3"
              onClick={() => addItemMutation.mutate()}
              disabled={!itemForm.title.trim() || !itemForm.action_description.trim() || addItemMutation.isPending}
            >
              <Plus size={14} /> Agregar acción
            </Button>
          </Card>
        </>
      )}
    </div>
  );
}

function KpiMeasurements({ kpiId }) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState('');
  const { data: measurements = [], isLoading } = useQuery({
    queryKey: ['kpiMeasurements', kpiId],
    queryFn: () => listKpiMeasurements(kpiId),
  });
  const mutation = useMutation({
    mutationFn: () =>
      addKpiMeasurement(kpiId, { measured_at: new Date().toISOString(), numeric_value: Number(value) }),
    onSuccess: () => {
      setValue('');
      queryClient.invalidateQueries({ queryKey: ['kpiMeasurements', kpiId] });
      queryClient.invalidateQueries({ queryKey: ['kpis'] });
    },
  });

  return (
    <div className="mt-2 border-t border-border pt-2">
      {isLoading ? null : measurements.length === 0 ? (
        <p className="text-xs text-muted">Sin mediciones registradas.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {measurements.map((m) => (
            <li key={m.id} className="text-xs text-muted">
              {new Date(m.measured_at).toLocaleDateString('es-PE')} — <span className="font-semibold text-dark">{m.numeric_value ?? m.text_value ?? '—'}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 flex items-center gap-2">
        <input
          className="colmena-input h-8 w-28 px-2 text-xs"
          type="number"
          placeholder="Valor"
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
        <Button variant="secondary" size="sm" onClick={() => mutation.mutate()} disabled={!value || mutation.isPending}>
          <CalendarClock size={12} /> Registrar seguimiento
        </Button>
      </div>
    </div>
  );
}

function KpiSection({ studyId }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(emptyKpiForm);
  const [expandedId, setExpandedId] = useState(null);

  const { data: kpis = [], isLoading } = useQuery({
    queryKey: ['kpis', studyId],
    queryFn: () => listKpis(studyId),
    enabled: Boolean(studyId),
  });

  const { data: plans = [] } = useQuery({
    queryKey: ['actionPlans', studyId],
    queryFn: () => listActionPlans(studyId),
    enabled: Boolean(studyId),
  });
  const { data: items = [] } = useQuery({
    queryKey: ['actionPlanItems', plans[0]?.id],
    queryFn: () => listActionPlanItems(plans[0].id),
    enabled: Boolean(plans[0]?.id),
  });
  const itemsById = new Map(items.map((item) => [item.id, item]));

  const createMutation = useMutation({
    mutationFn: () =>
      createKpi(studyId, {
        action_plan_item_id: form.action_plan_item_id ? Number(form.action_plan_item_id) : null,
        code: form.code || null,
        name: form.name,
        unit: form.unit || null,
        baseline_value: form.baseline_value ? Number(form.baseline_value) : null,
        target_value: form.target_value ? Number(form.target_value) : null,
        frequency: form.frequency || null,
      }),
    onSuccess: () => {
      setForm(emptyKpiForm);
      queryClient.invalidateQueries({ queryKey: ['kpis', studyId] });
    },
  });

  if (!studyId) {
    return (
      <div className="p-4">
        <EmptyState title="Elige una aplicación o estudio." description="Los KPIs se definen por cada aplicación del instrumento." />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <Card padded={false}>
        <div className="border-b border-border px-4 py-3">
          <p className="text-sm font-semibold text-dark">Indicadores de seguimiento (KPI)</p>
        </div>
        {isLoading ? (
          <div className="p-4">
            <LoadingState label="Cargando KPIs..." />
          </div>
        ) : kpis.length === 0 ? (
          <div className="p-4">
            <EmptyState title="Sin KPIs todavía" description="Define metas medibles para el seguimiento del plan preventivo." />
          </div>
        ) : (
          <div className="divide-y divide-border">
            {kpis.map((kpi) => {
              const linkedItem = kpi.action_plan_item_id ? itemsById.get(kpi.action_plan_item_id) : null;
              return (
                <div key={kpi.id} className="px-4 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-dark">
                        {kpi.name} {kpi.code ? <span className="font-mono text-xs text-muted">({kpi.code})</span> : null}
                      </p>
                      <p className="text-xs text-muted">
                        Acción: {linkedItem ? linkedItem.title : kpi.action_plan_item_id ? `#${kpi.action_plan_item_id}` : 'sin vincular'}
                      </p>
                      <p className="text-xs text-muted">
                        Línea base: {formatNumber(kpi.baseline_value)} · Actual: {formatNumber(kpi.current_value)} ·
                        Meta: {kpi.target_value ?? '—'} {kpi.unit || ''} · Frecuencia: {kpi.frequency || '—'}
                      </p>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => setExpandedId((id) => (id === kpi.id ? null : kpi.id))}>
                      <Gauge size={13} /> {expandedId === kpi.id ? 'Ocultar seguimiento' : 'Ver seguimiento'}
                    </Button>
                  </div>
                  {expandedId === kpi.id ? <KpiMeasurements kpiId={kpi.id} /> : null}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card>
        <p className="mb-3 text-sm font-semibold text-dark">Nuevo KPI</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <select
            className="colmena-input h-10 px-3 text-sm sm:col-span-3"
            value={form.action_plan_item_id}
            onChange={(e) => setForm((f) => ({ ...f, action_plan_item_id: e.target.value }))}
          >
            <option value="">Sin acción vinculada</option>
            {items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>
          <input className="colmena-input h-10 px-3 text-sm" placeholder="Nombre del indicador" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          <input className="colmena-input h-10 px-3 text-sm" placeholder="Código (opcional)" value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} />
          <input className="colmena-input h-10 px-3 text-sm" placeholder="Unidad (%, casos...)" value={form.unit} onChange={(e) => setForm((f) => ({ ...f, unit: e.target.value }))} />
          <input className="colmena-input h-10 px-3 text-sm" type="number" placeholder="Línea base" value={form.baseline_value} onChange={(e) => setForm((f) => ({ ...f, baseline_value: e.target.value }))} />
          <input className="colmena-input h-10 px-3 text-sm" type="number" placeholder="Meta" value={form.target_value} onChange={(e) => setForm((f) => ({ ...f, target_value: e.target.value }))} />
          <input className="colmena-input h-10 px-3 text-sm" placeholder="Frecuencia (mensual, trimestral...)" value={form.frequency} onChange={(e) => setForm((f) => ({ ...f, frequency: e.target.value }))} />
        </div>
        <Button variant="primary" className="mt-3" onClick={() => createMutation.mutate()} disabled={!form.name.trim() || createMutation.isPending}>
          <Target size={14} /> Crear KPI
        </Button>
      </Card>
    </div>
  );
}

export default function ProjectPlanPage() {
  const { projectId } = useParams();
  const [studyId, setStudyId] = useState(null);
  const [tab, setTab] = useState('actions');
  useActiveProject(projectId);

  const { data: project, isLoading: isLoadingProject } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });

  if (isLoadingProject) return <LoadingState label="Cargando..." />;
  if (!project) return <ProjectMissingState />;

  return (
    <div className="colmena-page space-y-6">
      <ProjectWorkspaceHeader activeTab="plan" />

      <Card>
        <StudySelector projectId={projectId} studyId={studyId} onStudyChange={setStudyId} />
      </Card>

      <Card padded={false} className="rounded-none border-x-0">
        <div className="flex gap-2 overflow-x-auto border-b border-border px-4 py-4">
          <button type="button" onClick={() => setTab('actions')} className={`colmena-pill-tab ${tab === 'actions' ? 'active' : ''}`}>
            <ClipboardList size={13} className="mr-1" /> Plan de acción
          </button>
          <button type="button" onClick={() => setTab('kpis')} className={`colmena-pill-tab ${tab === 'kpis' ? 'active' : ''}`}>
            <Gauge size={13} className="mr-1" /> KPIs
          </button>
        </div>
        {tab === 'actions' ? <ActionPlanSection studyId={studyId} /> : null}
        {tab === 'kpis' ? <KpiSection studyId={studyId} /> : null}
      </Card>
    </div>
  );
}
