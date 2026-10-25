import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithQueryClient } from '../../../test-utils/renderWithQueryClient.jsx';
import { getProjectLongitudinal } from '../../../api/analytics.js';
import LongitudinalBIWidget from './LongitudinalBIWidget.jsx';
vi.mock('../../../api/analytics.js', () => ({
  getProjectLongitudinal: vi.fn(),
}));
// Expose the exact chart input rather than asserting unrelated hidden table text.
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  LineChart: ({ data, children }) => (
    <svg
      role="img"
      aria-label="Serie temporal"
      data-points={JSON.stringify(data)}
    >
      {children}
    </svg>
  ),
  Line: ({ connectNulls, type }) => (
    <path data-connect-nulls={String(connectNulls)} data-interpolation={type} />
  ),
  CartesianGrid: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));
const point = (name, value, extra = {}) => ({
  study_name: name,
  unfavorable_pct: value,
  ...extra,
});
const trend = {
  construct_type: 'DIMENSION',
  construct_code: 'D1',
  construct_name: 'Carga',
  is_comparable: true,
  methodological_equivalence: true,
  points: [point('A', 20), point('B', 40)],
};
const render = (dimension = 'D1') =>
  renderWithQueryClient(
    <LongitudinalBIWidget projectId={8} dimension={dimension} />,
  );
beforeEach(() => {
  vi.clearAllMocks();
  getProjectLongitudinal.mockResolvedValue({ constructs: [trend] });
});
describe('authentic longitudinal visualization', () => {
  it('shows exact backend chart values and no spline inference', async () => {
    render();
    const chart = await screen.findByRole('img', { name: 'Serie temporal' });
    expect(chart).toBeVisible();
    expect(
      JSON.parse(chart.dataset.points).map((p) => p.unfavorable_pct),
    ).toEqual([20, 40]);
    expect(chart.querySelector('path')).toHaveAttribute(
      'data-interpolation',
      'linear',
    );
  });
  it.each([{ is_comparable: false }, { methodological_equivalence: false }])(
    'gates incompatible measurements %j',
    async (flags) => {
      getProjectLongitudinal.mockResolvedValue({
        constructs: [{ ...trend, ...flags }],
      });
      render();
      expect(await screen.findByRole('status')).toHaveTextContent(
        'comparabilidad no validada',
      );
      expect(screen.queryByRole('img')).not.toBeInTheDocument();
    },
  );
  it('keeps gaps instead of connecting missing, invalid or suppressed observations', async () => {
    getProjectLongitudinal.mockResolvedValue({
      constructs: [
        {
          ...trend,
          points: [
            point('A', 20),
            point('B', 45, { suppressed: true }),
            point('C', 101),
            point('D', null),
            point('E', 40),
          ],
        },
      ],
    });
    render();
    const chart = await screen.findByRole('img', { name: 'Serie temporal' });
    expect(
      JSON.parse(chart.dataset.points).map((p) => p.unfavorable_pct),
    ).toEqual([20, null, null, null, 40]);
    expect(chart.querySelector('path')).toHaveAttribute(
      'data-connect-nulls',
      'false',
    );
    expect(chart.dataset.points).not.toContain('45');
  });
  it('does not substitute another dimension when selected dimension is missing', async () => {
    render('D9');
    expect(
      await screen.findByText(
        'Todavía no hay dimensiones con mediciones comparables.',
      ),
    ).toBeVisible();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
  it('requires two valid points', async () => {
    getProjectLongitudinal.mockResolvedValue({
      constructs: [{ ...trend, points: [point('A', 20), point('B', -1)] }],
    });
    render();
    expect(await screen.findByText(/Se requieren al menos dos/)).toBeVisible();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
  it('shows request errors', async () => {
    getProjectLongitudinal.mockRejectedValue(new Error('offline'));
    render();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo consultar',
    );
  });
});
