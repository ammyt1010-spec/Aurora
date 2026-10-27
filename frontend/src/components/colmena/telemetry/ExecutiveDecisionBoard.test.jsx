import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { renderWithQueryClient } from '../../../test-utils/renderWithQueryClient.jsx';
import ExecutiveDecisionBoard from './ExecutiveDecisionBoard.jsx';
import { getCensopasReadiness } from '../../../api/instruments.js';
import { getExecutiveDashboard } from '../../../api/reports.js';
import {
  getCensopasResults,
  getCensopasUnitResults,
  getResultsOverview,
  getStudy,
  listStudyUnitTypes,
} from '../../../api/studies.js';

vi.mock('./LongitudinalBIWidget.jsx', () => ({
  default: () => <div>Longitudinal view loaded</div>,
}));
vi.mock('../../../api/instruments.js', () => ({
  getCensopasReadiness: vi.fn(),
}));
vi.mock('../../../api/reports.js', () => ({ getExecutiveDashboard: vi.fn() }));
vi.mock('../../../api/studies.js', () => ({
  getCensopasResults: vi.fn(),
  getCensopasUnitResults: vi.fn(),
  getResultsOverview: vi.fn(),
  getStudy: vi.fn(),
  listStudyUnitTypes: vi.fn(),
}));

const dimension = {
  construct_code: 'D1',
  construct_name: 'Carga laboral',
  construct_type: 'DIMENSION',
  n_valid: 80,
  suppressed: false,
  favorable_pct: 20,
  intermediate_pct: 30,
  unfavorable_pct: 50,
  collective_classification: 'RIESGO_ALTO',
  priority_rank: 1,
};
const hidden = {
  ...dimension,
  construct_code: 'D2',
  construct_name: 'Privado',
  suppressed: true,
  favorable_pct: null,
  intermediate_pct: null,
  unfavorable_pct: null,
};

function renderBoard(telemetry = { valid_count: 80 }) {
  return renderWithQueryClient(
    <MemoryRouter>
      <ExecutiveDecisionBoard
        projectId={8}
        studyId={19}
        telemetry={telemetry}
      />
    </MemoryRouter>,
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  getStudy.mockResolvedValue({ id: 19, instrument_version_id: 7 });
  getCensopasReadiness.mockResolvedValue({ is_censopas_instrument: true });
  getCensopasResults.mockResolvedValue({
    analysis_run_id: 41,
    results: [dimension, hidden],
  });
  getResultsOverview.mockResolvedValue({ results: [] });
  getExecutiveDashboard.mockResolvedValue({
    analysis_run_id: 41,
    construct_rankings: [
      {
        construct_code: 'D1',
        recommendation: 'Evaluar distribuci�n de cargas',
      },
    ],
    risk_distribution: { high_risk_count: 1 },
    participation: { valid_count: 80 },
  });
  listStudyUnitTypes.mockResolvedValue([{ id: 3, name: '�reas' }]);
  getCensopasUnitResults.mockResolvedValue({
    analysis_run_id: 41,
    results: [
      {
        ...dimension,
        unit_id: 20,
        unit_name: 'Operaciones',
        unfavorable_pct: 60,
        intermediate_pct: 20,
        favorable_pct: 20,
      },
      { ...hidden, unit_id: 22, unit_name: 'Equipo confidencial' },
    ],
  });
});

