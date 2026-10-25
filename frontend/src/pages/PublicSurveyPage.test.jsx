import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { renderWithQueryClient } from '../test-utils/renderWithQueryClient.jsx';
import { getPublicStudy, createPublicResponseSession } from '../api/public.js';
import { completeResponseSession, upsertResponse } from '../api/responses.js';
import { ApiError } from '../api/client.js';
import PublicSurveyPage from './PublicSurveyPage.jsx';
vi.mock('../api/public.js', () => ({
  getPublicStudy: vi.fn(),
  createPublicResponseSession: vi.fn(),
}));
vi.mock('../api/responses.js', () => ({
  completeResponseSession: vi.fn(),
  upsertResponse: vi.fn(),
}));
vi.mock('../components/colmena/survey/take/SurveyAllQuestionsView.jsx', () => ({
  default: ({ answers, onAnswerChange, onSubmit, submitting }) => (
    <div>
      <input
        aria-label="Respuesta"
        value={answers[1] || ''}
        onChange={(e) => onAnswerChange(1, e.target.value)}
      />
      <button disabled={submitting} onClick={onSubmit}>
        Enviar
      </button>
    </div>
  ),
}));
const bundle = {
  study_name: 'Estudio',
  questions: [{ id: 1, question_type: 'TEXT' }],
};
function renderPage(props = {}) {
  return renderWithQueryClient(
    <MemoryRouter>
      <PublicSurveyPage publicIdOverride="survey-a" {...props} />
    </MemoryRouter>,
  );
}
beforeEach(() => {
  sessionStorage.clear();
  vi.clearAllMocks();
  getPublicStudy.mockResolvedValue(bundle);
  createPublicResponseSession.mockResolvedValue({
    id: 11,
    access_token: 'isolated-capability',
  });
  upsertResponse.mockResolvedValue({});
  completeResponseSession.mockResolvedValue({});
});
describe('Public survey recovery', () => {
  it('restores the same independent session and unsent answers on reload', async () => {
    const first = renderPage();
    const input = await screen.findByLabelText('Respuesta');
    await waitFor(() => expect(screen.getByText('Enviar')).not.toBeDisabled());
    fireEvent.change(input, { target: { value: 'Saved locally' } });
    first.unmount();
    renderPage();
    expect(await screen.findByLabelText('Respuesta')).toHaveValue(
      'Saved locally',
    );
    expect(createPublicResponseSession).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByText('Enviar'));
    expect(
      await screen.findByText('¡Gracias por responder!'),
    ).toBeInTheDocument();
    expect(upsertResponse).toHaveBeenCalledWith(
      11,
      1,
      { text_value: 'Saved locally' },
      'isolated-capability',
    );
    expect(JSON.stringify(sessionStorage)).not.toContain('Saved locally');
  });
  it('does not create or submit another session after a completed questionnaire reload', async () => {
    const first = renderPage();
    await screen.findByLabelText('Respuesta');
    await waitFor(() => expect(screen.getByText('Enviar')).not.toBeDisabled());
    fireEvent.click(screen.getByText('Enviar'));
    await screen.findByText('¡Gracias por responder!');
    first.unmount();
    renderPage();
    await screen.findByText('¡Gracias por responder!');
    expect(createPublicResponseSession).toHaveBeenCalledTimes(1);
    expect(completeResponseSession).toHaveBeenCalledTimes(1);
  });
  it('retries uncertain completion with the same session, without resending answers', async () => {
    completeResponseSession.mockRejectedValueOnce(
      new Error('Network interrupted'),
    );
    const first = renderPage();
    fireEvent.change(await screen.findByLabelText('Respuesta'), {
      target: { value: 'Answer' },
    });
    await waitFor(() => expect(screen.getByText('Enviar')).not.toBeDisabled());
    fireEvent.click(screen.getByText('Enviar'));
    await waitFor(() =>
      expect(completeResponseSession).toHaveBeenCalledTimes(1),
    );
    await waitFor(() =>
      expect(screen.getByText('Confirmar envío')).not.toBeDisabled(),
    );
    first.unmount();
    renderPage();
    await screen.findByText('Confirmar envío');
    expect(screen.queryByLabelText('Respuesta')).not.toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText('Confirmar envío')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByText('Confirmar envío'));
    await screen.findByText('¡Gracias por responder!');
    expect(createPublicResponseSession).toHaveBeenCalledTimes(1);
    expect(upsertResponse).toHaveBeenCalledTimes(1);
    expect(completeResponseSession).toHaveBeenCalledTimes(2);
  });
  it.each([400, 422])(
    'allows correction after definite %s validation rejection',
    async (status) => {
      completeResponseSession.mockRejectedValueOnce(
        new ApiError(status, { message: 'Required answer' }),
      );
      renderPage();
      const input = await screen.findByLabelText('Respuesta');
      fireEvent.change(input, { target: { value: 'First' } });
      await waitFor(() =>
        expect(screen.getByText('Enviar')).not.toBeDisabled(),
      );
      fireEvent.click(screen.getByText('Enviar'));
      await waitFor(() =>
        expect(completeResponseSession).toHaveBeenCalledTimes(1),
      );
      const editable = await screen.findByLabelText('Respuesta');
      fireEvent.change(editable, { target: { value: 'Corrected' } });
      fireEvent.click(screen.getByText('Enviar'));
      await screen.findByText('¡Gracias por responder!');
      expect(upsertResponse).toHaveBeenLastCalledWith(
        11,
        1,
        { text_value: 'Corrected' },
        'isolated-capability',
      );
      expect(createPublicResponseSession).toHaveBeenCalledTimes(1);
    },
  );
});
