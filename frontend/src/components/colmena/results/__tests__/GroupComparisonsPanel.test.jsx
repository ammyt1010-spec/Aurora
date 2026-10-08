import { describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { renderWithQueryClient } from '../../../../test-utils/renderWithQueryClient.jsx';
import GroupComparisonsPanel from '../GroupComparisonsPanel.jsx';
import { formatNumber } from '../../../../utils/format.js';
import { displayLabel } from '../../../../utils/labels.js';

vi.mock('../../../../api/analytics.js', () => ({
  compareConstructGroups: vi.fn(),
}));

import { compareConstructGroups } from '../../../../api/analytics.js';

const overview = {
  results: [{ construct_id: 1, construct_name: 'D2 — Conflicto trabajo-familia', mean_score: 42.1 }],
};
const descriptives = {
  min_publishable_n: 5,
  questions: [
    {
      variable_id: 9,
      variable_label: 'Turno',
      measurement_level: 'NOMINAL',
      frequencies: [
        { code: 'A', label: 'Diurno' },
        { code: 'B', label: 'Rotativo' },
      ],
    },
  ],
};

async function compareAndWait() {
  renderWithQueryClient(<GroupComparisonsPanel studyId={1} overview={overview} descriptives={descriptives} />);
  await userEvent.click(screen.getByRole('button', { name: 'Comparar grupos' }));
}

describe('GroupComparisonsPanel — bloque de inferencia (no debe descartar el resultado estadístico)', () => {
  it('Mann-Whitney: muestra método, estadístico, p, tamaño de efecto y magnitud', async () => {
    compareConstructGroups.mockResolvedValue({
      method: 'MANN_WHITNEY',
      statistic: 2140.0,
      p_value: 0.0004,
      effect_size: 0.32,
      effect_label: 'MODERADA',
      suppressed: false,
      groups: [
        { code: 'A', n: 114, suppressed: false, mean: 40.1, median: 42.5 },
        { code: 'B', n: 66, suppressed: false, mean: 55.2, median: 58.0 },
      ],
      warnings: [],
    });

    await compareAndWait();

    await waitFor(() => expect(screen.getByText('Mann-Whitney U')).toBeInTheDocument());
    expect(screen.getByText(formatNumber(2140.0, { decimals: 2 }))).toBeInTheDocument();
    expect(screen.getByText(displayLabel('MODERADA'))).toBeInTheDocument();
    expect(screen.getByText('0.32')).toBeInTheDocument();
  });

  it('Kruskal-Wallis: muestra los mismos campos que Mann-Whitney', async () => {
    compareConstructGroups.mockResolvedValue({
      method: 'KRUSKAL_WALLIS',
      statistic: 8.71,
      p_value: 0.013,
      effect_size: 0.18,
      effect_label: 'PEQUEÑA',
      suppressed: false,
      groups: [
        { code: 'A', n: 30, suppressed: false, mean: 40, median: 41 },
        { code: 'B', n: 30, suppressed: false, mean: 50, median: 49 },
        { code: 'C', n: 30, suppressed: false, mean: 60, median: 58 },
      ],
      warnings: [],
    });

    await compareAndWait();

    await waitFor(() => expect(screen.getByText('Kruskal-Wallis')).toBeInTheDocument());
    expect(screen.getByText('8.71')).toBeInTheDocument();
    expect(screen.getByText(displayLabel('PEQUEÑA'))).toBeInTheDocument();
  });

  it('muestra q (BH) sólo cuando adjusted_p_value existe, sin inventar un placeholder cuando es null', async () => {
    compareConstructGroups.mockResolvedValue({
      method: 'MANN_WHITNEY',
      statistic: 100,
      p_value: 0.02,
      adjusted_p_value: 0.04,
      effect_size: 0.2,
      effect_label: 'PEQUEÑA',
      suppressed: false,
      groups: [
        { code: 'A', n: 10, suppressed: false, mean: 1, median: 1 },
        { code: 'B', n: 10, suppressed: false, mean: 2, median: 2 },
      ],
      warnings: [],
    });

    await compareAndWait();

    await waitFor(() => expect(screen.getByText('q (BH)')).toBeInTheDocument());
  });

  it('no muestra "q (BH)" cuando el backend no envía adjusted_p_value', async () => {
    compareConstructGroups.mockResolvedValue({
      method: 'MANN_WHITNEY',
      statistic: 100,
      p_value: 0.02,
      effect_size: 0.2,
      effect_label: 'PEQUEÑA',
      suppressed: false,
      groups: [
        { code: 'A', n: 10, suppressed: false, mean: 1, median: 1 },
        { code: 'B', n: 10, suppressed: false, mean: 2, median: 2 },
      ],
      warnings: [],
    });

    await compareAndWait();

    await waitFor(() => expect(screen.getByText('Mann-Whitney U')).toBeInTheDocument());
    expect(screen.queryByText('q (BH)')).not.toBeInTheDocument();
  });

  it('privacidad: si la prueba viene suprimida, no revela método/estadístico/p/efecto', async () => {
    compareConstructGroups.mockResolvedValue({
      method: null,
      statistic: null,
      p_value: null,
      effect_size: null,
      effect_label: null,
      suppressed: true,
      groups: [
        { code: 'A', n: 3, suppressed: true, mean: null, median: null },
        { code: 'B', n: 40, suppressed: false, mean: 55.4, median: 54.0 },
      ],
      warnings: ['Se suprimió la comparación porque al menos un grupo tiene menos de 5 casos.'],
    });

    await compareAndWait();

    expect(await screen.findByText(/Prueba suprimida/)).toBeInTheDocument();
    expect(screen.queryByText('Mann-Whitney U')).not.toBeInTheDocument();
    expect(screen.queryByText('Estadístico')).not.toBeInTheDocument();
  });
});
