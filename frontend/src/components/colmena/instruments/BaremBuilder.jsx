import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, CopyPlus, Layers3, LockKeyhole, Plus, Save, Sparkles } from 'lucide-react';

import { getInstrumentTree } from '../../../api/instruments.js';
import {
  activateBarem,
  createBarem,
  createEditableBaremCopy,
  generateBaremBands,
  listBarems,
  listStudies,
  replaceBaremBands,
} from '../../../api/studies.js';
import { Button } from '../../ui/Button.jsx';
import { Card } from '../../ui/Card.jsx';
import { EmptyState } from '../../ui/EmptyState.jsx';
import { StatusPill } from '../../ui/StatusPill.jsx';

function bandPayload(bands) {
  return bands.map((band) => {
    const payload = { ...band };
    delete payload.id;
    delete payload.barem_id;
    return payload;
  });
}

function groupedBands(bands) {
  return bands.reduce((groups, band) => {
    if (!groups.has(band.construct_id)) groups.set(band.construct_id, []);
    groups.get(band.construct_id).push(band);
    return groups;
  }, new Map());
}

export default function BaremBuilder({ versionId, projectId }) {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState('');
  const [levels, setLevels] = useState(3);
  const [direction, setDirection] = useState('');
  const [generationMethod, setGenerationMethod] = useState('EQUAL_INTERVAL');
  const [pilotStudyId, setPilotStudyId] = useState('');
  const [draftBands, setDraftBands] = useState([]);
  const [activation, setActivation] = useState(null);
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState({ name: '', population: '', source: '', version: 'v1' });

  const { data: barems = [] } = useQuery({
    queryKey: ['barems', versionId],
    queryFn: () => listBarems(versionId),
    enabled: Boolean(versionId),
  });
  const { data: tree } = useQuery({
    queryKey: ['instrumentTree', versionId],
    queryFn: () => getInstrumentTree(versionId),
    enabled: Boolean(versionId),
  });
  const { data: studiesData } = useQuery({
    queryKey: ['studies', projectId],
    queryFn: () => listStudies(projectId, { page: 1, pageSize: 100 }),
    enabled: Boolean(projectId),
  });

  const studies = studiesData?.items || [];
  const variableConstructs = useMemo(() => tree?.variables || [], [tree]);
  const variableIds = useMemo(
    () => new Set(variableConstructs.map((construct) => construct.id)),
    [variableConstructs],
  );
  const variableById = useMemo(
    () => new Map(variableConstructs.map((construct) => [construct.id, construct])),
    [variableConstructs],
  );
  const selected = barems.find((barem) => String(barem.id) === String(selectedId));
  const bandsByVariable = useMemo(() => groupedBands(draftBands), [draftBands]);
  const legacyBandCount = selected ? Math.max(0, selected.bands.length - draftBands.length) : 0;

  useEffect(() => {
    if (!selectedId && barems.length) setSelectedId(String(barems[0].id));
  }, [barems, selectedId]);

  useEffect(() => {
    const bands = selected?.bands || [];
    const rootBands = tree ? bands.filter((band) => variableIds.has(band.construct_id)) : bands;
    setDraftBands(rootBands.map((band) => ({ ...band })));
    setSaved(false);
  }, [selected, tree, variableIds]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['barems', versionId] });

  const createMutation = useMutation({
    mutationFn: () =>
      createBarem(versionId, {
        name: form.name,
        population_label: form.population,
        source_reference: form.source,
        barem_version: form.version,
      }),
    onSuccess: (barem) => {
      setSelectedId(String(barem.id));
      setForm({ name: '', population: '', source: '', version: 'v1' });
      invalidate();
    },
  });
  const generateMutation = useMutation({
    mutationFn: () =>
      generateBaremBands(selected.id, {
        construct_ids: variableConstructs.map((construct) => construct.id),
        levels,
        direction,
        method: generationMethod,
        study_id: generationMethod === 'QUANTILES' ? Number(pilotStudyId) : null,
      }),
    onSuccess: () => {
      setSaved(false);
      invalidate();
    },
  });
  const saveMutation = useMutation({
    mutationFn: () => replaceBaremBands(selected.id, bandPayload(draftBands)),
    onSuccess: () => {
      setSaved(true);
      invalidate();
    },
  });
  const activateMutation = useMutation({
    mutationFn: () => activateBarem(selected.id),
    onSuccess: (result) => {
      setActivation(result);
      invalidate();
    },
  });
  const editableCopyMutation = useMutation({
    mutationFn: () => createEditableBaremCopy(selected.id),
    onSuccess: (copy) => {
      setSelectedId(String(copy.id));
      setActivation(null);
      invalidate();
    },
  });

  const updateBand = (id, field, value) => {
    setSaved(false);
    setDraftBands((bands) =>
      bands.map((band) =>
        band.id === id
          ? { ...band, [field]: ['min_value', 'max_value'].includes(field) ? Number(value) : value }
          : band,
      ),
    );
  };

  if (!versionId) {
    return (
      <EmptyState
        title="Primero inicializa la estructura."
        description="Los baremos se aplican al variables raíz del proyecto."
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <div className="mb-4">
          <p className="text-sm font-semibold text-dark">Nuevo baremo</p>
          <p className="mt-1 text-xs text-muted">Registra una versión metodológica antes de proponer sus niveles.</p>
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(180px,1fr)_minmax(180px,1fr)_minmax(220px,2fr)_120px_auto] lg:items-end">
          <label className="flex flex-col gap-2">
            <span className="colmena-label">Nombre</span>
            <input
              className="colmena-input h-10 px-3 text-sm"
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder="Baremo general"
            />
          </label>
          <label className="flex flex-col gap-2">
            <span className="colmena-label">Población</span>
            <input
              className="colmena-input h-10 px-3 text-sm"
              value={form.population}
              onChange={(event) => setForm({ ...form, population: event.target.value })}
              placeholder="Estudiantes universitarios"
            />
          </label>
          <label className="flex flex-col gap-2">
            <span className="colmena-label">Fuente metodológica</span>
            <input
              className="colmena-input h-10 px-3 text-sm"
              value={form.source}
              onChange={(event) => setForm({ ...form, source: event.target.value })}
              placeholder="Manual técnico CENSOPAS o norma sectorial"
            />
          </label>
          <label className="flex flex-col gap-2">
            <span className="colmena-label">Versión</span>
            <input
              className="colmena-input h-10 px-3 text-sm"
              value={form.version}
              onChange={(event) => setForm({ ...form, version: event.target.value })}
            />
          </label>
          <Button
            variant="primary"
            size="sm"
            onClick={() => createMutation.mutate()}
            loading={createMutation.isPending}
            disabled={!form.name || !form.population || !form.source}
          >
            <Plus size={14} /> Crear
          </Button>
        </div>
        {createMutation.isError ? (
          <p className="mt-3 text-sm text-danger">{createMutation.error?.message || 'No se pudo crear el baremo.'}</p>
        ) : null}
      </Card>

      {barems.length ? (
        <Card padded={false}>
          <div className="flex flex-wrap items-end gap-3 border-b border-border px-4 py-4">
            <label className="flex min-w-64 flex-1 flex-col gap-2">
              <span className="colmena-label">Baremo</span>
              <select
                className="colmena-input h-10 px-3 text-sm"
                value={selectedId}
                onChange={(event) => {
                  setSelectedId(event.target.value);
                  setActivation(null);
                }}
              >
                <option value="">Selecciona…</option>
                {barems.map((barem) => (
                  <option key={barem.id} value={barem.id}>
                    {barem.name} · {barem.status === 'ACTIVE' ? 'Activo' : 'Borrador'}
                  </option>
                ))}
              </select>
            </label>

            {selected ? (
              <div className="flex items-center gap-2 pb-1">
                <StatusPill label={selected.status === 'ACTIVE' ? 'Activo' : 'Editable'} tone={selected.status === 'ACTIVE' ? 'active' : 'draft'} />
                <span className="text-xs text-muted">{variableConstructs.length} variables raíz</span>
              </div>
            ) : null}
          </div>

          {selected ? (
            <>
              <div className="border-b border-border bg-surfaceSoft px-4 py-3 text-xs text-muted">
                {selected.population_label} · fuente: {selected.source_reference} · Cada variable mantiene sus propios
                cortes de 0 a 100.
              </div>

              {selected.status === 'ACTIVE' ? (
                <div className="flex flex-col gap-3 border-b border-border bg-turquoiseSoft/60 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex gap-3">
                    <LockKeyhole size={18} className="mt-0.5 shrink-0 text-turquoiseDark" />
                    <div>
                      <p className="text-sm font-semibold text-dark">Este baremo está activo y conserva su historial.</p>
                      <p className="mt-1 text-xs text-muted">Crea una versión editable para cambiar niveles y guardarlos sin modificar el original.</p>
                    </div>
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => editableCopyMutation.mutate()}
                    loading={editableCopyMutation.isPending}
                  >
                    <CopyPlus size={14} /> Crear versión editable
                  </Button>
                </div>
              ) : (
                <div className="flex flex-wrap items-end gap-3 border-b border-border px-4 py-4">
                  <label className="flex flex-col gap-2">
                    <span className="colmena-label">Niveles</span>
                    <select className="colmena-input h-10 px-3 text-sm" value={levels} onChange={(event) => setLevels(Number(event.target.value))}>
                      <option value={3}>3 niveles</option>
                      <option value={5}>5 niveles</option>
                    </select>
                  </label>
                  <label className="flex flex-col gap-2">
                    <span className="colmena-label">Sentido</span>
                    <select className="colmena-input h-10 px-3 text-sm" value={direction} onChange={(event) => setDirection(event.target.value)}>
                      <option value="">Selecciona…</option>
                      <option value="HIGHER_BETTER">Mayor = favorable</option>
                      <option value="LOWER_BETTER">Menor = favorable (p. ej. riesgo)</option>
                    </select>
                  </label>
                  <label className="flex flex-col gap-2">
                    <span className="colmena-label">Propuesta</span>
                    <select className="colmena-input h-10 px-3 text-sm" value={generationMethod} onChange={(event) => setGenerationMethod(event.target.value)}>
                      <option value="EQUAL_INTERVAL">Intervalos iguales</option>
                      <option value="QUANTILES">Cuantiles del piloto</option>
                    </select>
                  </label>
                  {generationMethod === 'QUANTILES' ? (
                    <label className="flex flex-col gap-2">
                      <span className="colmena-label">Estudio piloto</span>
                      <select className="colmena-input h-10 px-3 text-sm" value={pilotStudyId} onChange={(event) => setPilotStudyId(event.target.value)}>
                        <option value="">Selecciona…</option>
                        {studies.map((study) => <option key={study.id} value={study.id}>{study.name}</option>)}
                      </select>
                    </label>
                  ) : null}
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => generateMutation.mutate()}
                    loading={generateMutation.isPending}
                    disabled={!variableConstructs.length || !direction || (generationMethod === 'QUANTILES' && !pilotStudyId)}
                  >
                    <Sparkles size={14} /> Proponer cortes
                  </Button>
                  <Button variant="primary" size="sm" onClick={() => activateMutation.mutate()} loading={activateMutation.isPending} disabled={!draftBands.length}>
                    <CheckCircle2 size={14} /> Activar
                  </Button>
                </div>
              )}

              {legacyBandCount > 0 ? (
                <div className="mx-4 mt-4 rounded-xl border border-amber/20 bg-yellowSoft px-3 py-2.5 text-xs text-yellowDark">
                  Se ocultaron {legacyBandCount} filas antiguas de dimensiones. El baremo ahora se administra únicamente para el variables raíz.
                </div>
              ) : null}

              {draftBands.length ? (
                <div className="space-y-4 p-4">
                  {Array.from(bandsByVariable.entries()).map(([constructId, bands]) => {
                    const variable = variableById.get(constructId);
                    return (
                      <section key={constructId} className="overflow-hidden rounded-2xl border border-border bg-white">
                        <div className="flex items-center justify-between gap-3 border-b border-border bg-surfaceSoft px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber/10 text-amber">
                              <Layers3 size={16} />
                            </span>
                            <div>
                              <p className="text-sm font-semibold text-dark">{variable?.name || `Variable ${constructId}`}</p>
                              <p className="text-xs text-muted">{bands.length} niveles</p>
                            </div>
                          </div>
                          {variable?.code ? <span className="font-mono text-[11px] text-muted">{variable.code}</span> : null}
                        </div>
                        <div className="divide-y divide-border">
                          {bands
                            .slice()
                            .sort((left, right) => left.severity_order - right.severity_order)
                            .map((band) => (
                              <div key={band.id || `${band.construct_id}-${band.severity_order}`} className="grid gap-3 px-4 py-3 lg:grid-cols-[minmax(130px,0.7fr)_100px_100px_minmax(240px,1.7fr)] lg:items-end">
                                <label className="flex flex-col gap-1.5">
                                  <span className="colmena-label">Nivel {band.severity_order}</span>
                                  <input className="colmena-input h-9 px-2 text-sm" value={band.label} disabled={selected.status === 'ACTIVE'} onChange={(event) => updateBand(band.id, 'label', event.target.value)} />
                                </label>
                                <label className="flex flex-col gap-1.5">
                                  <span className="colmena-label">Desde</span>
                                  <input type="number" className="colmena-input h-9 px-2 text-sm" value={band.min_value} disabled={selected.status === 'ACTIVE'} onChange={(event) => updateBand(band.id, 'min_value', event.target.value)} />
                                </label>
                                <label className="flex flex-col gap-1.5">
                                  <span className="colmena-label">Hasta</span>
                                  <input type="number" className="colmena-input h-9 px-2 text-sm" value={band.max_value} disabled={selected.status === 'ACTIVE'} onChange={(event) => updateBand(band.id, 'max_value', event.target.value)} />
                                </label>
                                <label className="flex flex-col gap-1.5">
                                  <span className="colmena-label">Interpretación</span>
                                  <input className="colmena-input h-9 px-2 text-sm" value={band.interpretation || ''} disabled={selected.status === 'ACTIVE'} onChange={(event) => updateBand(band.id, 'interpretation', event.target.value)} placeholder="Qué significa este nivel" />
                                </label>
                              </div>
                            ))}
                        </div>
                      </section>
                    );
                  })}
                </div>
              ) : (
                <div className="p-4">
                  <EmptyState title="Aún no hay niveles" description="Genera 3 o 5 niveles para el variables raíz del proyecto y luego ajusta sus cortes." />
                </div>
              )}

              {draftBands.length && selected.status !== 'ACTIVE' ? (
                <div className="sticky bottom-0 flex flex-wrap items-center justify-end gap-3 border-t border-border bg-white/95 p-4 backdrop-blur">
                  {saved ? <span className="text-sm font-medium text-success">Cambios guardados.</span> : null}
                  {saveMutation.isError ? <span className="text-sm text-danger">{saveMutation.error?.message}</span> : null}
                  <Button variant="primary" size="md" onClick={() => saveMutation.mutate()} loading={saveMutation.isPending}>
                    <Save size={15} /> Guardar cambios
                  </Button>
                </div>
              ) : null}

              {generateMutation.isError ? (
                <p className="mx-5 mb-5 rounded-xl bg-danger/10 p-4 text-sm text-danger">{generateMutation.error?.message || 'No se pudieron proponer los cortes.'}</p>
              ) : null}
              {editableCopyMutation.isError ? (
                <p className="mx-5 mb-5 rounded-xl bg-danger/10 p-4 text-sm text-danger">{editableCopyMutation.error?.message || 'No se pudo crear la versión editable.'}</p>
              ) : null}
              {activateMutation.isError ? (
                <p className="mx-5 mb-5 rounded-xl bg-danger/10 p-4 text-sm text-danger">{activateMutation.error?.message || 'No se pudo activar el baremo.'}</p>
              ) : null}
              {activation ? (
                <div className="m-5 rounded-xl bg-turquoise/10 p-4 text-sm text-turquoise">Baremo activo e inmutable.</div>
              ) : null}
            </>
          ) : (
            <div className="p-4">
              <EmptyState title="Selecciona un baremo" description="Podrás proponer niveles, revisar cortes y activarlo." />
            </div>
          )}
        </Card>
      ) : (
        <Card>
          <EmptyState title="Crea el primer baremo" description="Registra población, fuente y versión para mantener trazabilidad." />
        </Card>
      )}
    </div>
  );
}
