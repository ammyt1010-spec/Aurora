import { apiRequest } from './client.js';

export function listProjects({ page = 1, pageSize = 10 } = {}) {
  return apiRequest(`/projects?page=${page}&page_size=${pageSize}`);
}

export function createProject({ ownerUserId, name, projectType, description, metadata, organizationId, newOrganization, censopasStudy }) {
  return apiRequest('/projects', {
    method: 'POST',
    body: {
      owner_user_id: ownerUserId,
      name,
      project_type: projectType,
      description: description || null,
      metadata: metadata || {},
      organization_id: organizationId ?? null,
      new_organization: newOrganization ?? null,
      censopas_study: censopasStudy ?? null,
    },
  });
}

export function getProject(projectId) {
  return apiRequest(`/projects/${projectId}`);
}

export function updateProject(projectId, payload) {
  return apiRequest(`/projects/${projectId}`, { method: 'PATCH', body: payload });
}


export function listProjectMembers(projectId) {
  return apiRequest(`/projects/${projectId}/members`);
}

export function addProjectMemberByEmail(projectId, email, roleCode) {
  return apiRequest(`/projects/${projectId}/members/by-email`, {
    method: 'POST',
    body: { email, role_code: roleCode },
  });
}

export function removeProjectMember(projectId, userId) {
  return apiRequest(`/projects/${projectId}/members/${userId}`, { method: 'DELETE' });
}
