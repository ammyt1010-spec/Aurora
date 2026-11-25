import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { apiRequest } from '../../../api/client.js';
import { getPaymentInstructions, getEvaluationAccess } from '../../../api/billing.js';
import { renderWithQueryClient } from '../../../test-utils/renderWithQueryClient.jsx';
import InstrumentCartModal from './InstrumentCartModal.jsx';

vi.mock('../../../api/client.js', () => ({ apiRequest: vi.fn() }));
vi.mock('../../../api/billing.js', () => ({
  getPaymentInstructions: vi.fn(), getEvaluationAccess: vi.fn(),
}));

const INSTRUMENTS = [
  {
    instrument_version_id: 3,
    version_kind: 'SHORT',
    title: 'CENSOPAS-COPSOQ, versión corta',
  },
  {
    instrument_version_id: 4,
    version_kind: 'MEDIUM',
    title: 'CENSOPAS-COPSOQ, versión media',
  },
];

describe('InstrumentCartModal', () => {
  beforeEach(() => {
    apiRequest.mockReset();
    getPaymentInstructions.mockResolvedValue({
      bank_name: 'Banco por definir', account_holder: 'AURORA (datos provisionales)',
      account_number: 'PENDIENTE_DE_CONFIGURAR', cci: 'PENDIENTE_DE_CONFIGURAR',
      provisional: true, notice: 'Datos provisionales: no realices una transferencia.',
    });
    apiRequest
      .mockResolvedValueOnce({ project_id: 101, study_id: 31, survey_url: '/encuesta/corta-demo' })
      .mockResolvedValueOnce({ project_id: 102, study_id: 32, survey_url: '/encuesta/media-demo' });
  });

  const renderModal = (props) => renderWithQueryClient(
    <MemoryRouter><InstrumentCartModal instruments={INSTRUMENTS} onClose={vi.fn()} {...props} /></MemoryRouter>,
  );

  it('does not render until the user opens it', () => {
    renderModal({ isOpen: false });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('creates one public link and QR per selected official instrument', async () => {
    renderModal({ isOpen: true });
    fireEvent.change(screen.getByLabelText('Razón social'), { target: { value: 'Empresa Aurora SAC' } });
    fireEvent.change(screen.getByLabelText('RUC'), { target: { value: '20123456789' } });
    fireEvent.change(screen.getByLabelText('Cantidad de trabajadores'), { target: { value: '250' } });
    fireEvent.click(screen.getByRole('button', { name: 'Generar enlace y QR' }));

    await waitFor(() => expect(apiRequest).toHaveBeenCalledTimes(2));
    expect(apiRequest).toHaveBeenNthCalledWith(1, '/quick-eval', expect.objectContaining({
      method: 'POST',
      body: expect.objectContaining({ instrument_version: 'SHORT', population_invited: 250 }),
    }));
    expect(apiRequest).toHaveBeenNthCalledWith(2, '/quick-eval', expect.objectContaining({
      method: 'POST',
      body: expect.objectContaining({ instrument_version: 'MEDIUM', population_invited: 250 }),
    }));
    expect(await screen.findByText('Enlaces listos para compartir')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /corta-demo/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /media-demo/ })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Ver respuestas →' })).toHaveLength(2);
  });

  it('continues to the responses of the selected instrument', async () => {
    renderWithQueryClient(<MemoryRouter initialEntries={['/colmena']}>
      <Routes>
        <Route path="/colmena" element={<InstrumentCartModal instruments={[INSTRUMENTS[0]]} isOpen onClose={vi.fn()} />} />
        <Route path="/colmena/telemetry" element={<p>Seguimiento de respuestas</p>} />
      </Routes>
    </MemoryRouter>);
    fireEvent.change(screen.getByLabelText('Razón social'), { target: { value: 'Empresa Aurora SAC' } });
    fireEvent.change(screen.getByLabelText('RUC'), { target: { value: '20123456789' } });
    fireEvent.click(screen.getByRole('button', { name: 'Generar enlace y QR' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Ver respuestas →' }));
    expect(screen.getByText('Seguimiento de respuestas')).toBeInTheDocument();
    expect(localStorage.getItem('colmena.activeProjectId')).toBe('101');
    expect(localStorage.getItem('colmena.activeStudy.101')).toBe('31');
  });

  it('does not expose a QR before payment and shows provisional transfer details', async () => {
    apiRequest.mockReset();
    apiRequest.mockResolvedValueOnce({
      project_id: 103, study_id: 33, survey_url: null, payment_required: true,
      order_id: 9, amount: '600.00', pricing_mode: 'FIXED', free_remaining: 0,
    });
    getEvaluationAccess.mockResolvedValue({
      study_id: 33, status: 'ACTIVE', survey_url: '/encuesta/pagada', order_status: 'PAID',
    });
    renderWithQueryClient(<MemoryRouter><InstrumentCartModal instruments={[INSTRUMENTS[0]]} isOpen onClose={vi.fn()}
      trialRemaining={0} tariffs={[{ method_code: 'CENSOPAS_CORTA', min_workers: 101, max_workers: 300, price: '600.00', pricing_mode: 'FIXED', active: true }]} /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('Razón social'), { target: { value: 'Empresa Aurora SAC' } });
    fireEvent.change(screen.getByLabelText('RUC'), { target: { value: '20123456789' } });
    fireEvent.change(screen.getByLabelText('Cantidad de trabajadores'), { target: { value: '250' } });
    fireEvent.click(screen.getByRole('button', { name: 'Generar enlace y QR' }));
    expect(await screen.findByText('Pendiente de pago · orden #9')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /encuesta/ })).not.toBeInTheDocument();
    expect(await screen.findByText(/no realices una transferencia/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Comprobar activación' }));
    expect(await screen.findByRole('link', { name: /encuesta\/pagada/ })).toBeInTheDocument();
  });

  it('updates a manual quote without showing a link before payment', async () => {
    apiRequest.mockReset();
    apiRequest.mockResolvedValueOnce({
      project_id: 104, study_id: 34, survey_url: null, payment_required: true,
      order_id: 10, amount: null, pricing_mode: 'QUOTE', free_remaining: 0,
    });
    getEvaluationAccess.mockResolvedValue({
      study_id: 34, status: 'PENDING_PAYMENT', survey_url: null,
      order_status: 'PENDING_PAYMENT', amount: '1200.00',
    });
    renderWithQueryClient(<MemoryRouter><InstrumentCartModal instruments={[INSTRUMENTS[0]]} isOpen onClose={vi.fn()}
      trialRemaining={0} tariffs={[]} /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('Razón social'), { target: { value: 'Empresa Aurora SAC' } });
    fireEvent.change(screen.getByLabelText('RUC'), { target: { value: '20123456789' } });
    fireEvent.click(screen.getByRole('button', { name: 'Generar enlace y QR' }));
    expect((await screen.findAllByText(/Cotización pendiente: no transfieras/)).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Comprobar activación' }));
    expect(await screen.findByText('Importe: S/ 1200.00')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /encuesta/ })).not.toBeInTheDocument();
  });
});
