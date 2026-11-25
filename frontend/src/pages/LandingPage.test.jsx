import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { renderWithQueryClient } from '../test-utils/renderWithQueryClient.jsx';
import { getRegistrationPolicy } from '../api/auth.js';
import { useAuth } from '../auth/AuthContext.jsx';
import LandingPage from './LandingPage.jsx';

vi.mock('../api/auth.js', () => ({ getRegistrationPolicy: vi.fn() }));
vi.mock('../auth/AuthContext.jsx', () => ({ useAuth: vi.fn() }));

const renderLanding = () => renderWithQueryClient(<MemoryRouter><LandingPage /></MemoryRouter>);

describe('AURORA public landing', () => {
  beforeEach(() => {
    useAuth.mockReturnValue({ status: 'anonymous' });
    getRegistrationPolicy.mockResolvedValue({ self_registration_enabled: true });
  });

  it('explains the live product without presenting sample metrics as company data', async () => {
    renderLanding();
    expect(screen.getByRole('heading', { name: /El riesgo que no se ve/ })).toBeInTheDocument();
    expect((await screen.findAllByRole('link', { name: /Crear cuenta empresarial/ })).every((link) => link.getAttribute('href') === '/signup')).toBe(true);
    expect(screen.getByText('Datos ilustrativos')).toBeInTheDocument();
    expect(screen.getByText('Versión corta')).toBeInTheDocument();
    expect(screen.getByText('Versión media')).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'Crear cuenta' })).toHaveAttribute('href', '/signup');
  });

  it('opens accessible mobile navigation and points an authenticated user to the panel', async () => {
    useAuth.mockReturnValue({ status: 'authenticated' });
    renderLanding();
    const menu = screen.getByRole('button', { name: 'Abrir menú' });
    expect(menu).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(menu);
    expect(screen.getByRole('button', { name: 'Cerrar menú' })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getAllByRole('link', { name: 'Ir a mi panel' }).every((link) => link.getAttribute('href') === '/colmena')).toBe(true);
  });

  it('does not invite registrations when policy is closed', async () => {
    getRegistrationPolicy.mockResolvedValue({ self_registration_enabled: false });
    renderLanding();
    expect((await screen.findAllByRole('link', { name: 'Ingresar a AURORA' })).every((link) => link.getAttribute('href') === '/login')).toBe(true);
    expect(screen.queryByRole('link', { name: 'Crear cuenta' })).not.toBeInTheDocument();
  });
});
