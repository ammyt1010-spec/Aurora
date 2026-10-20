import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';

import { listStudies } from '../../api/studies.js';
import { displayLabel } from '../../utils/labels.js';

/**
 * Simplificado a sólo-estudio: el proyecto ya viene de la URL
 * (/colmena/project/:projectId/...), no hace falta elegirlo de nuevo.
 */
export default function StudySelector({ projectId, studyId, onStudyChange }) {
  const { data: studiesData } = useQuery({
    queryKey: ['studies', projectId],
    queryFn: () => listStudies(projectId, { page: 1, pageSize: 100 }),
    enabled: Boolean(projectId),
  });
  const studies = studiesData?.items ?? [];

  useEffect(() => {
    if (!studyId && studies.length > 0) onStudyChange(studies[0].id);
  }, [studyId, studies, onStudyChange]);

  return (
    <label className="flex flex-col gap-2">
      <span className="colmena-label">Aplicación / estudio</span>
      <select
        className="colmena-input h-10 min-w-[220px] px-4 text-sm text-dark"
        value={studyId || ''}
        onChange={(event) => onStudyChange(event.target.value ? Number(event.target.value) : null)}
      >
        <option value="">Selecciona un estudio</option>
        {studies.map((study) => (
          <option key={study.id} value={study.id}>
            {study.name} ({displayLabel(study.status)})
          </option>
        ))}
      </select>
    </label>
  );
}
