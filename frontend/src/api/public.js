import { apiRequest } from './client.js';

export function getPublicStudy(publicId) {
  return apiRequest(`/public/studies/${publicId}`, { skipAuth: true });
}

export function createPublicResponseSession(publicId, invitationToken = null) {
  return apiRequest(`/public/studies/${publicId}/response-sessions`, {
    method: 'POST',
    body: invitationToken ? { invitation_token: invitationToken } : undefined,
    skipAuth: true,
  });
}
