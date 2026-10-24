import { apiRequest } from './client.js';

export function createStudy(projectId, payload) {
  return apiRequest(`/projects/${projectId}/studies`, { method: 'POST', body: payload });
}

export function listStudies(projectId, { page = 1, pageSize = 50 } = {}) {
  return apiRequest(`/projects/${projectId}/studies?page=${page}&page_size=${pageSize}`);
}

export function getStudy(studyId) {
  return apiRequest(`/studies/${studyId}`);
}

export function updateStudy(studyId, payload) {
  return apiRequest(`/studies/${studyId}`, { method: 'PATCH', body: payload });
}

export function openStudy(studyId) {
  return apiRequest(`/studies/${studyId}/open`, { method: 'POST' });
}

export function closeStudy(studyId) {
  return apiRequest(`/studies/${studyId}/close`, { method: 'POST' });
}

export function archiveStudy(studyId) {
  return apiRequest(`/studies/${studyId}/archive`, { method: 'POST' });
}

export function getDataDictionary(studyId) {
  return apiRequest(`/studies/${studyId}/data-dictionary`);
}

export function getLongDataset(studyId) {
  return apiRequest(`/studies/${studyId}/dataset/long`);
}

export function getWideDataset(studyId) {
  return apiRequest(`/studies/${studyId}/dataset/wide`);
}

export function getResponseDescriptives(studyId) {
  return apiRequest(`/studies/${studyId}/response-descriptives`);
}

export function runScoring(studyId) {
  return apiRequest(`/studies/${studyId}/scoring`, { method: 'POST' });
}

export function getResultsOverview(studyId) {
  return apiRequest(`/studies/${studyId}/results/overview`);
}

export function listBarems(versionId) {
  return apiRequest(`/instrument-versions/${versionId}/barems`);
}

export function createBarem(versionId, payload) {
  return apiRequest(`/instrument-versions/${versionId}/barems`, { method: 'POST', body: payload });
}

export function generateBaremBands(baremId, payload) {
  return apiRequest(`/barems/${baremId}/generate-bands`, { method: 'POST', body: payload });
}

export function createEditableBaremCopy(baremId, payload = {}) {
  return apiRequest(`/barems/${baremId}/editable-copy`, { method: 'POST', body: payload });
}

export function replaceBaremBands(baremId, bands) {
  return apiRequest(`/barems/${baremId}/bands`, { method: 'PUT', body: { bands } });
}

export function activateBarem(baremId) {
  return apiRequest(`/barems/${baremId}/activate`, { method: 'POST' });
}

export function listStudyUnitTypes(studyId) {
  return apiRequest(`/studies/${studyId}/unit-types`);
}

export function createStudyUnitType(studyId, payload) {
  return apiRequest(`/studies/${studyId}/unit-types`, { method: 'POST', body: payload });
}

export function listStudyUnits(unitTypeId) {
  return apiRequest(`/study-unit-types/${unitTypeId}/units`);
}

export function createStudyUnit(unitTypeId, payload) {
  return apiRequest(`/study-unit-types/${unitTypeId}/units`, { method: 'POST', body: payload });
}

export function runCensopasScoring(studyId) {
  return apiRequest(`/studies/${studyId}/censopas/scoring`, { method: 'POST' });
}

export function getCensopasUnitResults(studyId, unitTypeId) {
  return apiRequest(`/studies/${studyId}/censopas/unit-results?unit_type_id=${unitTypeId}`);
}

export function getCensopasResults(studyId) {
  return apiRequest(`/studies/${studyId}/censopas/results`);
}
