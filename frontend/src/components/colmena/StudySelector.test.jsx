import { describe, expect, it } from 'vitest';

import { reportInstrumentLabel } from './StudySelector.jsx';

describe('reportInstrumentLabel', () => {
  it('identifica la versión corta del instrumento seleccionado', () => {
    expect(reportInstrumentLabel({
      instrument_name: 'CENSOPAS-COPSOQ',
      instrument_version_code: 'CENSOPAS-SHORT-V2',
    })).toBe('CENSOPAS-COPSOQ · versión corta');
  });

  it('identifica la versión media sin mezclarla con la corta', () => {
    expect(reportInstrumentLabel({
      instrument_name: 'CENSOPAS-COPSOQ',
      instrument_version_code: 'CENSOPAS-MEDIUM-V2',
    })).toBe('CENSOPAS-COPSOQ · versión media');
  });

  it('conserva el código de otros instrumentos futuros', () => {
    expect(reportInstrumentLabel({
      instrument_name: 'Instrumento ocupacional',
      instrument_version_code: 'V3',
    })).toBe('Instrumento ocupacional · V3');
  });
});
