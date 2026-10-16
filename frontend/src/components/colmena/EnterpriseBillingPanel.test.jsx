import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, screen } from '@testing-library/react';

import { renderWithQueryClient } from '../../test-utils/renderWithQueryClient.jsx';
import { listOrganizations } from '../../api/organizations.js';
import { getOrganizationBillingSummary } from '../../api/billing.js';
import { EnterpriseBillingPanel } from './EnterpriseBillingPanel.jsx';

vi.mock('../../api/organizations.js', () => ({ listOrganizations: vi.fn() }));
vi.mock('../../api/billing.js', () => ({
  getOrganizationBillingSummary: vi.fn(),
  BILLING_METHODS: [
    { code: 'SUSESO_ISTAS21_BREVE', label: 'SUSESO / ISTAS21 breve' },
    { code: 'CENSOPAS_CORTA', label: 'CENSOPAS COPSOQ corta' },
  ],
}));

const companyA = { organization: { id: 10, name: 'Empresa Alfa' }, role_code: 'OWNER' };
const companyB = { organization: { id: 20, name: 'Empresa Beta' }, role_code: 'ADMIN' };

beforeEach(() => {
  vi.clearAllMocks();
  listOrganizations.mockResolvedValue([companyA]);
  getOrganizationBillingSummary.mockResolvedValue({
    organization_id: 10,
    organization_name: 'Empresa Alfa',
    total_orders: 2,
    available_licenses: 1,
    consumed_licenses: 1,
    pending_payment: 0,
    awaiting_quote: 0,
    orders: [
      {
        id: 101,
        study_id: 5,
        organization_id: 10,
        workers: 45,
        headcount_source: 'PLANILLA_OFICIAL_EMPRESA',
        method_code: 'SUSESO_ISTAS21_BREVE',
        pricing_mode: 'FIXED',
        amount: '120.00',
        currency: 'PEN',
        status: 'PAID',
        payment_reference: 'TRANSF-4421',
        created_at: '2026-10-15T12:00:00Z',
        paid_at: '2026-10-15T12:30:00Z',
      },
      {
        id: 102,
        study_id: 6,
        organization_id: 10,
        workers: 80,
        headcount_source: 'ESTUDIO_DECLARADO',
        method_code: 'CENSOPAS_CORTA',
        pricing_mode: 'FIXED',
        amount: '200.00',
        currency: 'PEN',
        status: 'CONSUMED',
        payment_reference: 'TRANSF-4422',
        created_at: '2026-10-14T10:00:00Z',
        paid_at: '2026-10-14T10:15:00Z',
      },
    ],
  });
});

afterEach(cleanup);

describe('EnterpriseBillingPanel', () => {
  it('renders summary counters and license order history for managed company', async () => {
    renderWithQueryClient(<EnterpriseBillingPanel />);

    expect(await screen.findByText('Integridad y Licencias Comerciales')).toBeInTheDocument();
    expect(await screen.findByText('Disponibles')).toBeInTheDocument();
    expect(screen.getByText('Emitidos')).toBeInTheDocument();
    expect(screen.getByText('#101')).toBeInTheDocument();
    expect(screen.getByText('#102')).toBeInTheDocument();
    expect(screen.getByText('SUSESO / ISTAS21 breve')).toBeInTheDocument();
    expect(screen.getByText('CENSOPAS COPSOQ corta')).toBeInTheDocument();
    expect(screen.getByText('Disponible')).toBeInTheDocument();
    expect(screen.getByText('Consumida')).toBeInTheDocument();
    expect(screen.getByText('TRANSF-4421')).toBeInTheDocument();
    expect(screen.getByText('PLANILLA_OFICIAL_EMPRESA')).toBeInTheDocument();
  });

  it('hides billing panel when user has only collaborator role', async () => {
    listOrganizations.mockResolvedValue([{ ...companyA, role_code: 'COLLABORATOR' }]);
    renderWithQueryClient(<EnterpriseBillingPanel />);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(screen.queryByText('Integridad y Licencias Comerciales')).not.toBeInTheDocument();
    expect(getOrganizationBillingSummary).not.toHaveBeenCalled();
  });

  it('allows switching organizations when multiple managed companies exist', async () => {
    listOrganizations.mockResolvedValue([companyA, companyB]);
    renderWithQueryClient(<EnterpriseBillingPanel />);

    const select = await screen.findByLabelText('Seleccionar empresa para consultar licencias');
    expect(select).toBeInTheDocument();

    fireEvent.change(select, { target: { value: '20' } });
    expect(getOrganizationBillingSummary).toHaveBeenCalledWith(20);
  });
});
