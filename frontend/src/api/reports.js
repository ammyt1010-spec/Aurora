import { API_BASE_URL, apiRequest } from './client.js';

export function createReportTemplate(payload) {
  return apiRequest('/report-templates', { method: 'POST', body: payload });
}

export function createReport(studyId, payload) {
  return apiRequest(`/studies/${studyId}/reports`, { method: 'POST', body: payload });
}

export function createReportPreview(studyId, payload) {
  return apiRequest(`/studies/${studyId}/reports/preview-async`, { method: 'POST', body: payload });
}

export function getReportPreviewStatus(reportId) {
  return apiRequest(`/reports/${reportId}/preview-status`);
}

export function getReport(reportId) {
  return apiRequest(`/reports/${reportId}`);
}

export function getReportDownloadUrl(reportId) {
  return `${API_BASE_URL}/reports/${reportId}/download`;
}

export function getReportPreviewPdfUrl(reportId) {
  return `${API_BASE_URL}/reports/${reportId}/preview.pdf`;
}

export function getReportPdfDownloadUrl(reportId) {
  return `${API_BASE_URL}/reports/${reportId}/download.pdf`;
}