describe('AURORA single-screen executive canvas', () => {
  it('keeps capture telemetry visible when no scoring run exists and marks analysis N/D', async () => {
    getCensopasResults.mockRejectedValue(
      Object.assign(new Error('scoring not completed'), {
        status: 409,
        errorCode: 'CONFLICT',
        body: { latest_run_status: null },
      }),
    );
    renderBoard({ valid_count: 1 });

    expect(
      await screen.findByRole('status'),
    ).toHaveTextContent('todav�a no tiene una corrida de scoring completada');
    expect(screen.getByTestId('metric-Respuestas v�lidas')).toHaveTextContent('1');
    expect(screen.getByTestId('metric-Dimensiones publicables')).toHaveTextContent('N/D');
    expect(screen.queryByRole('img', { name: /Distribuci�n de/ })).not.toBeInTheDocument();
    expect(getExecutiveDashboard).not.toHaveBeenCalled();
  });

  it('still surfaces a failed scoring run as an actual diagnostic error', async () => {
    getCensopasResults.mockRejectedValue(
      Object.assign(new Error('scoring failed'), {
        status: 409,
        errorCode: 'CONFLICT',
        body: { latest_run_status: 'FAILED' },
      }),
    );
    renderBoard({ valid_count: 1 });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo consultar el diagn�stico metodol�gico',
    );
    expect(screen.queryByTestId('metric-Respuestas v�lidas')).not.toBeInTheDocument();
  });

  it.each([401, 403, 500])('does not treat HTTP %i as an absent scoring run', async (status) => {
    getCensopasResults.mockRejectedValue(
      Object.assign(new Error('request failed'), {
        status,
        errorCode: status === 401 ? 'AUTHENTICATION_ERROR' : status === 403 ? 'FORBIDDEN' : 'SERVER_ERROR',
        body: { latest_run_status: null },
      }),
    );
    renderBoard({ valid_count: 1 });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo consultar el diagn�stico metodol�gico',
    );
    expect(screen.queryByTestId('metric-Respuestas v�lidas')).not.toBeInTheDocument();
  });

  it('unifies management diagnosis and excludes private rows', async () => {
    renderBoard();
    expect(
      await screen.findByRole('heading', {
        name: 'Dimensiones y comparaciones',
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Qu� significa' }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText('Evaluar distribuci�n de cargas'),
    ).toBeInTheDocument();
    expect(screen.queryByText('Privado')).not.toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('80')).toBeInTheDocument();
    expect(screen.getByText('Riesgo alto')).toBeInTheDocument();
  });
  it('filters authorized segments without exposing suppressed units', async () => {
    renderBoard();
    expect(
      await screen.findByRole('heading', { name: 'Diagn�stico ejecutivo' }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Tipo de segmento'), {
      target: { value: '3' },
    });
    expect(
      await screen.findByRole('columnheader', { name: 'Operaciones' }),
    ).toBeInTheDocument();
    expect(screen.queryByText('Equipo confidencial')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Unidad del segmento'), {
      target: { value: '20' },
    });
    expect(
      screen.getByText('Comparaci�n descriptiva por segmento'),
    ).toBeInTheDocument();
    expect(
      screen.queryByText('Evaluar distribuci�n de cargas'),
    ).not.toBeInTheDocument();
    expect(screen.getAllByText('60.0%').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Restablecer' }));
    expect(screen.getByLabelText('Tipo de segmento').value).toBe('');
  });
  it('keeps generic scores distinct from CENSOPAS categories', async () => {
    getCensopasReadiness.mockResolvedValue({ is_censopas_instrument: false });
    getResultsOverview.mockResolvedValue({
      results: [
        {
          construct_code: 'Q1',
          construct_name: 'Clima',
          construct_type: 'DIMENSION',
          suppressed: false,
          mean_score: 72,
        },
      ],
    });
    renderBoard();
    expect(
      await screen.findByText(
        'Puntuaci�n descriptiva normalizada, no nivel de riesgo',
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText('Riesgo alto')).not.toBeInTheDocument();
  });
  it('switches analyses in place without adding vertically stacked dashboards', async () => {
    renderBoard();
    await screen.findByRole('heading', { name: 'Dimensiones y comparaciones' });
    expect(
      screen.queryByText('Longitudinal view loaded'),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Mapa de calor' }));
    expect(
      screen.getByRole('group', {
        name: 'Mapa de calor de dimensiones publicables',
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText('Privado')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Diagn�stico' }));
    fireEvent.click(screen.getByRole('button', { name: 'Evoluci�n' }));
    expect(screen.getByText('Longitudinal view loaded')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Diagn�stico' }));
    expect(
      screen.queryByText('Longitudinal view loaded'),
    ).not.toBeInTheDocument();
  });

  it('shows a real error instead of endless loading when study fails', async () => {
    getStudy.mockRejectedValue(new Error('Fall� conexi�n'));
    renderBoard();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo consultar el diagn�stico metodol�gico',
    );
  });
});

describe('visible authenticated metrics and geometry', () => {
  it.each([0, 35, 112])('keeps real N=%s with no demo fallback', async (n) => {
    if (n === 0) getCensopasResults.mockResolvedValue({ results: [] });
    renderBoard({
      valid_count: n,
      invited_count: null,
      response_rate: null,
      valid_rate: null,
    });
    expect(
      await screen.findByTestId('metric-Respuestas v�lidas'),
    ).toHaveTextContent(String(n));
    expect(screen.getByTestId('metric-Invitaciones')).toHaveTextContent('N/D');
    expect(screen.getByTestId('metric-Cobertura v�lida')).toHaveTextContent(
      'N/D',
    );
    expect(screen.queryByText('20 personas')).not.toBeInTheDocument();
    expect(
      screen.queryByText('Unidad Minera San Crist�bal'),
    ).not.toBeInTheDocument();
    expect(document.querySelector('.aurora-kpi-sparkline')).toBeNull();
    if (n === 0)
      expect(
        screen.queryByRole('img', { name: /Carga laboral/ }),
      ).not.toBeInTheDocument();
  });
  it.each([15, 65])(
    'uses changed backend unfavorable percentage %s in visible bars and donut',
    async (pct) => {
      getCensopasResults.mockResolvedValue({
        results: [
          {
            ...dimension,
            favorable_pct: 100 - pct,
            intermediate_pct: 0,
            unfavorable_pct: pct,
          },
        ],
      });
      renderBoard({
        valid_count: 35,
        invited_count: 50,
        response_rate: 0.8,
        valid_rate: 0.7,
      });
      const graph = await screen.findByRole('img', {
        name: new RegExp(`Carga laboral: Favorable`),
      });
      expect(graph).toBeVisible();
      expect(graph.querySelector('[data-band="unfavorable_pct"]')).toHaveStyle({
        width: `${pct}%`,
      });
      const donut = screen.getByRole('img', {
        name: 'Distribuci�n de Carga laboral',
      });
      expect(donut).toBeVisible();
      expect(
        donut.querySelector('[data-band="unfavorable_pct"]'),
      ).toHaveAttribute('data-value', String(pct));
      expect(
        screen.getByTestId('metric-Mayor % desfavorable'),
      ).toHaveTextContent(`${pct}.0%`);
      expect(screen.getByTestId('metric-Cobertura v�lida')).toHaveTextContent(
        '70.0%',
      );
      expect(screen.getByTestId('metric-Participaci�n')).toHaveTextContent(
        '80.0%',
      );
      expect(document.querySelector('.sr-only')).toBeNull();
    },
  );
  it('leaves missing and suppressed values unavailable and filters disabled honestly', async () => {
    getCensopasResults.mockResolvedValue({
      results: [hidden, { ...dimension, unfavorable_pct: null }],
    });
    renderBoard({});
    expect(
      await screen.findByTestId('metric-Respuestas v�lidas'),
    ).toHaveTextContent('N/D');
    expect(screen.getByTestId('metric-Mayor % desfavorable')).toHaveTextContent(
      'N/D',
    );
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(
      screen.getByLabelText('Filtros demogr�ficos no disponibles'),
    ).toBeDisabled();
    expect(screen.getByLabelText('Unidad del segmento')).toBeDisabled();
  });
  it('renders generic score geometry without CENSOPAS categories or fabricated gauges', async () => {
    getCensopasReadiness.mockResolvedValue({ is_censopas_instrument: false });
    getResultsOverview.mockResolvedValue({
      results: [{ ...dimension, mean_score: 37 }],
    });
    renderBoard();
    const graph = await screen.findByRole('img', {
      name: 'Carga laboral: puntaje 37',
    });
    expect(graph).toBeVisible();
    expect(graph.querySelector('[data-score]')).toHaveStyle({ width: '37%' });
    expect(document.querySelector('[data-band]')).toBeNull();
    expect(screen.queryByText('Riesgo alto')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Tipo de segmento')).toBeDisabled();
    expect(getCensopasResults).not.toHaveBeenCalled();
  });
  it('reports failed segment requests without invented matrix cells', async () => {
    getCensopasUnitResults.mockRejectedValue(new Error('unavailable'));
    renderBoard();
    await screen.findByRole('heading', { name: 'Diagn�stico ejecutivo' });
    fireEvent.change(screen.getByLabelText('Tipo de segmento'), {
      target: { value: '3' },
    });
    expect(
      await screen.findByText('No se pudieron consultar los segmentos. N/D'),
    ).toBeVisible();
    expect(screen.getByTestId('metric-Mayor % desfavorable')).toHaveTextContent(
      'N/D',
    );
  });
});

it('changes visible results when the dimension and unit filters change', async () => {
  getCensopasResults.mockResolvedValue({
    analysis_run_id: 41,
    results: [
      dimension,
      {
        ...dimension,
        construct_code: 'D3',
        construct_name: 'Autonom�a',
        favorable_pct: 60,
        intermediate_pct: 30,
        unfavorable_pct: 10,
      },
    ],
  });
  renderBoard();
  await screen.findByRole('img', { name: /Carga laboral: Favorable/ });
  fireEvent.change(screen.getByLabelText('Dimensi�n del diagn�stico'), {
    target: { value: 'D3' },
  });
  expect(
    screen.queryByRole('img', { name: /Carga laboral: Favorable/ }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole('img', { name: /Autonom�a: Favorable/ }),
  ).toBeVisible();
  expect(screen.getByTestId('metric-Mayor % desfavorable')).toHaveTextContent(
    '10.0%',
  );
  fireEvent.change(screen.getByLabelText('Dimensi�n del diagn�stico'), {
    target: { value: 'D1' },
  });
  fireEvent.change(screen.getByLabelText('Tipo de segmento'), {
    target: { value: '3' },
  });
  await screen.findByRole('columnheader', { name: 'Operaciones' });
  fireEvent.change(screen.getByLabelText('Unidad del segmento'), {
    target: { value: '20' },
  });
  expect(
    screen
      .getByRole('img', { name: /Carga laboral: Favorable/ })
      .querySelector('[data-band="unfavorable_pct"]'),
  ).toHaveStyle({ width: '60%' });
  expect(screen.getByRole('button', { name: 'Evoluci�n' })).toBeDisabled();
});

it('pins executive recommendations to the primary result run', async () => {
  renderBoard();
  await screen.findByText('Evaluar distribuci�n de cargas');
  expect(getExecutiveDashboard).toHaveBeenCalledWith(19, 41);
});
it('does not consult unpinned executive interpretations when the run is unknown', async () => {
  getCensopasResults.mockResolvedValue({ results: [dimension] });
  renderBoard();
  await screen.findByRole('img', { name: /Carga laboral: Favorable/ });
  expect(getExecutiveDashboard).not.toHaveBeenCalled();
  expect(
    screen.queryByText('Evaluar distribuci�n de cargas'),
  ).not.toBeInTheDocument();
});

it('fails closed when segment and primary result runs differ', async () => {
  getCensopasUnitResults.mockResolvedValue({
    analysis_run_id: 99,
    results: [
      { ...dimension, unit_id: 20, unit_name: 'Other run private context' },
    ],
  });
  renderBoard();
  await screen.findByRole('heading', { name: 'Diagn�stico ejecutivo' });
  fireEvent.change(screen.getByLabelText('Tipo de segmento'), {
    target: { value: '3' },
  });
  expect(
    await screen.findByText(/La corrida del segmento no coincide/),
  ).toBeVisible();
  expect(
    screen.getByTestId('metric-Dimensiones publicables'),
  ).toHaveTextContent('N/D');
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(
    screen.queryByText('Other run private context'),
  ).not.toBeInTheDocument();
});
it('withholds interpretations returned for a different scoring run', async () => {
  getExecutiveDashboard.mockResolvedValue({
    analysis_run_id: 99,
    construct_rankings: [
      { construct_code: 'D1', recommendation: 'Wrong run interpretation' },
    ],
  });
  renderBoard();
  await screen.findByRole('img', { name: /Carga laboral: Favorable/ });
  expect(
    screen.queryByText('Wrong run interpretation'),
  ).not.toBeInTheDocument();
});

