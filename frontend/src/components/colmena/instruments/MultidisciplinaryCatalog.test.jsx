import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, screen } from '@testing-library/react';

import { renderWithQueryClient } from '../../../test-utils/renderWithQueryClient.jsx';
import { listInstruments, listDisciplines, validateInstrumentVersion, linkStudyInstrument } from '../../../api/instruments.js';
import MultidisciplinaryCatalog from './MultidisciplinaryCatalog.jsx';

vi.mock('../../../api/instruments.js', () => ({
  listDisciplines: vi.fn(),
  listInstruments: vi.fn(),
  validateInstrumentVersion: vi.fn(),
  linkStudyInstrument: vi.fn(),
}));

const mockDisciplines = [
  { code: 'PSICOSOCIAL', name: 'Riesgos Psicosociales' },
  { code: 'ERGONOMIA', name: 'Ergonomía y Factores Físicos' },
  { code: 'LIDERAZGO_BURNOUT', name: 'Liderazgo y Burnout (MBI)' },
];

const mockInstruments = [
  {
    id: 1,
    code: 'CENSOPAS_COPSOQ_SHORT',
    name: 'CENSOPAS-COPSOQ Versión Corta',
    discipline: 'PSICOSOCIAL',
    description: 'Cuestionario oficial de riesgos psicosociales en el trabajo.',
    author: 'CENSOPAS Perú',
    reproduction_terms: 'Uso oficial bajo licencia institucional.',
    method_code: 'CENSOPAS_CORTA',
    status: 'AUTHORIZED',
    is_system: true,
    metadata: { default_version_id: 10 },
  },
  {
    id: 2,
    code: 'BURNOUT_MBI_GS',
    name: 'Inventario de Burnout de Maslach (MBI-GS)',
    discipline: 'LIDERAZGO_BURNOUT',
    description: 'Evaluación de agotamiento emocional, despersonalización y realización.',
    author: 'C. Maslach & S. Jackson',
    reproduction_terms: 'Licencia académica autorizada.',
    method_code: 'BURNOUT_MBI',
    status: 'VALIDATING',
    is_system: false,
    metadata: { default_version_id: 20 },
  },
  {
    id: 3,
    code: 'ERGONOMIA_ROSA_V1',
    name: 'Evaluación Rápida de Tensión en Oficina (ROSA)',
    discipline: 'ERGONOMIA',
    description: 'Método ergonómico para puestos de oficina con pantallas de visualización.',
    author: 'M. Sonne et al.',
    reproduction_terms: 'Dominio público con atribución.',
    method_code: 'ERGONOMIA_ROSA',
    status: 'DRAFT',
    is_system: false,
    metadata: { default_version_id: 30 },
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  window.alert = vi.fn();
  listDisciplines.mockResolvedValue(mockDisciplines);
  listInstruments.mockResolvedValue({ items: mockInstruments, total: 3 });
});

afterEach(() => {
  cleanup();
});

describe('MultidisciplinaryCatalog', () => {
  it('renders all instruments with discipline badges and status pills', async () => {
    renderWithQueryClient(
      <MultidisciplinaryCatalog projectId={1} currentStudyId={100} currentVersionId={10} />
    );

    // Instrument titles
    expect(await screen.findByText('CENSOPAS-COPSOQ Versión Corta')).toBeInTheDocument();
    expect(screen.getByText('Inventario de Burnout de Maslach (MBI-GS)')).toBeInTheDocument();
    expect(screen.getByText('Evaluación Rápida de Tensión en Oficina (ROSA)')).toBeInTheDocument();

    // Status badges (filter options also exist, so use getAllByText)
    expect(screen.getAllByText('Autorizado').length).toBeGreaterThan(0);
    expect(screen.getAllByText('En Validación').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Borrador').length).toBeGreaterThan(0);

    // Disciplines
    expect(screen.getByText('PSICOSOCIAL')).toBeInTheDocument();
    expect(screen.getByText('LIDERAZGO_BURNOUT')).toBeInTheDocument();
    expect(screen.getByText('ERGONOMIA')).toBeInTheDocument();

    // Reproduction terms
    expect(screen.getByText(/Uso oficial bajo licencia institucional/i)).toBeInTheDocument();
  });

  it('filters instruments when a discipline pill is selected', async () => {
    renderWithQueryClient(
      <MultidisciplinaryCatalog projectId={1} currentStudyId={100} currentVersionId={10} />
    );

    const ergoButton = await screen.findByRole('button', { name: /Ergonomía/i });
    fireEvent.click(ergoButton);

    expect(listInstruments).toHaveBeenCalledWith(
      expect.objectContaining({
        discipline: 'ERGONOMIA',
      })
    );
  });

  it('supports linking an instrument to the current study', async () => {
    linkStudyInstrument.mockResolvedValue({ status: 'success' });

    renderWithQueryClient(
      <MultidisciplinaryCatalog projectId={1} currentStudyId={100} currentVersionId={10} />
    );

    expect(await screen.findByText('CENSOPAS-COPSOQ Versión Corta')).toBeInTheDocument();
    const linkButtons = await screen.findAllByRole('button', { name: /Vincular a Estudio/i });
    expect(linkButtons.length).toBeGreaterThan(0);

    fireEvent.click(linkButtons[0]);
    await vi.waitFor(() => {
      expect(linkStudyInstrument).toHaveBeenCalledWith(100, 10);
    });
  });
});
