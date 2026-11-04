import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { renderWithQueryClient } from '../../test-utils/renderWithQueryClient.jsx';
import { getCensopasPlans } from '../../api/instruments.js';
import DashboardPage, { availableInstrumentCards } from './DashboardPage.jsx';

vi.mock('../../api/instruments.js', () => ({ getCensopasPlans: vi.fn() }));

const OFFICIAL_PLANS = {
  plans: [
    {
      version_kind: 'SHORT', version_code: 'SHORT-OFICIAL', instrument_version_id: 3,
      question_count: 42, scored_item_count: 31, dimension_count: 6, subdimension_count: 0,
      ready_for_scoring: true,
    },
    {
      version_kind: 'MEDIUM', version_code: 'MEDIUM-OFICIAL', instrument_version_id: 4,
      question_count: 112, scored_item_count: 69, dimension_count: 6, subdimension_count: 20,
      ready_for_scoring: true,
    },
  ],
};

describe('AURORA simple instrument cart', () => {
  beforeEach(() => getCensopasPlans.mockResolvedValue(OFFICIAL_PLANS));

  const renderDashboard = () => renderWithQueryClient(<MemoryRouter><DashboardPage /></MemoryRouter>);

  it('shows only the two accepted official versions, short first', async () => {
    renderDashboard();
    const short = await screen.findByText('CENSOPAS-COPSOQ, versión corta');
    const medium = screen.getByText('CENSOPAS-COPSOQ, versión media');
    expect(short.compareDocumentPosition(medium) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText(/42 preguntas · 31 ítems puntuables/)).toBeInTheDocument();
    expect(screen.getByText(/112 preguntas · 69 ítems puntuables/)).toBeInTheDocument();
  });

  it('excludes non-official and invented variants', () => {
    const cards = availableInstrumentCards({ plans: [
      ...OFFICIAL_PLANS.plans,
      { version_kind: 'SHORT', version_code: 'SHORT-DEMO', instrument_version_id: 9 },
      { version_kind: 'PREMIUM', version_code: 'PREMIUM', instrument_version_id: 10 },
    ] });
    expect(cards.map((item) => item.instrument_version_id)).toEqual([3, 4]);
  });

  it('adds instruments to the cart and opens the link and QR generator', async () => {
    renderDashboard();
    const boxes = await screen.findAllByRole('checkbox');
    const generate = screen.getByRole('button', { name: 'Continuar · generar enlace y QR' });
    expect(generate).toBeDisabled();
    fireEvent.click(boxes[0]);
    fireEvent.click(boxes[1]);
    expect(generate).toBeEnabled();
    fireEvent.click(generate);
    expect(await screen.findByText('Datos de la empresa')).toBeInTheDocument();
    expect(screen.getByText('Completa estos datos una vez. Aurora generará un enlace independiente por instrumento.')).toBeInTheDocument();
  });

  it('shows a clear empty state when no official instrument is published', async () => {
    getCensopasPlans.mockResolvedValue({ plans: [] });
    renderDashboard();
    expect(await screen.findByText('No hay instrumentos oficiales disponibles')).toBeInTheDocument();
  });
});
