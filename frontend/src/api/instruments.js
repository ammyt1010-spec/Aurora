import { apiRequest } from './client.js';

export function createInstrument(payload) {
  return apiRequest('/instruments', { method: 'POST', body: payload });
}

export function createProjectInstrument(projectId, payload) {
  return apiRequest(`/projects/${projectId}/instruments`, { method: 'POST', body: payload });
}

export function listDisciplines() {
  return apiRequest('/instruments/disciplines');
}

export function listInstruments({ page = 1, pageSize = 50, discipline = null, status = null, query = null, organizationId = null } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (discipline) params.append('discipline', discipline);
  if (status) params.append('status', status);
  if (query) params.append('query', query);
  if (organizationId) params.append('organization_id', String(organizationId));
  return apiRequest(`/instruments?${params.toString()}`);
}

export function listProjectInstruments(projectId, { page = 1, pageSize = 100, discipline = null, status = null, query = null } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (discipline) params.append('discipline', discipline);
  if (status) params.append('status', status);
  if (query) params.append('query', query);
  return apiRequest(`/projects/${projectId}/instruments?${params.toString()}`);
}

export function getInstrument(instrumentId, { organizationId = null } = {}) {
  const params = organizationId ? `?organization_id=${organizationId}` : '';
  return apiRequest(`/instruments/${instrumentId}${params}`);
}

export function updateInstrument(instrumentId, payload) {
  return apiRequest(`/instruments/${instrumentId}`, { method: 'PATCH', body: payload });
}

export function updateInstrumentStatus(instrumentId, { status, notes = null }) {
  return apiRequest(`/instruments/${instrumentId}/status`, { method: 'POST', body: { status, notes } });
}

export function validateInstrumentVersion(versionId) {
  return apiRequest(`/instrument-versions/${versionId}/validate`, { method: 'POST' });
}

export function linkStudyInstrument(studyId, versionId) {
  return apiRequest(`/studies/${studyId}/instruments/${versionId}`, { method: 'POST' });
}

export function createInstrumentVersion(instrumentId, payload) {
  return apiRequest(`/instruments/${instrumentId}/versions`, { method: 'POST', body: payload });
}

export function listInstrumentVersions(instrumentId) {
  return apiRequest(`/instruments/${instrumentId}/versions`);
}

export function getInstrumentVersion(instrumentId, versionId) {
  return apiRequest(`/instruments/${instrumentId}/versions/${versionId}`);
}

export function updateInstrumentVersion(versionId, payload) {
  return apiRequest(`/instrument-versions/${versionId}`, { method: 'PATCH', body: payload });
}

export function cloneInstrumentVersion(instrumentId, versionId, payload) {
  return apiRequest(`/instruments/${instrumentId}/versions/${versionId}/clone`, {
    method: 'POST',
    body: payload,
  });
}

export function getCensopasReadiness(versionId) {
  return apiRequest("/instrument-versions/" + versionId + "/censopas/readiness");
}

export function getCensopasPlans() {
  return apiRequest('/censopas/plans');
}

export function getInstrumentTree(versionId) {
  return apiRequest(`/instrument-versions/${versionId}/tree`);
}

export function getConstructMatrix(versionId) {
  return apiRequest(`/instrument-versions/${versionId}/construct-matrix`);
}

export function listItems(versionId) {
  return apiRequest(`/instrument-versions/${versionId}/items`);
}

export function createItem(versionId, payload) {
  return apiRequest(`/instrument-versions/${versionId}/items`, { method: 'POST', body: payload });
}

export function batchUpdateItems(versionId, items) {
  return apiRequest(`/instrument-versions/${versionId}/items/batch`, {
    method: 'PATCH',
    body: { items },
  });
}

export function getItem(itemId) {
  return apiRequest(`/items/${itemId}`);
}

export function updateItem(itemId, payload) {
  return apiRequest(`/items/${itemId}`, { method: 'PATCH', body: payload });
}

export function deleteItem(itemId) {
  return apiRequest(`/items/${itemId}`, { method: 'DELETE' });
}

export function listLikertScales(versionId) {
  return apiRequest(`/instrument-versions/${versionId}/likert-scales`);
}

export function createLikertScale(versionId, payload) {
  return apiRequest(`/instrument-versions/${versionId}/likert-scales`, { method: 'POST', body: payload });
}

export function updateLikertScale(optionSetId, payload) {
  return apiRequest(`/option-sets/${optionSetId}`, { method: 'PATCH', body: payload });
}
