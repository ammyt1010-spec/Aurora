import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { renderWithQueryClient } from '../../../test-utils/renderWithQueryClient.jsx';
import { getProject } from '../../../api/projects.js';
import { listOrganizations } from '../../../api/organizations.js';
import { getStudy, listStudies } from '../../../api/studies.js';
import { createReportPreview } from '../../../api/reports.js';
import { fetchProtectedBlob } from '../../../api/protectedFiles.js';
import ProjectReportsPage from './ProjectReportsPage.jsx';

vi.mock('../../../api/projects.js', () => ({ getProject: vi.fn() }));
vi.mock('../../../api/organizations.js', () => ({ listOrganizations: vi.fn() }));
vi.mock('../../../api/studies.js', () => ({ getStudy: vi.fn(), listStudies: vi.fn() }));
vi.mock('../../../api/reports.js', () => ({
  createReportPreview: vi.fn(),
  getReportPreviewPdfUrl: (id) => `/reports/${id}/preview.pdf`,
}));
vi.mock('../../../api/protectedFiles.js', () => ({
  fetchProtectedBlob: vi.fn(),
  downloadProtectedFile: vi.fn(),
}));
vi.mock('../../../components/colmena/PdfCanvasViewer.jsx', () => ({
  default: () => <div>Visor de páginas activo</div>,
}));

describe('informe empresarial simple', () => {
  beforeEach(() => {
    localStorage.clear();
    getProject.mockResolvedValue({ id: 23, organization_id: 1, metadata: { censopas_study_id: 26 } });
    listOrganizations.mockResolvedValue([{ organization: { id: 1, legal_name: 'Empresa Demo', tax_id: '20123456789' } }]);
    listStudies.mockResolvedValue({ items: [{
      id: 26, name: 'Aplicación minera', status: 'OPEN', instrument_name: 'CENSOPAS-COPSOQ',
      instrument_version_code: 'MEDIUM-OFICIAL',
    }] });
    getStudy.mockResolvedValue({ id: 26, instrument_name: 'CENSOPAS-COPSOQ', instrument_version_code: 'MEDIUM-OFICIAL' });
    createReportPreview.mockResolvedValue({ preview_id: 48, is_sample: true, pages: 14 });
    fetchProtectedBlob.mockResolvedValue(new Blob(['%PDF-1.4'], { type: 'application/pdf' }));
    URL.createObjectURL = vi.fn(() => 'blob:aurora-demo');
    URL.revokeObjectURL = vi.fn();
  });

  it('muestra solo el flujo del PDF y genera una muestra completa', async () => {
    renderWithQueryClient(<MemoryRouter initialEntries={['/colmena/project/23/reports']}>
      <Routes><Route path="/colmena/project/:projectId/reports" element={<ProjectReportsPage />} /></Routes>
    </MemoryRouter>);

    const generate = await screen.findByRole('button', { name: 'Generar informe PDF' });
    expect(screen.queryByText(/Emisión definitiva/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Informes anteriores/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Opciones técnicas/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Resumen metodológico/)).not.toBeInTheDocument();

    fireEvent.click(generate);
    await waitFor(() => expect(createReportPreview).toHaveBeenCalledWith(26, expect.objectContaining({
      report_mode: 'SAMPLE', is_sample_preview: true, output_format: 'PDF', sections: [],
    })));
    expect(await screen.findByText('Páginas renderizadas: 14')).toBeInTheDocument();
    expect(await screen.findByText('Visor de páginas activo')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Descargar PDF de prueba' })).toBeEnabled();
  });
});
