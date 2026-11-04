import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { apiRequest } from '../../../api/client.js';
import { renderWithQueryClient } from '../../../test-utils/renderWithQueryClient.jsx';
import InstrumentCartModal from './InstrumentCartModal.jsx';

vi.mock('../../../api/client.js', () => ({ apiRequest: vi.fn() }));

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
});
