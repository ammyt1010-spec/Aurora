import { describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { renderWithQueryClient } from '../test-utils/renderWithQueryClient.jsx';
import { getRegistrationPolicy } from '../api/auth.js';
import { useAuth } from '../auth/AuthContext.jsx';
import LoginPage from './LoginPage.jsx';

vi.mock('../api/auth.js', () => ({ getRegistrationPolicy: vi.fn() }));
vi.mock('../auth/AuthContext.jsx', () => ({ useAuth: vi.fn() }));

describe('AURORA public sign-in presentation', () => {
  it('keeps account access and a clear route back to the product page', async () => {
    useAuth.mockReturnValue({ login: vi.fn(), demoLogin: vi.fn() });
    getRegistrationPolicy.mockResolvedValue({ self_registration_enabled: true });
    renderWithQueryClient(<MemoryRouter><LoginPage /></MemoryRouter>);
    expect(screen.getByRole('heading', { name: 'Bienvenido a AURORA' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ingresar con credenciales' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Volver al inicio/ })).toHaveAttribute('href', '/');
    expect(await screen.findByRole('link', { name: 'Crear cuenta' })).toHaveAttribute('href', '/signup');
  });
});
