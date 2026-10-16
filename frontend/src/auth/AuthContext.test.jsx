import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

import { AuthProvider, useAuth } from './AuthContext.jsx';
import { fetchCurrentUser, logoutUser } from '../api/auth.js';

vi.mock('../api/auth.js', () => ({
  fetchCurrentUser: vi.fn(),
  logoutUser: vi.fn(),
  loginUser: vi.fn(),
  demoLoginUser: vi.fn(),
  registerUser: vi.fn(),
}));

function createDeferred() {
  let resolve;
  let reject;
  const promise = new Promise((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

function AuthProbe() {
  const { status, user, logout } = useAuth();
  const close = () => logout().catch(() => {});
  return (
    <div>
      <span data-testid="auth-status">{status}</span>
      <span data-testid="auth-user">{user?.email || 'none'}</span>
      <button type="button" onClick={close}>Cerrar sesión</button>
    </div>
  );
}

function mountAuthenticatedProvider() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(['private-project', 9], { company: 'Empresa A' });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AuthProvider><AuthProbe /></AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

beforeEach(() => {
  vi.clearAllMocks();
  fetchCurrentUser.mockResolvedValue({ id: 1, email: 'admin@aurora.test' });
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe('AURORA browser logout', () => {
  it('does not claim success until the backend confirms revocation', async () => {
    const pending = createDeferred();
    logoutUser.mockReturnValue(pending.promise);
    const client = mountAuthenticatedProvider();

    expect(await screen.findByText('authenticated')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }));
    expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated');
    expect(client.getQueryData(['private-project', 9])).toBeDefined();

    pending.resolve(null);
    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('anonymous');
    });
    expect(screen.getByTestId('auth-user')).toHaveTextContent('none');
    expect(client.getQueryData(['private-project', 9])).toBeUndefined();
    expect(logoutUser).toHaveBeenCalledTimes(1);
  });

  it('retains authentication and private cache when logout fails', async () => {
    const pending = createDeferred();
    logoutUser.mockReturnValue(pending.promise);
    const client = mountAuthenticatedProvider();

    expect(await screen.findByText('authenticated')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }));
    pending.reject(new Error('backend unavailable'));

    await waitFor(() => expect(logoutUser).toHaveBeenCalledTimes(1));
    // Allow the catch handler to execute before inspecting the current state.
    await waitFor(() => expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated'));
    expect(screen.getByTestId('auth-user')).toHaveTextContent('admin@aurora.test');
    expect(client.getQueryData(['private-project', 9])).toEqual({ company: 'Empresa A' });
  });

  it('coalesces multiple logout clicks into a single API revocation', async () => {
    const pending = createDeferred();
    logoutUser.mockReturnValue(pending.promise);
    mountAuthenticatedProvider();

    expect(await screen.findByText('authenticated')).toBeInTheDocument();
    const button = screen.getByRole('button', { name: 'Cerrar sesión' });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(logoutUser).toHaveBeenCalledTimes(1);

    pending.resolve(null);
    await waitFor(() => expect(screen.getByTestId('auth-status')).toHaveTextContent('anonymous'));
  });
});
