import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithQueryClient } from '../../../test-utils/renderWithQueryClient.jsx';
import { listInstrumentVersions } from '../../../api/instruments.js';
import { listStudies, createStudy } from '../../../api/studies.js';
import {
  listSurveys,
  createSurveyFromInstrument,
} from '../../../api/surveys.js';
import CatalogCampaignModal from './CatalogCampaignModal.jsx';
vi.mock('../../../auth/AuthContext.jsx', () => ({
  useAuth: () => ({ user: { id: 7 } }),
}));
vi.mock('../../../api/instruments.js', () => ({
  listInstrumentVersions: vi.fn(),
}));
vi.mock('../../../api/studies.js', () => ({
  listStudies: vi.fn(),
  createStudy: vi.fn(),
}));
vi.mock('../../../api/surveys.js', () => ({
  listSurveys: vi.fn(),
  createSurveyFromInstrument: vi.fn(),
}));
beforeEach(() => {
  vi.clearAllMocks();
  listInstrumentVersions.mockResolvedValue([
    { id: 44, version_code: 'APPROVED-1', status: 'ACTIVE' },
    { id: 45, version_code: 'DRAFT-2', status: 'DRAFT' },
  ]);
  listStudies.mockResolvedValue({ items: [] });
  listSurveys.mockResolvedValue({ items: [] });
  createSurveyFromInstrument.mockResolvedValue({ id: 80 });
  createStudy.mockResolvedValue({ id: 90 });
});
async function choose(onCreated = vi.fn()) {
  renderWithQueryClient(
    <CatalogCampaignModal
      instrument={{ id: 4, name: 'ROSA' }}
      projects={[{ id: 9, name: 'Synthetic company' }]}
      onClose={vi.fn()}
      onCreated={onCreated}
    />,
  );
  await screen.findByText('APPROVED-1');
  fireEvent.change(screen.getByLabelText('Empresa'), {
    target: { value: '9' },
  });
  fireEvent.change(screen.getByLabelText('Versión publicada'), {
    target: { value: '44' },
  });
  fireEvent.click(screen.getByText('Continuar con esta campaña'));
  return onCreated;
}
it('uses the selected published version and selected company without substituting CENSOPAS', async () => {
  const callback = await choose();
  await waitFor(() =>
    expect(callback).toHaveBeenCalledWith({ projectId: '9', studyId: 90 }),
  );
  expect(createSurveyFromInstrument).toHaveBeenCalledWith('9', {
    created_by_user_id: 7,
    instrument_version_id: 44,
    name: 'ROSA',
    survey_type: 'INSTRUMENT',
  });
  expect(createStudy).toHaveBeenCalledWith(
    '9',
    expect.objectContaining({ survey_id: 80, study_type: 'RESEARCH' }),
  );
  expect(screen.queryByText('DRAFT-2')).not.toBeInTheDocument();
});
it('reuses the matching campaign rather than creating duplicate surveys or studies', async () => {
  listStudies.mockResolvedValue({
    items: [{ id: 91, instrument_version_id: 44, status: 'OPEN' }],
  });
  const callback = await choose();
  await waitFor(() =>
    expect(callback).toHaveBeenCalledWith({ projectId: '9', studyId: 91 }),
  );
  expect(createSurveyFromInstrument).not.toHaveBeenCalled();
  expect(createStudy).not.toHaveBeenCalled();
});
