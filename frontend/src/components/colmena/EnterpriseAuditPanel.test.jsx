import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, screen } from '@testing-library/react';

import { renderWithQueryClient } from '../../test-utils/renderWithQueryClient.jsx';
import { listOrganizations } from '../../api/organizations.js';
import { listOrganizationAuditEvents } from '../../api/audit.js';
import { EnterpriseAuditPanel } from './EnterpriseAuditPanel.jsx';

vi.mock('../../api/organizations.js', () => ({ listOrganizations: vi.fn() }));
vi.mock('../../api/audit.js', () => ({ listOrganizationAuditEvents: vi.fn() }));

const company = { organization: { id: 8, name: 'Empresa de prueba' }, role_code: 'OWNER' };

beforeEach(() => {
  vi.clearAllMocks();
  listOrganizations.mockResolvedValue([company]);
  listOrganizationAuditEvents.mockResolvedValue({
    items: [{
      id: 99,
      action: 'PROJECT_MEMBER_ADDED',
      actor_user_id: 1,
      project_id: 12,
      created_at: '2026-10-01T10:00:00Z',
    }],
    next_before_id: null,
  });
});

afterEach(cleanup);

describe('EnterpriseAuditPanel', () => {
  it('shows company-only activity without sensitive before/after payloads', async () => {
    renderWithQueryClient(<EnterpriseAuditPanel />);
    expect(await screen.findByText('Integrante incorporado')).toBeInTheDocument();
    expect(screen.getByText('Historial de actividad empresarial')).toBeInTheDocument();
    expect(screen.getByText('#12')).toBeInTheDocument();
    expect(listOrganizationAuditEvents).toHaveBeenCalledWith(8, { limit: 30, beforeId: null });
    expect(screen.queryByText('Contraseña')).not.toBeInTheDocument();
  });

  it('does not fetch audit events for non-admin memberships', async () => {
    listOrganizations.mockResolvedValue([{ ...company, role_code: 'COLLABORATOR' }]);
    renderWithQueryClient(<EnterpriseAuditPanel />);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByText('Historial de actividad empresarial')).not.toBeInTheDocument();
    expect(listOrganizationAuditEvents).not.toHaveBeenCalled();
  });

  it('supports cursor pagination without duplicating the first page', async () => {
    listOrganizationAuditEvents
      .mockResolvedValueOnce({
        items: [{ id: 20, action: 'PROJECT_CREATED', actor_user_id: 1, project_id: 12, created_at: null }],
        next_before_id: 20,
      })
      .mockResolvedValueOnce({
        items: [{ id: 19, action: 'PROJECT_UPDATED', actor_user_id: 1, project_id: 12, created_at: null }],
        next_before_id: null,
      });
    renderWithQueryClient(<EnterpriseAuditPanel />);
    expect(await screen.findByText('Proyecto creado')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Mostrar eventos anteriores' }));
    expect(await screen.findByText('Proyecto modificado')).toBeInTheDocument();
    expect(listOrganizationAuditEvents).toHaveBeenNthCalledWith(2, 8, { limit: 30, beforeId: 20 });
  });
});
