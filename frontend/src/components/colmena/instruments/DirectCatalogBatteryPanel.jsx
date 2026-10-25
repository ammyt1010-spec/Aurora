import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { QRCodeSVG } from 'qrcode.react';
import { fetchCurrentUser } from '../../../api/auth.js';
import {
  listInstruments,
  listInstrumentVersions,
} from '../../../api/instruments.js';
import { listStudies, createStudy, openStudy } from '../../../api/studies.js';
import {
  listSurveys,
  createSurveyFromInstrument,
} from '../../../api/surveys.js';
import { createEvaluationBundle } from '../../../api/evaluationBundles.js';

async function loadAllPages(fetchPage) {
  const items = [];
  let page = 1;
  let total = Infinity;
  while (items.length < total) {
    const result = await fetchPage(page);
    if (
      !result ||
      !Array.isArray(result.items) ||
      !Number.isInteger(result.total) ||
      result.total < 0
    ) {
      throw new Error(
        'Respuesta paginada inválida; no se puede verificar si ya existen campañas.',
      );
    }
    items.push(...result.items);
    if (items.length >= result.total) return items;
    if (!result.items.length)
      throw new Error(
        'La lista de campañas está incompleta. Intenta nuevamente.',
      );
    total = result.total;
    page += 1;
  }
  return items;
}

export async function prepareCatalogBattery(
  projectId,
  entries,
  onProgress = () => {},
  organizationId,
) {
  if (!entries.length || entries.length > 12)
    throw new Error('Selecciona entre 1 y 12 versiones.');
  // Revalidate at the moment of generation, even when reusing an OPEN campaign.
  const instruments = await loadAllPages((page) =>
    listInstruments({ page, pageSize: 100, organizationId }),
  );
  for (const entry of entries) {
    const instrument = instruments.find(
      (item) => item.id === entry.instrument.id,
    );
    if (
      !instrument ||
      !['AUTHORIZED', 'ACTIVE'].includes(instrument.status) ||
      (instrument.project_id &&
        String(instrument.project_id) !== String(projectId))
    ) {
      throw new Error(
        entry.instrument.name +
          ': la autorización del catálogo ya no está vigente.',
      );
    }
    const versions = await listInstrumentVersions(instrument.id);
    const statuses = instrument.is_system
      ? ['AUTHORIZED', 'ACTIVE', 'LOCKED']
      : ['AUTHORIZED', 'ACTIVE'];
    if (
      !Array.isArray(versions) ||
      !versions.some(
        (version) =>
          version.id === entry.version.id && statuses.includes(version.status),
      )
    ) {
      throw new Error(
        entry.instrument.name +
          ' · ' +
          entry.version.version_code +
          ': la versión ya no está autorizada.',
      );
    }
  }
  const user = await fetchCurrentUser();
  const studies = await loadAllPages((page) =>
    listStudies(projectId, { page, pageSize: 100 }),
  );
  const surveys = await loadAllPages((page) =>
    listSurveys(projectId, { page, pageSize: 100 }),
  );
  const ready = [];
  for (const entry of entries) {
    const label = entry.instrument.name + ' · ' + entry.version.version_code;
    try {
      onProgress(label + ': preparando campaña…');
      let study = studies.find(
        (item) =>
          item.instrument_version_id === entry.version.id &&
          ['DRAFT', 'OPEN'].includes(item.status),
      );
      if (!study) {
        let survey = surveys.find(
          (item) => item.instrument_version_id === entry.version.id,
        );
        if (!survey) {
          survey = await createSurveyFromInstrument(projectId, {
            created_by_user_id: user.id,
            instrument_version_id: entry.version.id,
            name: label,
            survey_type: 'INSTRUMENT',
          });
          surveys.push(survey);
        }
        study = await createStudy(projectId, {
          survey_id: survey.id,
          name: label,
          study_type:
            entry.instrument.code === 'CENSOPAS_COPSOQ' ? 'CENSO' : 'RESEARCH',
          min_publishable_n: 5,
        });
        studies.push(study);
      }
      if (study.requires_invitation)
        throw new Error(
          'La campaña requiere invitaciones individuales; no se puede emitir acceso público.',
        );
      if (study.status === 'DRAFT') study = await openStudy(study.id);
      const now = Date.now();
      if (
        study.status !== 'OPEN' ||
        !study.public_id ||
        (study.start_at && Date.parse(study.start_at) > now) ||
        (study.end_at && Date.parse(study.end_at) <= now)
      ) {
        throw new Error(
          'La campaña no está abierta o está fuera de su período de recepción.',
        );
      }
      ready.push(study);
      onProgress(label + ': abierta y disponible.');
    } catch (error) {
      throw new Error(
        label +
          ': ' +
          error.message +
          ' Las campañas ya preparadas se conservan; no se generó un enlace conjunto.',
      );
    }
  }
  if (ready.length === 1) return '/encuesta/' + ready[0].public_id;
  try {
    const bundle = await createEvaluationBundle(projectId, {
      label: 'Batería de instrumentos autorizados',
      study_ids: ready.map((study) => study.id),
    });
    if (!bundle.public_id)
      throw new Error('El servidor no devolvió un enlace válido.');
    return '/bateria/' + bundle.public_id;
  } catch (error) {
    throw new Error(
      'Las campañas se prepararon, pero no se pudo emitir la batería: ' +
        error.message,
    );
  }
}

