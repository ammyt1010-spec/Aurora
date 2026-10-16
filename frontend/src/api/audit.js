import { apiRequest } from './client.js';

export function listOrganizationAuditEvents(organizationId, { limit = 30, beforeId = null } = {}) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (beforeId != null) query.set('before_id', String(beforeId));
  return apiRequest(`/organizations/${organizationId}/audit-events?${query}`);
}
