import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { renderWithQueryClient } from '../../../test-utils/renderWithQueryClient.jsx';
import { getCensopasReadiness } from '../../../api/instruments.js';
import { getExecutiveDashboard } from '../../../api/reports.js';
import {
  getCensopasResults, getCensopasUnitResults, getResultsOverview, getStudy, listStudyUnitTypes,
} from '../../../api/studies.js';
import PremiumBIWorkspace from './PremiumBIWorkspace.jsx';

vi.mock('../../../api/instruments.js', () => ({ getCensopasReadiness: vi.fn() }));
vi.mock('../../../api/reports.js', () => ({ getExecutiveDashboard: vi.fn() }));
vi.mock('../../../api/studies.js', () => ({
  getCensopasResults: vi.fn(),
  getCensopasUnitResults: vi.fn(),
  getResultsOverview: vi.fn(),
  getStudy: vi.fn(),
  listStudyUnitTypes: vi.fn(),
}));

const basicDimension = {
  construct_type: 'DIMENSION', construct_code: 'D1', construct_name: 'Carga laboral',
  n_valid: 48, suppressed: false, priority_rank: 1,
  unfavorable_pct: 48, intermediate_pct: 31, favorable_pct: 21,
};
const suppressedDimension = {
  ...basicDimension, construct_code: 'D2', construct_name: 'Dimensión confidencial',
  suppressed: true, unfavorable_pct: null, intermediate_pct: null, favorable_pct: null,
};

function renderDashboard() {
  return renderWithQueryClient(<MemoryRouter><PremiumBIWorkspace projectId={5} studyId={12} telemetry={{ valid_count: 48 }} /></MemoryRouter>);
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.removeItem('aurora:bi:layout:v1');
  getStudy.mockResolvedValue({ id: 12, instrument_version_id: 21 });
  getCensopasReadiness.mockResolvedValue({ is_censopas_instrument: true });
  getCensopasResults.mockResolvedValue({ results: [basicDimension, suppressedDimension], scoring_status: 'COMPLETED' });
  getResultsOverview.mockResolvedValue({ results: [] });
  listStudyUnitTypes.mockResolvedValue([{ id: 3, name: 'Áreas' }]);
  getCensopasUnitResults.mockResolvedValue({
    min_publishable_n: 10, results: [
      { ...basicDimension, unit_id: 8, unit_name: 'Operaciones', unfavorable_pct: 58, intermediate_pct: 21, favorable_pct: 21 },
      { ...suppressedDimension, unit_id: 9, unit_name: 'Equipo pequeño', unfavorable_pct: null },
    ],
  });
  getExecutiveDashboard.mockResolvedValue({
    participation: { valid_count: 48 },
    risk_distribution: { high_risk_count: 1, medium_risk_count: 0, low_risk_count: 0 },
    headline: 'Se requiere intervención preventiva.',
    construct_rankings: [{
      construct_code: 'D1', construct_name: 'Carga laboral',
      traffic_light: 'RED', recommendation: 'Revisar distribución de turnos.',
    }],
  });
});

describe('AURORA BI workspace', () => {
  it('presents only server-derived publishable dimensions', async () => {
    renderDashboard();
    expect(await screen.findByText('Mapa de riesgos por dimensión')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Carga laboral: 48.0% desfavorable/ })).toBeInTheDocument();
    expect(screen.queryByText('Dimensión confidencial')).not.toBeInTheDocument();
    expect(screen.getByText('Se requiere intervención preventiva.')).toBeInTheDocument();
  });

  it('lets the corporate user choose and order widgets', async () => {
    renderDashboard();
    expect(await screen.findByText('Mapa de riesgos por dimensión')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Elegir cuadros' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Prioridades' }));
    expect(screen.queryByText('Prioridades de intervención')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Subir Hallazgos y acciones' }));
    await waitFor(() => expect(JSON.parse(localStorage.getItem('aurora:bi:layout:v1'))).not.toContain('ranking'));
  });

  it('loads a real server-approved segment without showing suppressed groups', async () => {
    renderDashboard();
    expect(await screen.findByText('Mapa de riesgos por dimensión')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Segmento'), { target: { value: '3' } });
    expect(await screen.findByRole('option', { name: 'Operaciones' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Equipo pequeño' })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Unidad'), { target: { value: '8' } });
    expect(await screen.findByText(/Filtro activo: Operaciones/)).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Carga laboral: 58.0% desfavorable/ })).toBeInTheDocument();
    expect(screen.getByText(/Las recomendaciones globales no se atribuyen a segmentos/)).toBeInTheDocument();
    expect(screen.queryByText('Equipo pequeño')).not.toBeInTheDocument();
  });
});
