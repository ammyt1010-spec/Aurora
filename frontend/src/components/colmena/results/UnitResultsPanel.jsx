import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PlusCircle, ShieldAlert, ShieldCheck, Users } from 'lucide-react';

import {
  createStudyUnit,
  createStudyUnitType,
  getCensopasResults,
  getCensopasUnitResults,
  getStudy,
  listStudyUnitTypes,
  listStudyUnits,
} from '../../../api/studies.js';
import { getCensopasReadiness } from '../../../api/instruments.js';
import { formatNumber } from '../../../utils/format.js';
import { Button } from '../../ui/Button.jsx';
import { Card } from '../../ui/Card.jsx';
import { EmptyState } from '../../ui/EmptyState.jsx';
import { LoadingState } from '../../ui/LoadingState.jsx';
import CensopasReadinessPanel from '../instruments/CensopasReadinessPanel.jsx';

const SUPPRESSION_LABELS = {
  BELOW_MINIMUM_N: 'unidad con menos de {n} respuestas válidas',
  SECONDARY_DEDUCTION_PROTECTION: 'protección secundaria — evita reconstruir por resta otra unidad suprimida',
};

export default function UnitResultsPanel({ studyId }) {
  const queryClient = useQueryClient();

  const { data: study } = useQuery({ queryKey: ['study', studyId], queryFn: () => getStudy(studyId) });
  const { data: unitTypes = [], isLoading: loadingTypes } = useQuery({
    queryKey: ['studyUnitTypes', studyId],
    queryFn: () => listStudyUnitTypes(studyId),
    enabled: Boolean(studyId),
  });

  const [unitTypeId, setUnitTypeId] = useState('');
  useEffect(() => {
    if (unitTypes.length && !unitTypes.some((type) => String(type.id) === unitTypeId)) {
      setUnitTypeId(String(unitTypes[0].id));
    }
  }, [unitTypeId, unitTypes]);

  const [typeForm, setTypeForm] = useState({ code: '', name: '' });
  const createTypeMutation = useMutation({
    mutationFn: (payload) => createStudyUnitType(studyId, payload),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['studyUnitTypes', studyId] });
      setUnitTypeId(String(created.id));
      setTypeForm({ code: '', name: '' });
    },
  });

  if (!study || loadingTypes) return <LoadingState label="Cargando unidades…" />;

  const isDraft = study.status === 'DRAFT';

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="rounded-2xl border border-border bg-surfaceSoft p-5 text-sm leading-5 text-muted">
        Aurora suprime el resultado visible de cualquier unidad (área, sede, turno, contrato…) con menos de{' '}
        <strong className="text-dark">{study.min_publishable_n}</strong> respuestas válidas — pero conserva
        esas respuestas para los agregados globales. Si una unidad organizacionalmente válida es demasiado
        pequeña por sí sola, agrúpala como hija de otra unidad al configurarla: Aurora publicará el
        resultado combinado del padre y dejará de mostrar las celdas individuales de sus hijas.
      </div>

      <Card>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <label className="flex min-w-56 flex-col gap-2">
            <span className="colmena-label">Segmentación</span>
            <select
              className="colmena-input h-10 px-4 text-sm"
              value={unitTypeId}
              onChange={(event) => setUnitTypeId(event.target.value)}
              disabled={!unitTypes.length}
            >
              {unitTypes.length ? null : <option value="">Sin tipos de unidad</option>}
              {unitTypes.map((type) => (
                <option key={type.id} value={type.id}>{type.name}</option>
              ))}
            </select>
          </label>

          {isDraft ? (
            <form
              className="flex flex-wrap items-end gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                createTypeMutation.mutate(typeForm);
              }}
            >
              <label className="flex flex-col gap-1">
                <span className="colmena-label">Código</span>
                <input
                  className="colmena-input h-9 w-28 px-3 text-sm"
                  value={typeForm.code}
                  onChange={(event) => setTypeForm((form) => ({ ...form, code: event.target.value }))}
                  placeholder="AREA"
                  required
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="colmena-label">Nombre del tipo</span>
                <input
                  className="colmena-input h-9 w-44 px-3 text-sm"
                  value={typeForm.name}
                  onChange={(event) => setTypeForm((form) => ({ ...form, name: event.target.value }))}
                  placeholder="Área"
                  required
                />
              </label>
              <Button type="submit" size="sm" variant="secondary" loading={createTypeMutation.isPending}>
                <PlusCircle size={14} className="mr-1" /> Nuevo tipo
              </Button>
            </form>
          ) : null}
        </div>
        {createTypeMutation.isError ? (
          <p className="mt-3 text-xs font-medium text-danger">
            {createTypeMutation.error?.message || 'No se pudo crear el tipo de unidad.'}
          </p>
        ) : null}
      </Card>

      {!unitTypeId ? (
        <EmptyState
          title={isDraft ? 'Configura un tipo de unidad' : 'Este estudio no tiene segmentaciones configuradas'}
          description={
            isDraft
              ? 'Los tipos de unidad (área, sede, turno, contrato…) se crean antes de abrir el estudio, con "Nuevo tipo" arriba.'
              : 'Los tipos de unidad sólo pueden configurarse mientras el estudio está en DRAFT.'
          }
        />
      ) : isDraft ? (
        <UnitsConfigPanel unitTypeId={Number(unitTypeId)} />
      ) : (
        <UnitResultsTable
          studyId={studyId}
          unitTypeId={Number(unitTypeId)}
          minPublishableN={study.min_publishable_n}
          instrumentVersionId={study.instrument_version_id}
          projectId={study.project_id}
        />
      )}
    </div>
  );
}

