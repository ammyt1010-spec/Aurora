import { describe, expect, it } from 'vitest';
import {
  DEFAULT_WIDGETS, getDimensions, percent, readWidgetPreferences,
  reorderWidget, safeSegmentRows, safeUnitChoices,
} from './dashboardModel.js';

const publishable = {
  construct_code: 'D1', construct_type: 'DIMENSION', construct_name: 'Carga laboral',
  suppressed: false, favorable_pct: 24, intermediate_pct: 31,
  unfavorable_pct: 45, unit_id: 10, unit_name: 'Operaciones', priority_rank: 2,
};
const privateRow = { ...publishable, construct_code: 'D2', construct_name: 'Privado', unit_id: 20, unit_name: 'Equipo mínimo', suppressed: true, unfavorable_pct: 91 };

describe('AURORA BI executive model', () => {
  it('never exposes suppressed dimensions or units', () => {
    expect(getDimensions([privateRow, publishable]).map((x) => x.construct_code)).toEqual(['D1']);
    expect(safeUnitChoices([privateRow, publishable])).toEqual([{ id: 10, name: 'Operaciones' }]);
    expect(safeSegmentRows([publishable, privateRow]).map((x) => x.unit_id)).toEqual([10]);
  });

  it('does not manufacture favorable values from missing risk bands', () => {
    expect(getDimensions([{ ...publishable, intermediate_pct: null }])).toEqual([]);
    expect(percent(null)).toBeNull();
    expect(percent(170)).toBe(100);
    expect(percent(-20)).toBe(0);
  });

  it('filters segments and dimensions without changing the statistical bands', () => {
    const additional = { ...publishable, unit_id: 11, unit_name: 'Planta', unfavorable_pct: 32 };
    const output = safeSegmentRows([publishable, additional], '10', 'D1');
    expect(output).toHaveLength(1);
    expect(output[0].unfavorable_pct).toBe(45);
    expect(safeSegmentRows([publishable], '99')).toEqual([]);
  });

  it('keeps generic scores distinct from CENSOPAS risk', () => {
    const generic = { construct_code: 'C1', construct_type: 'DIMENSION', construct_name: 'Clima', suppressed: false, mean_score: 62 };
    expect(getDimensions([generic], { isCensopas: false })).toHaveLength(1);
    expect(getDimensions([generic], { isCensopas: true })).toHaveLength(0);
  });

  it('reorders widgets and refuses disabled empty preferences', () => {
    expect(reorderWidget(['summary', 'ranking'], 'ranking', -1)).toEqual(['ranking', 'summary']);
    localStorage.setItem('aurora-test-pref', JSON.stringify(['invalid', 'invalid']));
    expect(readWidgetPreferences('aurora-test-pref')).toEqual(DEFAULT_WIDGETS);
    localStorage.removeItem('aurora-test-pref');
  });
});
