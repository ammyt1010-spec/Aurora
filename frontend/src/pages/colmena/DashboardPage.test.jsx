import { describe, expect, it, vi } from 'vitest';
import { availableInstrumentCards } from './DashboardPage.jsx';

describe('AURORA instrument catalog', () => {
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
