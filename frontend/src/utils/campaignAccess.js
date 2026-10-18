// El backend valida nuevamente el estado y la fecha de cierre.
// Esta comprobación evita que la interfaz ofrezca enlaces e invitaciones caducados.
export function canDistributeSurvey(study, now = Date.now()) {
  if (!study || study.status !== 'OPEN') return false;
  if (!study.end_at) return true;
  const expiresAt = Date.parse(study.end_at);
  return Number.isFinite(expiresAt) && expiresAt > now;
}

export function selectCampaign(studies, selectedId) {
  if (!Array.isArray(studies) || studies.length === 0) return null;
  return studies.find((study) => String(study.id) === String(selectedId))
    || studies.find((study) => study.status === 'OPEN')
    || studies[0];
}
