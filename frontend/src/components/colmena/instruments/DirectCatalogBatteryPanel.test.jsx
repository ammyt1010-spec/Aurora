import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, expect, it, vi } from 'vitest';
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { renderWithQueryClient } from '../../../test-utils/renderWithQueryClient.jsx';
import { fetchCurrentUser } from '../../../api/auth.js';
import {
  listInstruments,
  listInstrumentVersions,
} from '../../../api/instruments.js';
import { listStudies, createStudy, openStudy } from '../../../api/studies.js';
import {
  listSurveys,
  createSurveyFromInstrument,
} from '../../../api/surveys.js';
import { createEvaluationBundle } from '../../../api/evaluationBundles.js';
import DirectCatalogBatteryPanel from './DirectCatalogBatteryPanel.jsx';
vi.mock('../../../api/auth.js', () => ({ fetchCurrentUser: vi.fn() }));
vi.mock('../../../api/instruments.js', () => ({
  listInstruments: vi.fn(),
  listInstrumentVersions: vi.fn(),
}));
vi.mock('../../../api/studies.js', () => ({
  listStudies: vi.fn(),
  createStudy: vi.fn(),
  openStudy: vi.fn(),
}));
vi.mock('../../../api/surveys.js', () => ({
  listSurveys: vi.fn(),
  createSurveyFromInstrument: vi.fn(),
}));
vi.mock('../../../api/evaluationBundles.js', () => ({
  createEvaluationBundle: vi.fn(),
}));
beforeEach(() => {
  vi.clearAllMocks();
  fetchCurrentUser.mockResolvedValue({ id: 7 });
  listInstruments.mockResolvedValue({
    items: [
      { id: 1, name: 'ROSA', status: 'AUTHORIZED' },
      { id: 2, name: 'Burnout', status: 'ACTIVE' },
      { id: 3, name: 'Unapproved', status: 'DRAFT' },
    ],
    total: 3,
  });
  listInstrumentVersions.mockImplementation((id) =>
    Promise.resolve([
      { id: id * 10, version_code: 'V' + id, status: 'ACTIVE' },
    ]),
  );
  listStudies.mockResolvedValue({ items: [], total: 0 });
  listSurveys.mockResolvedValue({ items: [], total: 0 });
  createSurveyFromInstrument.mockImplementation((project, payload) =>
    Promise.resolve({
      id: payload.instrument_version_id + 1,
      instrument_version_id: payload.instrument_version_id,
    }),
  );
  createStudy.mockImplementation((project, payload) =>
    Promise.resolve({ id: payload.survey_id + 1, status: 'DRAFT' }),
  );
  openStudy.mockImplementation((id) =>
    Promise.resolve({ id, status: 'OPEN', public_id: 'study-' + id }),
  );
  createEvaluationBundle.mockResolvedValue({ public_id: 'ordered-battery' });
});
async function renderPanel() {
  renderWithQueryClient(
    <DirectCatalogBatteryPanel
      projects={[{ id: 9, name: 'Synthetic company', organization_id: 99 }]}
    />,
  );
  return await screen.findAllByRole('checkbox');
}
it('generates one real instrument URL and QR directly from a catalog checkbox', async () => {
  const boxes = await renderPanel();
  expect(boxes).toHaveLength(2);
  fireEvent.click(boxes[0]);
  fireEvent.click(screen.getByText('Generar enlace y QR'));
  expect(await screen.findByRole('link')).toHaveAttribute(
    'href',
    window.location.origin + '/encuesta/study-12',
  );
  expect(
    screen.getByLabelText('QR del catálogo seleccionado'),
  ).toBeInTheDocument();
  expect(createSurveyFromInstrument).toHaveBeenCalledWith(
    '9',
    expect.objectContaining({
      instrument_version_id: 10,
      created_by_user_id: 7,
    }),
  );
  expect(openStudy).toHaveBeenCalledWith(12);
  expect(createEvaluationBundle).not.toHaveBeenCalled();
});
it('creates two selected catalog instruments in click order and one shared QR', async () => {
  const boxes = await renderPanel();
  fireEvent.click(boxes[1]);
  fireEvent.click(boxes[0]);
  fireEvent.click(screen.getByText('Generar enlace y QR'));
  expect(await screen.findByRole('link')).toHaveAttribute(
    'href',
    window.location.origin + '/bateria/ordered-battery',
  );
  expect(createEvaluationBundle).toHaveBeenCalledWith('9', {
    label: 'Batería de instrumentos autorizados',
    study_ids: [22, 12],
  });
  expect(openStudy.mock.calls).toEqual([[22], [12]]);
});
it('retries a mixed-version battery by reusing prepared campaigns without duplicates', async () => {
  const surveys = [];
  const studies = [];
  listStudies.mockImplementation(() =>
    Promise.resolve({ items: [...studies], total: studies.length }),
  );
  listSurveys.mockImplementation(() =>
    Promise.resolve({ items: [...surveys], total: surveys.length }),
  );
  createSurveyFromInstrument.mockImplementation((project, payload) => {
    const survey = {
      id: payload.instrument_version_id + 1,
      instrument_version_id: payload.instrument_version_id,
    };
    surveys.push(survey);
    return Promise.resolve(survey);
  });
  createStudy
    .mockImplementationOnce((project, payload) => {
      const study = {
        id: payload.survey_id + 1,
        survey_id: payload.survey_id,
        instrument_version_id: payload.survey_id - 1,
        status: 'DRAFT',
      };
      studies.push(study);
      return Promise.resolve(study);
    })
    .mockRejectedValueOnce(new Error('temporary preparation failure'))
    .mockImplementationOnce((project, payload) => {
      const study = {
        id: payload.survey_id + 1,
        survey_id: payload.survey_id,
        instrument_version_id: payload.survey_id - 1,
        status: 'DRAFT',
      };
      studies.push(study);
      return Promise.resolve(study);
    });
  openStudy.mockImplementation((id) => {
    const study = studies.find((item) => item.id === id);
    if (study) {
      study.status = 'OPEN';
      study.public_id = 'study-' + id;
    }
    return Promise.resolve({ id, status: 'OPEN', public_id: 'study-' + id });
  });

  const boxes = await renderPanel();
  fireEvent.click(boxes[0]);
  fireEvent.click(boxes[1]);
  fireEvent.click(screen.getByText('Generar enlace y QR'));
  expect(await screen.findByText(/temporary preparation failure/)).toBeInTheDocument();
  expect(createEvaluationBundle).not.toHaveBeenCalled();

  fireEvent.click(screen.getByText('Generar enlace y QR'));
  expect(await screen.findByRole('link')).toHaveAttribute(
    'href',
    window.location.origin + '/bateria/ordered-battery',
  );
  expect(createStudy).toHaveBeenCalledTimes(3);
  expect(studies.map((study) => study.instrument_version_id)).toEqual([10, 20]);
  expect(createEvaluationBundle).toHaveBeenCalledWith('9', {
    label: 'Batería de instrumentos autorizados',
    study_ids: [12, 22],
  });
});
it('shows the exact blocked method and no fake URL after server readiness refusal', async () => {
  openStudy.mockImplementation((id) =>
    id === 22
      ? Promise.reject(new Error('Baremo no configurado'))
      : Promise.resolve({ id, status: 'OPEN', public_id: 'study-' + id }),
  );
  const boxes = await renderPanel();
  fireEvent.click(boxes[0]);
  fireEvent.click(boxes[1]);
  fireEvent.click(screen.getByText('Generar enlace y QR'));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Burnout · V2: Baremo no configurado',
  );
  expect(screen.getByRole('alert')).toHaveTextContent(
    'campañas ya preparadas se conservan',
  );
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  expect(createEvaluationBundle).not.toHaveBeenCalled();
});
it('reuses matching public campaigns without opening or creating duplicates', async () => {
  listStudies.mockResolvedValue({
    items: [
      {
        id: 80,
        instrument_version_id: 10,
        status: 'OPEN',
        public_id: 'existing',
      },
    ],
    total: 1,
  });
  const boxes = await renderPanel();
  fireEvent.click(boxes[0]);
  fireEvent.click(screen.getByText('Generar enlace y QR'));
  await waitFor(() =>
    expect(screen.getByRole('link')).toHaveAttribute(
      'href',
      window.location.origin + '/encuesta/existing',
    ),
  );
  expect(createStudy).not.toHaveBeenCalled();
  expect(createSurveyFromInstrument).not.toHaveBeenCalled();
  expect(openStudy).not.toHaveBeenCalled();
});

