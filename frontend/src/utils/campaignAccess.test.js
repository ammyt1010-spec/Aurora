import { describe, expect, it } from 'vitest';

import { canDistributeSurvey, selectCampaign } from './campaignAccess.js';

describe('enterprise campaign distribution guard', () => {
  it('blocks missing, draft, closed and archived campaigns', () => {
    expect(canDistributeSurvey(null)).toBe(false);
    for (const status of ['DRAFT', 'CLOSED', 'ARCHIVED']) {
      expect(canDistributeSurvey({ status })).toBe(false);
    }
  });

  it('accepts open campaigns within the stated response window', () => {
    const now = Date.parse('2026-10-17T12:00:00Z');
    expect(canDistributeSurvey({ status: 'OPEN' }, now)).toBe(true);
    expect(canDistributeSurvey({ status: 'OPEN', end_at: '2026-10-17T12:00:01Z' }, now)).toBe(true);
    expect(canDistributeSurvey({ status: 'OPEN', end_at: '2026-10-17T12:00:00Z' }, now)).toBe(false);
    expect(canDistributeSurvey({ status: 'OPEN', end_at: 'invalid' }, now)).toBe(false);
  });

  it('respects a selected campaign and otherwise prefers an open campaign', () => {
    const campaigns = [
      { id: 1, status: 'CLOSED' },
      { id: 2, status: 'OPEN' },
      { id: 3, status: 'DRAFT' },
    ];
    expect(selectCampaign(campaigns, '3').id).toBe(3);
    expect(selectCampaign(campaigns, null).id).toBe(2);
    expect(selectCampaign([], '2')).toBe(null);
  });
});
