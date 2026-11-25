import { describe, expect, it } from 'vitest';
import { dimensionComparisons, filteredDimensionRows, segmentOptions } from './segmentDashboardModel.js';

const base = [
  { construct_code: 'D1', construct_name: 'Exigencias', construct_type: 'DIMENSION', unfavorable_pct: 20, favorable_pct: 30, intermediate_pct: 50 },
  { construct_code: 'D2', construct_name: 'Control', construct_type: 'DIMENSION', unfavorable_pct: 10, favorable_pct: 40, intermediate_pct: 50 },
];
const result = (code, group, unfavorable, suppressed = false) => ({
  construct_code: code, construct_name: code, construct_type: 'DIMENSION', group_value: group,
  n_valid: suppressed ? 3 : 12, unfavorable_pct: suppressed ? null : unfavorable,
  favorable_pct: suppressed ? null : 40, intermediate_pct: suppressed ? null : 60 - unfavorable,
  suppressed,
});

describe('segmentación de telemetría', () => {
  it('recalcula la vista del segmento sin reutilizar el agregado empresarial para celdas ocultas', () => {
    const rows = [result('D1', 'Mujer', 35), result('D2', 'Mujer', 5, true)];
    expect(segmentOptions(rows)).toEqual([{ id: 'Mujer', label: 'Mujer' }]);
    const filtered = filteredDimensionRows(base, rows, 'Mujer');
    expect(filtered[0].unfavorable_pct).toBe(35);
    expect(filtered[1].suppressed).toBe(true);
    expect(filtered[1].unfavorable_pct).toBeNull();
    expect(filtered[1].n_valid).toBeNull();
  });

  it('ordena comparaciones publicables sin mostrar grupos suprimidos', () => {
    const rows = [result('D1', 'Mujer', 35), result('D1', 'Hombre', 18), result('D1', 'Sin dato', 0, true)];
    expect(dimensionComparisons(rows, 'D1').map((row) => row.label)).toEqual(['Mujer', 'Hombre']);
    expect(filteredDimensionRows(base, rows, 'ALL')).toBe(base);
  });
});
