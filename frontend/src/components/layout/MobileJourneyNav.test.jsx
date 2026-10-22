import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { MobileJourneyNav } from './MobileJourneyNav.jsx';

describe('AURORA: tres pantallas', () => {
  it('expone solo inicio, telemetria e informe en movil', () => {
    render(<MemoryRouter initialEntries={['/colmena/telemetry']}><MobileJourneyNav /></MemoryRouter>);
    const nav = screen.getByRole('navigation', { name: 'Pantallas principales' });
    const links = nav.querySelectorAll('a');
    expect(links).toHaveLength(3);
    expect([...links].map(link => link.textContent)).toEqual(['Inicio', 'Telemetría', 'Informe']);
    expect(links[1]).toHaveAttribute('aria-current', 'page');
    expect(links[0]).toHaveAttribute('href', '/colmena');
    expect(links[2]).toHaveAttribute('href', '/colmena/reports');
  });
});
