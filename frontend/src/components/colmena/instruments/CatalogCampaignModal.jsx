import { useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { listInstrumentVersions } from '../../../api/instruments.js';
import { listStudies, createStudy } from '../../../api/studies.js';
import {
  listSurveys,
  createSurveyFromInstrument,
} from '../../../api/surveys.js';
import { useAuth } from '../../../auth/AuthContext.jsx';
import { Modal } from '../../ui/Modal.jsx';

/** Keep the actual catalog/version selection through campaign configuration. */
export default function CatalogCampaignModal({
  instrument,
  projects,
  onClose,
  onCreated,
}) {
  const { user } = useAuth();
  const [projectId, setProjectId] = useState('');
  const [versionId, setVersionId] = useState('');
  const busy = useRef(false);
  const versions = useQuery({
    queryKey: ['catalog-campaign-versions', instrument.id],
    queryFn: () => listInstrumentVersions(instrument.id),
    retry: false,
  });
  const available = (versions.data || []).filter((version) =>
    (instrument.is_system
      ? ['AUTHORIZED', 'ACTIVE', 'LOCKED']
      : ['AUTHORIZED', 'ACTIVE']
    ).includes(version.status),
  );
  const selectedVersion = available.find(
    (version) => String(version.id) === versionId,
  );
  const configure = useMutation({
    mutationFn: async () => {
      if (busy.current || !selectedVersion || !projectId || !user?.id)
        throw new Error('Selecciona empresa y versión publicada.');
      busy.current = true;
      try {
        const studies = await listStudies(projectId, {
          page: 1,
          pageSize: 100,
        });
        const existing = studies.items.find(
          (study) =>
            study.instrument_version_id === selectedVersion.id &&
            ['DRAFT', 'OPEN'].includes(study.status),
        );
        if (existing) return existing;
        const surveys = await listSurveys(projectId, {
          page: 1,
          pageSize: 100,
        });
        // Reuse a survey after a failed campaign request rather than duplicating it.
        const survey =
          surveys.items.find(
            (item) => item.instrument_version_id === selectedVersion.id,
          ) ||
          (await createSurveyFromInstrument(projectId, {
            created_by_user_id: user.id,
            instrument_version_id: selectedVersion.id,
            name: instrument.name,
            survey_type: 'INSTRUMENT',
          }));
        return await createStudy(projectId, {
          survey_id: survey.id,
          name: instrument.name + ' · ' + selectedVersion.version_code,
          study_type:
            instrument.code === 'CENSOPAS_COPSOQ' ? 'CENSO' : 'RESEARCH',
          min_publishable_n: 5,
        });
      } finally {
        busy.current = false;
      }
    },
    onSuccess: (study) => onCreated({ projectId, studyId: study.id }),
  });
  return (
    <Modal
      isOpen
      title={'Configurar ' + instrument.name}
      onClose={onClose}
      preventClose={configure.isPending}
    >
      <div className="space-y-4">
        <p className="text-sm">
          Selecciona la empresa y la versión publicada. Se conservará una
          campaña existente o se preparará una nueva en borrador, sin abrir la
          recolección automáticamente.
        </p>
        <label className="block">
          Empresa
          <select
            className="colmena-input w-full"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            disabled={configure.isPending}
          >
            <option value="">Selecciona una empresa</option>
            {projects
              .filter(
                (project) =>
                  !instrument.project_id ||
                  project.id === instrument.project_id,
              )
              .map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
          </select>
        </label>
        <label className="block">
          Versión publicada
          <select
            className="colmena-input w-full"
            value={versionId}
            onChange={(event) => setVersionId(event.target.value)}
            disabled={configure.isPending}
          >
            <option value="">Selecciona una versión</option>
            {available.map((version) => (
              <option key={version.id} value={version.id}>
                {version.version_code}
              </option>
            ))}
          </select>
        </label>
        {!projects.length && (
          <p role="status">
            Primero registra una evaluación empresarial; después vuelve a
            seleccionar este instrumento.
          </p>
        )}
        {versions.isLoading && <p role="status">Consultando versiones…</p>}
        {versions.isError && (
          <p role="alert">
            No se pudieron consultar las versiones autorizadas.
          </p>
        )}
        {versions.isSuccess && !available.length && (
          <p role="status">
            Este instrumento no tiene versiones publicadas disponibles.
          </p>
        )}
        {configure.isError && <p role="alert">{configure.error.message}</p>}
        <button
          className="survey-btn survey-btn-primary"
          type="button"
          disabled={!projectId || !selectedVersion || configure.isPending}
          onClick={() => configure.mutate()}
        >
          {configure.isPending ? 'Preparando…' : 'Continuar con esta campaña'}
        </button>
      </div>
    </Modal>
  );
}
