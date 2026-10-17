import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./client.js', () => ({
  API_BASE_URL: '/api/v1',
  apiRequest: vi.fn(),
}));

import { apiRequest } from './client.js';
import {
  getExecutiveDashboard,
  getOrganizationReportHistory,
  listReportTemplates,
} from './reports.js';

describe('enterprise reporting API routes', () => {
  beforeEach(() => vi.clearAllMocks());

  it('loads report templates and securely scopes the executive dashboard', () => {
    listReportTemplates();
    expect(apiRequest).toHaveBeenCalledWith('/report-templates');
    getExecutiveDashboard(15);
    expect(apiRequest).toHaveBeenCalledWith('/studies/15/reports/executive-dashboard');
  });

  it('restricts report history URLs to the selected organization', () => {
    getOrganizationReportHistory(7, { studyId: 15, discipline: 'CLIMA' });
    expect(apiRequest).toHaveBeenCalledWith(
      '/organizations/7/reports/history?study_id=15&discipline=CLIMA',
    );
  });
});
