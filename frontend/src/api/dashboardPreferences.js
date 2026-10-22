import { apiRequest } from './client.js';

export const DEFAULT_LAYOUT = Object.freeze({
  widgets: ['summary', 'distribution', 'ranking', 'segments', 'actions', 'trend', 'action_plan'],
  density: 'compact',
  chart_mode: 'stacked',
});
export function getDashboardPreferences(organizationId) {
  return apiRequest(`/dashboard-preferences/${organizationId}`);
}
export function saveDashboardPreferences(organizationId, layout) {
  return apiRequest(`/dashboard-preferences/${organizationId}`, {
    method: 'PUT',
    body: { widgets: layout.widgets, density: layout.density, chart_mode: layout.chart_mode },
  });
}
