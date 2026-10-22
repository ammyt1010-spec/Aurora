import { apiRequest, API_BASE_URL } from './client.js';

export const createEvaluationBundle = (projectId, payload) =>
  apiRequest(`/projects/${projectId}/bundles`, { method: 'POST', body: payload });
export const listEvaluationBundles = (projectId) =>
  apiRequest(`/projects/${projectId}/bundles`);
export const revokeEvaluationBundle = (projectId, bundleId) =>
  apiRequest(`/projects/${projectId}/bundles/${bundleId}/revoke`, { method: 'POST' });
export const getPublicEvaluationBundle = (publicId) =>
  apiRequest(`/public/bundles/${encodeURIComponent(publicId)}`, { skipAuth: true });

export const createConsolidatedBundleReport = (projectId, bundleId) =>
  apiRequest(`/projects/${projectId}/bundles/${bundleId}/consolidated-reports`, { method: 'POST' });
export const listConsolidatedBundleReports = (projectId, bundleId) =>
  apiRequest(`/projects/${projectId}/bundles/${bundleId}/consolidated-reports`);
export const consolidatedPdfUrl = (reportId) =>
  `${API_BASE_URL}/consolidated-bundle-reports/${reportId}/download`;
