import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from './LoginPage.jsx';

const { login, demoLogin, navigate } = vi.hoisted(() => ({
  login: vi.fn(),
  demoLogin: vi.fn(),
  navigate: vi.fn(),
}));
vi.mock('../auth/AuthContext.jsx', () => ({
  useAuth: () => ({ login, demoLogin }),
}));
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal()),
  useNavigate: () => navigate,
}));

function renderLogin() {
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
}

describe('credential-free demo login', () => {
  beforeEach(() => vi.resetAllMocks());

  it('fails visibly without ordinary-login fallback or navigation', async () => {
    demoLogin.mockRejectedValue(new Error('unavailable'));
    renderLogin();
    fireEvent.click(screen.getByRole('button', { name: /Ver Demo Minera/i }));
    expect(
      await screen.findByText(/No se pudo iniciar el modo demostración/),
    ).toBeInTheDocument();
    expect(demoLogin).toHaveBeenCalledOnce();
    expect(login).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });

  it('uses only the public demo flow and clears a previous error on retry', async () => {
    demoLogin
      .mockRejectedValueOnce(new Error('unavailable'))
      .mockResolvedValueOnce({});
    renderLogin();
    const button = screen.getByRole('button', { name: /Ver Demo Minera/i });
    fireEvent.click(button);
    await screen.findByText(/No se pudo iniciar el modo demostración/);
    fireEvent.click(button);
    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith('/colmena/project/23/telemetry', {
        replace: true,
      }),
    );
    expect(
      screen.queryByText(/No se pudo iniciar el modo demostración/),
    ).not.toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });
});
