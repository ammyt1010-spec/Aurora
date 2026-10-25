import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithQueryClient } from '../../../test-utils/renderWithQueryClient.jsx';
import { listStudies } from '../../../api/studies.js';
import { createEvaluationBundle } from '../../../api/evaluationBundles.js';
import BundleSelectionPanel from './BundleSelectionPanel.jsx';
vi.mock('../../../api/studies.js', () => ({ listStudies: vi.fn() }));
vi.mock('../../../api/evaluationBundles.js', () => ({
  createEvaluationBundle: vi.fn(),
}));
const studies = Array.from({ length: 13 }, (_, i) => ({
  id: i + 1,
  name: 'Instrument ' + (i + 1),
  status: 'OPEN',
  public_id: 'public-' + (i + 1),
  instrument_version_id: i + 10,
}));
beforeEach(() => {
  vi.clearAllMocks();
  listStudies.mockResolvedValue({ items: studies });
  createEvaluationBundle.mockResolvedValue({ public_id: 'batch' });
});
function renderPanel() {
  return renderWithQueryClient(
    <BundleSelectionPanel
      projects={[
        { id: 1, name: 'Company A' },
        { id: 2, name: 'Company B' },
      ]}
    />,
  );
}
it('shares one selected authorized instrument directly without creating a battery', async () => {
  renderPanel();
  const boxes = await screen.findAllByRole('checkbox');
  fireEvent.click(boxes[0]);
  fireEvent.click(screen.getByText('Generar enlace y QR'));
  expect(await screen.findByRole('link')).toHaveAttribute(
    'href',
    window.location.origin + '/encuesta/public-1',
  );
  expect(createEvaluationBundle).not.toHaveBeenCalled();
  fireEvent.click(boxes[1]);
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});
it('preserves selection order and caps a batch at twelve instruments', async () => {
  renderPanel();
  const boxes = await screen.findAllByRole('checkbox');
  [...boxes].reverse().forEach((box) => fireEvent.click(box));
  expect(boxes[0]).not.toBeChecked();
  fireEvent.click(screen.getByText('Generar enlace y QR'));
  await waitFor(() =>
    expect(createEvaluationBundle).toHaveBeenCalledWith('1', {
      label: 'Batería empresarial · Company A',
      study_ids: [13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2],
    }),
  );
});
it('clears company-specific selection and generated links when changing company', async () => {
  renderPanel();
  fireEvent.click((await screen.findAllByRole('checkbox'))[0]);
  fireEvent.click(screen.getByText('Generar enlace y QR'));
  await screen.findByRole('link');
  fireEvent.change(screen.getByLabelText('Empresa para la batería'), {
    target: { value: '2' },
  });
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  expect(screen.getByText('Generar enlace y QR')).toBeDisabled();
});
