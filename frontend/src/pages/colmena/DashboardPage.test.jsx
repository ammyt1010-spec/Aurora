import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { renderWithQueryClient } from '../../test-utils/renderWithQueryClient.jsx';
import DashboardPage from './DashboardPage.jsx';
import { getCensopasPlans, listDisciplines, listInstruments } from '../../api/instruments.js';
import { listProjects } from '../../api/projects.js';

vi.mock('../../api/instruments.js', () => ({
  getCensopasPlans: vi.fn(),
  listDisciplines: vi.fn(),
  listInstruments: vi.fn(),
  validateInstrumentVersion: vi.fn(),
  linkStudyInstrument: vi.fn(),
}));
vi.mock('../../api/projects.js', () => ({ listProjects: vi.fn() }));
import { availableInstrumentCards } from './DashboardPage.jsx';

describe('AURORA instrument catalog', () => {
  beforeEach(() => {
    listDisciplines.mockResolvedValue([]);
    listInstruments.mockResolvedValue({ items: [] });
    listProjects.mockResolvedValue({ items: [] });
  });
  it('renders real published instruments instead of phantom catalog items', async () => {
    getCensopasPlans.mockResolvedValue({
      plans: [
        { version_kind: 'MEDIUM', instrument_version_id: 100,
          version_code: 'MEDIUM-OFICIAL', question_count: 112,
          scored_item_count: 69, dimension_count: 6, subdimension_count: 20,
          ready_for_scoring: true },
      ],
    });
    renderWithQueryClient(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(await screen.findByText('CENSOPAS-COPSOQ, versión media')).toBeInTheDocument();
    expect(screen.getByText(/112 preguntas, 69 ítems puntuables/)).toBeInTheDocument();
    expect(screen.queryByText('Clima de Seguridad Industrial')).not.toBeInTheDocument();
    expect(screen.queryByText('Salud Ocupacional & Ergonomía')).not.toBeInTheDocument();
  });

  it('renders an actionable server error rather than throwing a React tree error', async () => {
    getCensopasPlans.mockRejectedValue(new Error('API temporalmente indisponible'));
    renderWithQueryClient(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(await screen.findByText('No se pudo cargar el catálogo', {}, { timeout: 5000 })).toBeInTheDocument();
  });

  it('does not invent instruments not published in the backend', () => {
    const cards = availableInstrumentCards({ plans: [
      { version_kind: 'SHORT', instrument_version_id: 11, ready_for_scoring: true },
      { version_kind: 'MEDIUM', instrument_version_id: 12, ready_for_scoring: true },
      { version_kind: 'FAKE', instrument_version_id: 13, ready_for_scoring: true },
    ] });
    expect(cards).toHaveLength(2);
    expect(cards.map((card) => card.instrument_version_id)).toEqual([12, 11]);
  });

  it('does not confuse absence of published data with fake fallback cards', () => {
    expect(availableInstrumentCards({ plans: [] })).toEqual([]);
    expect(availableInstrumentCards(null)).toEqual([]);
  });

  it('prefers the scoring-ready version of a published instrument', () => {
    const cards = availableInstrumentCards({ plans: [
      { version_kind: 'SHORT', instrument_version_id: 1, ready_for_scoring: false },
      { version_kind: 'SHORT', instrument_version_id: 2, ready_for_scoring: true },
    ] });
    expect(cards[0].instrument_version_id).toBe(2);
  });
});
