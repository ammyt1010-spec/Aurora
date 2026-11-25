import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';

import { renderWithQueryClient } from '../../test-utils/renderWithQueryClient.jsx';
import { listUserSessions, revokeUserSession, revokeOtherUserSessions } from '../../api/sessions.js';
import { SessionManagementPanel } from './SessionManagementPanel.jsx';

vi.mock('../../api/sessions.js', () => ({
  listUserSessions: vi.fn(),
  revokeUserSession: vi.fn(),
  revokeOtherUserSessions: vi.fn(),
}));

const mockSessions = [
  {
    session_id: 'sid_current_1',
    device_family: 'Desktop',
    os_family: 'Windows',
    browser_family: 'Chrome',
    ip_address: '192.168.1.***',
    created_at: '2026-10-16T08:00:00Z',
    last_activity_at: '2026-10-16T08:30:00Z',
    expires_at: '2026-10-23T08:00:00Z',
    is_current: true,
  },
  {
    session_id: 'sid_remote_2',
    device_family: 'Mobile',
    os_family: 'iOS',
    browser_family: 'Safari',
    ip_address: '190.237.45.***',
    created_at: '2026-10-15T12:00:00Z',
    last_activity_at: '2026-10-15T14:00:00Z',
    expires_at: '2026-10-22T12:00:00Z',
    is_current: false,
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  listUserSessions.mockResolvedValue(mockSessions);
  revokeUserSession.mockResolvedValue();
  revokeOtherUserSessions.mockResolvedValue({ message: 'Se cerraron 1 sesiones en otros dispositivos.' });
});

afterEach(cleanup);

describe('SessionManagementPanel', () => {
  it('renders active sessions with current badge and device info', async () => {
    renderWithQueryClient(<SessionManagementPanel />);
    expect(await screen.findByText('Chrome en Windows')).toBeInTheDocument();
    expect(screen.getByText('Dispositivos y sesiones activas')).toBeInTheDocument();
    expect(screen.getByText('Safari en iOS')).toBeInTheDocument();
    expect(screen.getByText('Sesión actual')).toBeInTheDocument();
    expect(screen.getByText('Este equipo')).toBeInTheDocument();
  });

  it('allows revoking a specific remote session', async () => {
    renderWithQueryClient(<SessionManagementPanel />);
    const revokeBtn = await screen.findByRole('button', { name: 'Cerrar sesión' }, { timeout: 3000 });
    expect(revokeBtn).toBeInTheDocument();

    fireEvent.click(revokeBtn);
    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(revokeUserSession).toHaveBeenCalledWith('sid_remote_2');
    });
  });

  it('allows revoking all other sessions when remote sessions exist', async () => {
    renderWithQueryClient(<SessionManagementPanel />);
    const revokeOthersBtn = await screen.findByRole('button', { name: 'Cerrar las demás sesiones' }, { timeout: 3000 });
    expect(revokeOthersBtn).toBeInTheDocument();

    fireEvent.click(revokeOthersBtn);
    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(revokeOtherUserSessions).toHaveBeenCalled();
    });
  });

  it('does not display "Cerrar las demás sesiones" if only current session is active', async () => {
    listUserSessions.mockResolvedValue([mockSessions[0]]);
    renderWithQueryClient(<SessionManagementPanel />);
    expect(await screen.findByText('Chrome en Windows')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cerrar las demás sesiones' })).not.toBeInTheDocument();
  });
});
