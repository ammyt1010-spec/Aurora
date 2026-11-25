const ACTIVE_STUDY_PREFIX = 'colmena.activeStudy.';

export function getActiveStudyId(projectId) {
  if (!projectId) return null;
  const raw = localStorage.getItem(`${ACTIVE_STUDY_PREFIX}${projectId}`);
  const id = Number(raw);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

export function setActiveStudyId(projectId, studyId) {
  if (!projectId || !studyId) return;
  localStorage.setItem(`${ACTIVE_STUDY_PREFIX}${projectId}`, String(studyId));
}
