import { useQuery } from '@tanstack/react-query';

import { listStudies } from '../../api/studies.js';
import { displayLabel } from '../../utils/labels.js';

/**
 * Simplificado a sólo-estudio: el proyecto ya viene de la URL
 * (/colmena/project/:projectId/...), no hace falta elegirlo de nuevo.
 */
export function reportInstrumentLabel(study) {
  const name = study.instrument_name || 'Instrumento no vinculado';
  const code = study.instrument_version_code || '';
  const version = /SHORT|CORTA/i.test(code) ? 'versión corta'
    : /MEDIUM|MEDIA/i.test(code) ? 'versión media'
      : code || 'versión no especificada';
  return `${name} · ${version}`;
}

export default function StudySelector({ projectId, studyId, onStudyChange, showInstrument = false }) {
  const { data: studiesData } = useQuery({
    queryKey: ['studies', projectId],
    queryFn: () => listStudies(projectId, { page: 1, pageSize: 100 }),
    enabled: Boolean(projectId),
  });
  const studies = studiesData?.items ?? [];

  return (
    <label className="flex flex-col gap-2">
      <span className="colmena-label">{showInstrument ? 'Instrumento / aplicación' : 'Aplicación / estudio'}</span>
      <select
        className="colmena-input h-10 w-full min-w-0 max-w-full px-4 text-sm text-dark"
        value={studyId || ''}
        onChange={(event) => onStudyChange(event.target.value ? Number(event.target.value) : null)}
      >
        <option value="">Selecciona un estudio</option>
        {studies.map((study) => (
          <option key={study.id} value={study.id}>
            {showInstrument ? `${reportInstrumentLabel(study)} — ` : ''}{study.name} ({displayLabel(study.status)})
          </option>
        ))}
      </select>
    </label>
  );
}