it('finds existing campaigns beyond the first page without duplicating them', async () => {
  listStudies.mockImplementation((project, { page }) =>
    Promise.resolve(
      page === 1
        ? {
            items: [{ id: 5, instrument_version_id: 999, status: 'OPEN' }],
            total: 2,
          }
        : {
            items: [
              {
                id: 80,
                instrument_version_id: 10,
                status: 'OPEN',
                public_id: 'later-page',
              },
            ],
            total: 2,
          },
    ),
  );
  const boxes = await renderPanel();
  fireEvent.click(boxes[0]);
  fireEvent.click(screen.getByText('Generar enlace y QR'));
  expect(await screen.findByRole('link')).toHaveAttribute(
    'href',
    window.location.origin + '/encuesta/later-page',
  );
  expect(listStudies).toHaveBeenCalledWith('9', { page: 2, pageSize: 100 });
  expect(createStudy).not.toHaveBeenCalled();
});
it('does not bypass invitations on an existing matching campaign', async () => {
  listStudies.mockResolvedValue({
    items: [
      {
        id: 80,
        instrument_version_id: 10,
        status: 'OPEN',
        public_id: 'private',
        requires_invitation: true,
      },
    ],
    total: 1,
  });
  const boxes = await renderPanel();
  fireEvent.click(boxes[0]);
  fireEvent.click(screen.getByText('Generar enlace y QR'));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'requiere invitaciones individuales',
  );
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  expect(createStudy).not.toHaveBeenCalled();
});
it('keeps CENSOPAS campaign type so server barem mismatch checks cannot be bypassed', async () => {
  listInstruments.mockResolvedValue({
    items: [
      {
        id: 1,
        name: 'CENSOPAS',
        code: 'CENSOPAS_COPSOQ',
        status: 'ACTIVE',
        is_system: true,
      },
    ],
    total: 1,
  });
  const boxes = await renderPanel();
  fireEvent.click(boxes[0]);
  fireEvent.click(screen.getByText('Generar enlace y QR'));
  await screen.findByRole('link');
  expect(createStudy).toHaveBeenCalledWith(
    '9',
    expect.objectContaining({ study_type: 'CENSO' }),
  );
});

