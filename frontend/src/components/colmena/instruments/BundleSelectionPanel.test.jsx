import { describe, expect, it } from 'vitest';

import {
  isAcceptedInstrumentStudy,
  officialInstrumentVersionLabel,
} from './BundleSelectionPanel.jsx';

describe('BundleSelectionPanel official CENSOPAS versions', () => {
  it('labels only the accepted official short and medium versions', () => {
    expect(officialInstrumentVersionLabel({
      instrument_name: 'CENSOPAS-COPSOQ',
      instrument_version_code: 'SHORT-OFICIAL',
    })).toBe('Versión corta oficial');
    expect(officialInstrumentVersionLabel({
      instrument_name: 'CENSOPAS-COPSOQ',
      instrument_version_code: 'MEDIUM-OFICIAL',
    })).toBe('Versión media oficial');
  });

  it('rejects invented or demo CENSOPAS variants from the battery', () => {
    expect(isAcceptedInstrumentStudy({
      instrument_name: 'CENSOPAS-COPSOQ',
      instrument_version_code: 'PREMIUM',
    })).toBe(false);
    expect(isAcceptedInstrumentStudy({
      instrument_name: 'CENSOPAS-COPSOQ',
      instrument_version_code: 'SHORT-DEMO',
    })).toBe(false);
  });
});
