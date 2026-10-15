import { apiRequest } from './client.js';

export function createResponseSession(studyId) {
  return apiRequest(`/studies/${studyId}/response-sessions`, { method: 'POST' });
}

export function upsertResponse(sessionId, questionId, payload, accessToken = null) {
  return apiRequest(`/response-sessions/${sessionId}/responses/${questionId}`, {
    method: 'PUT',
    body: payload,
    headers: accessToken ? { 'X-Response-Token': accessToken } : {},
    skipAuth: Boolean(accessToken),
  });
}

export function completeResponseSession(sessionId, payload = {}, accessToken = null) {
  return apiRequest(`/response-sessions/${sessionId}/complete`, {
    method: 'POST',
    body: payload,
    headers: accessToken ? { 'X-Response-Token': accessToken } : {},
    skipAuth: Boolean(accessToken),
  });
}