it('revalidates revoked selected versions before any campaign or link mutation', async () => {
  const boxes = await renderPanel();
  fireEvent.click(boxes[0]);
  listInstrumentVersions.mockResolvedValue([
    { id: 10, version_code: 'V1', status: 'DRAFT' },
  ]);
  fireEvent.click(screen.getByText('Generar enlace y QR'));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'versión ya no está autorizada',
  );
  expect(createStudy).not.toHaveBeenCalled();
  expect(openStudy).not.toHaveBeenCalled();
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});
it('fails closed on malformed campaign lists rather than creating duplicates', async () => {
  listStudies.mockResolvedValue({});
  const boxes = await renderPanel();
  fireEvent.click(boxes[0]);
  fireEvent.click(screen.getByText('Generar enlace y QR'));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Respuesta paginada inválida',
  );
  expect(createStudy).not.toHaveBeenCalled();
  expect(createSurveyFromInstrument).not.toHaveBeenCalled();
});

it('prunes revoked selections when the authorized catalog refetch removes them', async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <DirectCatalogBatteryPanel
        projects={[{ id: 9, name: 'Synthetic company', organization_id: 99 }]}
      />
    </QueryClientProvider>,
  );
  fireEvent.click((await screen.findAllByRole('checkbox'))[0]);
  act(() => client.setQueryData(['home-authorized-catalog', '9', 99], []));
  await waitFor(() =>
    expect(screen.getByText('Generar enlace y QR')).toBeDisabled(),
  );
  expect(screen.getByText('0 seleccionados')).toBeInTheDocument();
  expect(createStudy).not.toHaveBeenCalled();
});
it('refuses incomplete pages instead of assuming no matching campaign exists', async () => {
  listStudies.mockImplementation((project, { page }) =>
    Promise.resolve(
      page === 1
        ? {
            items: [{ id: 5, instrument_version_id: 999, status: 'OPEN' }],
            total: 2,
          }
        : { items: [], total: 2 },
    ),
  );
  const boxes = await renderPanel();
  fireEvent.click(boxes[0]);
  fireEvent.click(screen.getByText('Generar enlace y QR'));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'lista de campañas está incompleta',
  );
  expect(createStudy).not.toHaveBeenCalled();
  expect(createSurveyFromInstrument).not.toHaveBeenCalled();
});