function UnitsConfigPanel({ unitTypeId }) {
  const queryClient = useQueryClient();
  const { data: units = [], isLoading } = useQuery({
    queryKey: ['studyUnits', unitTypeId],
    queryFn: () => listStudyUnits(unitTypeId),
    enabled: Boolean(unitTypeId),
  });

  const [form, setForm] = useState({ code: '', name: '', parent_id: '' });
  const createUnitMutation = useMutation({
    mutationFn: (payload) => createStudyUnit(unitTypeId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studyUnits', unitTypeId] });
      setForm({ code: '', name: '', parent_id: '' });
    },
  });

  const unitsById = new Map(units.map((unit) => [unit.id, unit]));

  if (isLoading) return <LoadingState label="Cargando unidades…" />;

  return (
    <Card>
      <div className="flex items-center gap-2">
        <Users size={16} className="text-turquoise" />
        <p className="text-sm font-semibold text-dark">Unidades de esta segmentación</p>
      </div>
      <p className="mt-1 text-xs text-muted">
        Para agrupar una unidad pequeña bajo otra mayor (p. ej. «Contabilidad» y «Tesorería» bajo
        «Administración financiera»), elige la unidad mayor como «Unidad padre».
      </p>

      <form
        className="mt-4 flex flex-wrap items-end gap-3 rounded-xl border border-dashed border-border p-4"
        onSubmit={(event) => {
          event.preventDefault();
          createUnitMutation.mutate({
            code: form.code || null,
            name: form.name,
            parent_id: form.parent_id ? Number(form.parent_id) : null,
          });
        }}
      >
        <label className="flex flex-col gap-1">
          <span className="colmena-label">Código</span>
          <input
            className="colmena-input h-9 w-28 px-3 text-sm"
            value={form.code}
            onChange={(event) => setForm((prev) => ({ ...prev, code: event.target.value }))}
            placeholder="Opcional"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="colmena-label">Nombre</span>
          <input
            className="colmena-input h-9 w-52 px-3 text-sm"
            value={form.name}
            onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
            placeholder="Contabilidad"
            required
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="colmena-label">Unidad padre</span>
          <select
            className="colmena-input h-9 w-52 px-3 text-sm"
            value={form.parent_id}
            onChange={(event) => setForm((prev) => ({ ...prev, parent_id: event.target.value }))}
          >
            <option value="">Ninguna (unidad de nivel superior)</option>
            {units.map((unit) => (
              <option key={unit.id} value={unit.id}>{unit.name}</option>
            ))}
          </select>
        </label>
        <Button type="submit" size="sm" loading={createUnitMutation.isPending} disabled={!form.name}>
          <PlusCircle size={14} className="mr-1" /> Agregar unidad
        </Button>
      </form>
      {createUnitMutation.isError ? (
        <p className="mt-3 text-xs font-medium text-danger">
          {createUnitMutation.error?.message || 'No se pudo crear la unidad.'}
        </p>
      ) : null}

      {units.length ? (
        <div className="mt-4 overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-surfaceSoft">
              <tr>
                {['Unidad', 'Código', 'Unidad padre'].map((label) => (
                  <th key={label} className="px-4 py-2.5 text-xs font-semibold text-muted">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {units.map((unit) => (
                <tr key={unit.id} className="border-t border-border">
                  <td className="px-4 py-2.5 font-medium text-dark">{unit.name}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-muted">{unit.code || '—'}</td>
                  <td className="px-4 py-2.5 text-xs text-muted">
                    {unit.parent_id ? unitsById.get(unit.parent_id)?.name || `#${unit.parent_id}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="mt-4">
          <EmptyState title="Sin unidades todavía" description="Agrega al menos una unidad con el formulario de arriba." />
        </div>
      )}
    </Card>
  );
}

function UnitResultsTable({ studyId, unitTypeId, minPublishableN, instrumentVersionId, projectId }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['censopasUnitResults', studyId, unitTypeId],
    queryFn: () => getCensopasUnitResults(studyId, unitTypeId),
    enabled: Boolean(studyId) && Boolean(unitTypeId),
    retry: false,
  });

  const { data: readiness, isFetching: isLoadingReadiness } = useQuery({
    queryKey: ['censopas-readiness', instrumentVersionId],
    queryFn: () => getCensopasReadiness(instrumentVersionId),
    enabled: Boolean(instrumentVersionId),
    retry: false,
  });

  const { data: globalResults } = useQuery({
    queryKey: ['censopasResults', studyId],
    queryFn: () => getCensopasResults(studyId),
    enabled: Boolean(studyId),
    retry: false,
  });

  const results = data?.results || [];
  const byConstruct = new Map();
  results.forEach((result) => {
    const list = byConstruct.get(result.construct_id) || { name: result.construct_name, rows: [] };
    list.rows.push(result);
    byConstruct.set(result.construct_id, list);
  });

  return (
    <Card>
      {instrumentVersionId ? (
        <div className="mb-4">
          <CensopasReadinessPanel readiness={readiness} isLoading={isLoadingReadiness} />
        </div>
      ) : null}

      {globalResults?.scoring_status ? (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surfaceSoft px-3 py-2 text-xs text-muted">
          <span>
            Estado del scoring oficial: <strong className="text-dark">{globalResults.scoring_status}</strong>
          </span>
          <span>·</span>
          <span>
            Equivalencia oficial: <strong className="text-dark">{globalResults.official_equivalence_enabled ? 'habilitada' : 'deshabilitada'}</strong>
          </span>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 rounded-xl bg-turquoiseSoft px-3 py-2 text-xs font-semibold text-turquoiseDark">
          <ShieldCheck size={15} />
          Umbral n ≥ {data?.min_publishable_n ?? minPublishableN}
        </div>
        {/* "Calcular resultados" es una única acción para todo el estudio —
            vive en la pestaña Baremos, no un botón propio aquí, para que
            nunca existan dos corridas independientes del mismo estudio. */}
        {projectId ? (
          <Link
            to={`/colmena/project/${projectId}/results`}
            className="colmena-badge inline-flex bg-amber/10 text-yellowDark"
          >
            Calcular / actualizar resultados en Baremos
          </Link>
        ) : null}
      </div>

      {isLoading ? (
        <div className="mt-4"><LoadingState label="Cargando resultados por unidad…" /></div>
      ) : isError ? (
        <div className="mt-4">
          <EmptyState
            title="Aún no hay una corrida CENSOPAS completa"
            description={error?.message || 'Calcula los resultados con el botón de arriba para ver el desglose por unidad.'}
          />
        </div>
      ) : !results.length ? (
        <div className="mt-4">
          <EmptyState title="Sin resultados por unidad" description="Ninguna sesión tiene esta segmentación asignada todavía." />
        </div>
      ) : (
        <div className="mt-4 flex flex-col gap-6">
          {[...byConstruct.entries()].map(([constructId, group]) => (
            <div key={constructId} className="overflow-x-auto rounded-xl border border-border">
              <p className="border-b border-border bg-surfaceSoft px-4 py-2.5 text-sm font-semibold text-dark">
                {group.name}
              </p>
              <table className="w-full text-left text-sm">
                <thead className="bg-surfaceSoft/60">
                  <tr>
                    {['Unidad', 'n', 'Puntaje', 'Estado'].map((label) => (
                      <th key={label} className="px-4 py-2.5 text-xs font-semibold text-muted">{label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {group.rows.map((row) => (
                    <tr key={row.unit_id} className="border-t border-border align-top">
                      <td className="px-4 py-3">
                        <p className="font-medium text-dark">{row.unit_name}</p>
                        {row.grouped_units?.length ? (
                          <p className="mt-0.5 text-xs text-muted">Incluye: {row.grouped_units.join(', ')}</p>
                        ) : null}
                      </td>
                      <td className="px-4 py-3">{row.n_valid}</td>
                      <td className="px-4 py-3">
                        {row.suppressed ? '—' : row.construct_score !== null ? formatNumber(row.construct_score) : '—'}
                      </td>
                      <td className="px-4 py-3">
                        {row.suppressed ? (
                          <span className="inline-flex items-start gap-1.5 text-xs font-medium text-warning">
                            <ShieldAlert size={13} className="mt-0.5 shrink-0" />
                            <span>
                              Resultado suprimido
                              <br />
                              <span className="text-muted">
                                Motivo: {(SUPPRESSION_LABELS[row.suppression_reason] || 'privacidad').replace(
                                  '{n}',
                                  data?.min_publishable_n ?? minPublishableN,
                                )}
                              </span>
                            </span>
                          </span>
                        ) : (
                          <span className="text-xs font-medium text-success">Publicable</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
      <p className="mt-4 text-xs leading-5 text-muted">
        Las respuestas de las unidades suprimidas o agrupadas siguen incluidas en los resultados globales del
        estudio; sólo se oculta su celda individual.
      </p>
    </Card>
  );
}
