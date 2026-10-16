import { apiRequest } from './client.js';

export function listUserSessions() {
  return apiRequest('/auth/sessions');
}

export function revokeUserSession(sessionId) {
  return apiRequest(`/auth/sessions/${sessionId}`, { method: 'DELETE' });
}

export function revokeOtherUserSessions() {
  return apiRequest('/auth/sessions', { method: 'DELETE' });
}
