import { apiRequest } from './client.js';

export function getAnalyticsMethods() {
  return apiRequest('/analytics/methods');
}

export function getAvailableMethods(studyId, variableIds) {
  return apiRequest(`/studies/${studyId}/analytics/available-methods`, {
    method: 'POST',
    body: { variable_ids: variableIds },
  });
}

const METHOD_PATHS = {
  describe: 'describe',
  frequencies: 'frequencies',
  crosstab: 'crosstab',
  compareGroups: 'compare-groups',
  correlation: 'correlation',
  reliability: 'reliability',
  logisticRegression: 'logistic-regression',
  kmeans: 'kmeans',
};

export function runAnalysis(method, studyId, payload) {
  const path = METHOD_PATHS[method];
  if (!path) {
    throw new Error(`Método de análisis desconocido: ${method}`);
  }
  return apiRequest(`/studies/${studyId}/analytics/${path}`, { method: 'POST', body: payload });
}

export function createAnalysisRun(studyId, payload) {
  return apiRequest(`/studies/${studyId}/analysis-runs`, { method: 'POST', body: payload });
}

export function getAnalysisRun(runId) {
  return apiRequest(`/analysis-runs/${runId}`);
}

export function runNormality(studyId, payload = {}) {
  return apiRequest(`/studies/${studyId}/analytics/normality`, { method: 'POST', body: payload });
}

export function runSpearmanMatrix(studyId, payload = {}) {
  return apiRequest(`/studies/${studyId}/analytics/spearman-matrix`, { method: 'POST', body: payload });
}

export function compareConstructGroups(studyId, payload) {
  return apiRequest(`/studies/${studyId}/analytics/construct-compare-groups`, { method: 'POST', body: payload });
}

export function getProjectLongitudinal(projectId) {
  return apiRequest(`/projects/${projectId}/analytics/longitudinal`);
}
