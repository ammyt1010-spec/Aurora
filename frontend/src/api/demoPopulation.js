import { apiRequest } from './client.js';

export function getDemoPopulationStatus(studyId) {
  return apiRequest(`/studies/${studyId}/demo-population`);
}

export function startDemoPopulation(studyId) {
  return apiRequest(`/studies/${studyId}/demo-population`, { method: 'POST' });
}