export default function DirectCatalogBatteryPanel({ projects }) {
  const queryClient = useQueryClient();
  const [projectId, setProjectId] = useState('');
  const [selected, setSelected] = useState([]);
  const [url, setUrl] = useState('');
  const [progress, setProgress] = useState('');
  const [copyStatus, setCopyStatus] = useState('');
  const busy = useRef(false);
  const qrRef = useRef(null);
  const [search, setSearch] = useState('');
  const project = projects.find((item) => String(item.id) === projectId);
  useEffect(() => {
    if (!projects.length) {
      setProjectId('');
      return;
    }
    if (
      projects.length &&
      !projects.some((item) => String(item.id) === projectId)
    )
      setProjectId(String(projects[0].id));
  }, [projects, projectId]);
  useEffect(() => {
    setSelected([]);
    setUrl('');
    setProgress('');
    setCopyStatus('');
  }, [projectId]);
  const catalog = useQuery({
    queryKey: ['home-authorized-catalog', projectId, project?.organization_id],
    enabled: Boolean(projectId),
    retry: false,
    queryFn: async () => {
      const instruments = await loadAllPages((page) =>
        listInstruments({
          page,
          pageSize: 100,
          organizationId: project?.organization_id,
        }),
      );
      const authorized = instruments.filter(
        (instrument) =>
          ['AUTHORIZED', 'ACTIVE'].includes(instrument.status) &&
          (!instrument.project_id ||
            String(instrument.project_id) === projectId),
      );
      const rows = await Promise.all(
        authorized.map(async (instrument) => {
          const versions = await listInstrumentVersions(instrument.id);
          const statuses = instrument.is_system
            ? ['AUTHORIZED', 'ACTIVE', 'LOCKED']
            : ['AUTHORIZED', 'ACTIVE'];
          return versions
            .filter((version) => statuses.includes(version.status))
            .map((version) => ({ instrument, version }));
        }),
      );
      return rows.flat();
    },
  });
  const selectionValid = selected.every((entry) =>
    (catalog.data || []).some((row) => row.version.id === entry.version.id),
  );
  useEffect(() => {
    if (!catalog.isSuccess || selectionValid) return;
    setSelected((previous) =>
      previous.filter((entry) =>
        catalog.data.some((row) => row.version.id === entry.version.id),
      ),
    );
    setUrl('');
  }, [catalog.data, catalog.isSuccess, selectionValid]);
  const visibleEntries = (catalog.data || []).filter((entry) =>
    [
      entry.instrument.name,
      entry.instrument.discipline,
      entry.version.version_code,
    ]
      .join(' ')
      .toLocaleLowerCase()
      .includes(search.toLocaleLowerCase()),
  );
  const create = useMutation({
    mutationFn: async () => {
      if (busy.current) throw new Error('La preparación ya está en curso.');
      busy.current = true;
      setUrl('');
      try {
        return await prepareCatalogBattery(
          projectId,
          selected,
          setProgress,
          project?.organization_id,
        );
      } finally {
        busy.current = false;
      }
    },
    onSuccess: (path) => setUrl(window.location.origin + path),
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: ['aurora-battery-studies', projectId],
      });
      queryClient.invalidateQueries({ queryKey: ['studies', projectId] });
    },
  });
  return (
    <section
      className="rounded-xl border border-[#D9E6F1] bg-white p-4"
      aria-label="Catálogo para enlace y QR"
    >
      <h2 className="text-sm font-bold">
        Selecciona los instrumentos autorizados
      </h2>
      <p className="mt-1 text-xs text-muted">
        Marca de 1 a 12 versiones en el orden de aplicación. Al generar, se
        preparan y abren las campañas mediante las validaciones del servidor.
      </p>
      <label className="mt-3 block text-xs font-semibold">
        Empresa / evaluación
        <select
          aria-label="Empresa del catálogo"
          className="colmena-input mt-1 w-full"
          value={projectId}
          disabled={create.isPending}
          onChange={(event) => setProjectId(event.target.value)}
        >
          {!projects.length && (
            <option value="">
              Registra primero una evaluación empresarial
            </option>
          )}
          {projects.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      {catalog.isLoading && (
        <p role="status">Consultando versiones autorizadas…</p>
      )}
      {catalog.isError && (
        <p role="alert">
          No se pudo consultar el catálogo autorizado. No se generó ningún
          acceso.
        </p>
      )}
      {catalog.isSuccess && !catalog.data.length && (
        <p role="status">
          No hay versiones autorizadas disponibles para esta empresa.
        </p>
      )}
      <input
        className="colmena-input mt-3 w-full"
        aria-label="Buscar instrumento o versión"
        placeholder="Buscar instrumento, versión o disciplina"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />
      <fieldset className="mt-3 grid max-h-60 gap-2 overflow-y-auto sm:grid-cols-2 xl:grid-cols-3">
        <legend className="sr-only">
          Versiones de instrumentos autorizadas
        </legend>
        {visibleEntries.map((entry) => {
          const order = selected.findIndex(
            (item) => item.version.id === entry.version.id,
          );
          return (
            <label
              key={entry.version.id}
              className="flex items-center gap-2 rounded-lg border p-2 text-xs"
            >
              <input
                type="checkbox"
                checked={order >= 0}
                disabled={
                  create.isPending || (selected.length >= 12 && order < 0)
                }
                onChange={(event) => {
                  setUrl('');
                  setProgress('');
                  setCopyStatus('');
                  create.reset();
                  setSelected((previous) =>
                    event.target.checked
                      ? [...previous, entry]
                      : previous.filter(
                          (item) => item.version.id !== entry.version.id,
                        ),
                  );
                }}
              />
              <span>
                {entry.instrument.name} · {entry.version.version_code}
              </span>
              {order >= 0 && (
                <strong aria-label={'Orden ' + (order + 1)}>{order + 1}</strong>
              )}
            </label>
          );
        })}
      </fieldset>
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="text-xs">{selected.length} seleccionados</span>
        <button
          type="button"
          className="survey-btn survey-btn-primary"
          disabled={
            !selected.length ||
            !selectionValid ||
            !catalog.isSuccess ||
            catalog.isFetching ||
            create.isPending
          }
          onClick={() => create.mutate()}
        >
          {create.isPending ? 'Validando y preparando…' : 'Generar enlace y QR'}
        </button>
      </div>
      {progress && (
        <p role="status" className="mt-2 text-xs">
          {progress}
        </p>
      )}
      {create.isError && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {create.error.message}
        </p>
      )}
      {url && selectionValid && catalog.isSuccess && !catalog.isFetching && (
        <div className="mt-3 flex flex-wrap items-center gap-3 rounded-lg bg-slate-50 p-3">
          <div ref={qrRef}>
            <QRCodeSVG
              value={url}
              size={80}
              aria-label="QR del catálogo seleccionado"
            />
          </div>
          <div className="min-w-0">
            <a
              className="break-all text-sm underline"
              href={url}
              target="_blank"
              rel="noreferrer"
            >
              {url}
            </a>
            <button
              className="ml-3 text-sm underline"
              type="button"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(url);
                  setCopyStatus('Copiado');
                } catch {
                  setCopyStatus('No se pudo copiar; selecciona el enlace.');
                }
              }}
            >
              Copiar enlace
            </button>
            <button
              className="ml-3 text-sm underline"
              type="button"
              onClick={() => {
                const svg = qrRef.current?.querySelector('svg');
                if (!svg) return;
                const objectUrl = URL.createObjectURL(
                  new Blob([new XMLSerializer().serializeToString(svg)], {
                    type: 'image/svg+xml',
                  }),
                );
                const link = document.createElement('a');
                link.href = objectUrl;
                link.download = 'aurora-instrumentos-qr.svg';
                document.body.appendChild(link);
                link.click();
                link.remove();
                window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
              }}
            >
              Descargar QR
            </button>
            {copyStatus && <p role="status">{copyStatus}</p>}
          </div>
        </div>
      )}
    </section>
  );
}
