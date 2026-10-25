import { API_BASE_URL, apiRequest } from './client.js';

export function createReportTemplate(payload) {
  return apiRequest('/report-templates', { method: 'POST', body: payload });
}

export function updateReportTemplate(templateId, payload) {
  return apiRequest(`/report-templates/${templateId}`, {
    method: 'PUT',
    body: payload,
  });
}

export function createReport(studyId, payload) {
  return apiRequest(`/studies/${studyId}/reports`, {
    method: 'POST',
    body: payload,
  });
}

export function createReportPreview(studyId, payload) {
  return apiRequest(`/studies/${studyId}/reports/preview`, {
    method: 'POST',
    body: payload,
  });
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

export function listStudyReports(studyId) {
  return apiRequest(`/studies/${studyId}/reports`);
}

export function listReportTemplates(discipline = null) {
  const filter = discipline
    ? `?discipline=${encodeURIComponent(discipline)}`
    : '';
  return apiRequest(`/report-templates${filter}`);
}

export function getExecutiveDashboard(studyId, analysisRunId = null) {
  return apiRequest(
    `/studies/${studyId}/reports/executive-dashboard${analysisRunId ? `?analysis_run_id=${encodeURIComponent(analysisRunId)}` : ''}`,
  );
}

export function getOrganizationReportHistory(
  organizationId,
  { studyId, discipline } = {},
) {
  const query = new URLSearchParams();
  if (studyId) query.set('study_id', String(studyId));
  if (discipline) query.set('discipline', discipline);
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return apiRequest(
    `/organizations/${organizationId}/reports/history${suffix}`,
  );
}
