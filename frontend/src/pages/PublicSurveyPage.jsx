import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { CheckCircle2 } from 'lucide-react';

import { getPublicStudy, createPublicResponseSession } from '../api/public.js';
import { completeResponseSession, upsertResponse } from '../api/responses.js';
import { readProgress, writeProgress } from '../utils/publicSurveyProgress.js';
import { ApiError } from '../api/client.js';
import { BrandMark } from '../brand/BrandMark.jsx';
import {
  resolveSurveyTheme,
  buildSurveyThemeVars,
} from '../design/surveyThemes.js';
import { hasAnswerValue } from '../utils/surveyAnswers.js';
import SurveyProgressHeader from '../components/colmena/survey/take/SurveyProgressHeader.jsx';
import SurveyQuestionRenderer from '../components/colmena/survey/take/SurveyQuestionRenderer.jsx';
import SurveyAllQuestionsView from '../components/colmena/survey/take/SurveyAllQuestionsView.jsx';

function toResponsePayload(question, value) {
  if (value === undefined || value === null || value === '') {
    return { is_missing: true };
  }
  switch (question.question_type) {
    case 'SINGLE_CHOICE':
    case 'LIKERT':
      return { option_id: value };
    case 'MULTIPLE_CHOICE':
    case 'RANKING':
      return { selected_option_ids: value };
    case 'NUMBER':
      return { numeric_value: value };
    case 'TEXT':
      return { text_value: value };
    case 'BOOLEAN':
      return { boolean_value: value };
    case 'DATE':
      return { date_value: value };
    case 'DATETIME':
      return { datetime_value: value };
    default:
      return { is_missing: true };
  }
}

export default function PublicSurveyPage({
  publicIdOverride,
  onCompleted,
  batteryContext,
}) {
  const { publicId: routePublicId } = useParams();
  const publicId = publicIdOverride || routePublicId;
  return (
    <SurveyFlow
      key={publicId}
      publicId={publicId}
      onCompleted={onCompleted}
      batteryContext={batteryContext}
    />
  );
}

function SurveyFlow({ publicId, onCompleted, batteryContext }) {
  const storageKey = 'aurora-survey:' + publicId;
  const [saved] = useState(() => readProgress(storageKey));
  const sessionCreatedRef = useRef(
    Boolean(saved.session || saved.completed || saved.expired),
  );
  const submittingRef = useRef(false);
  const [expired, setExpired] = useState(Boolean(saved.expired));
  const [session, setSession] = useState(saved.session || null);
  const [answers, setAnswers] = useState(saved.answers || {});
  const [index, setIndex] = useState(saved.index || 0);
  const [completed, setCompleted] = useState(Boolean(saved.completed));
  const [completionPending, setCompletionPending] = useState(
    Boolean(saved.completionPending),
  );
  const [invitationToken, setInvitationToken] = useState('');
  const [viewMode, setViewMode] = useState(saved.viewMode || 'all');

  useEffect(() => {
    if (expired) return;
    writeProgress(
      storageKey,
      completed
        ? { completed: true }
        : { session, answers, index, viewMode, completionPending },
    );
  }, [
    storageKey,
    session,
    answers,
    index,
    viewMode,
    completed,
    completionPending,
    expired,
  ]);

  const {
    data: bundle,
    isLoading: isLoadingBundle,
    isError: isBundleError,
  } = useQuery({
    queryKey: ['publicStudy', publicId],
    queryFn: () => getPublicStudy(publicId),
    retry: false,
  });

  const createSessionMutation = useMutation({
    mutationFn: (token) => createPublicResponseSession(publicId, token),
    onSuccess: (data) => setSession(data),
  });

  useEffect(() => {
    if (bundle && !bundle.requires_invitation && !sessionCreatedRef.current) {
      sessionCreatedRef.current = true;
      createSessionMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bundle]);

  const answerMutation = useMutation({
    mutationFn: ({ questionId, payload }) =>
      upsertResponse(session.id, questionId, payload, session.access_token),
  });

  const completeMutation = useMutation({
    mutationFn: () =>
      completeResponseSession(session.id, {}, session.access_token),
    onError: (error) => {
      if (error instanceof ApiError && [400, 422].includes(error.status))
        setCompletionPending(false);
    },
    onSuccess: async () => {
      // Persist completion before advancing, including if navigation/refetch fails.
      writeProgress(storageKey, { completed: true });
      setCompleted(true);
      setAnswers({});
      setSession(null);
      if (onCompleted) await onCompleted();
    },
  });

  if (isLoadingBundle) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-hero-glow">
        <div className="colmena-card px-8 py-6 text-sm text-muted">
          Cargando…
        </div>
      </div>
    );
  }

  if (isBundleError || !bundle) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-hero-glow px-4">
        <div className="colmena-card max-w-md px-8 py-10 text-center">
          <BrandMark className="mx-auto mb-4 h-8 w-8" />
          <p className="text-lg font-bold text-dark">
            Esta encuesta no está disponible.
          </p>
          <p className="mt-2 text-sm text-muted">
            El enlace puede estar mal escrito, o el estudio todavía no está
            abierto para respuestas.
          </p>
        </div>
      </div>
    );
  }

  if (expired) {
    return (
      <div role="alert" className="mx-auto max-w-lg space-y-3 p-8">
        <p>
          El progreso local venció después de 12 horas. Se eliminaron las
          respuestas y credenciales guardadas en esta pestaña. Si ya enviaste el
          cuestionario, no lo repitas.
        </p>
        <button
          type="button"
          className="survey-btn survey-btn-primary"
          onClick={() => {
            setExpired(false);
            if (!bundle.requires_invitation) createSessionMutation.mutate();
          }}
        >
          Iniciar una nueva sesión
        </button>
      </div>
    );
  }

  if (bundle.requires_invitation && !session && !completed) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-hero-glow px-4">
        <form
          className="colmena-card w-full max-w-md space-y-4 p-8"
          onSubmit={(event) => {
            event.preventDefault();
            createSessionMutation.mutate(invitationToken.trim());
          }}
        >
          <h1 className="text-lg font-bold text-dark">
            Acceso privado a la evaluación
          </h1>
          <p className="text-sm text-muted">
            Introduce el código de invitación proporcionado por el responsable
            del estudio.
          </p>
          <input
            className="colmena-input w-full"
            type="password"
            autoComplete="off"
            value={invitationToken}
            onChange={(event) => setInvitationToken(event.target.value)}
            placeholder="Código de invitación"
            required
          />
          {createSessionMutation.isError ? (
            <p className="text-sm text-danger">
              Código inválido, vencido o ya utilizado.
            </p>
          ) : null}
          <button
            className="survey-btn survey-btn-primary"
            type="submit"
            disabled={
              !invitationToken.trim() || createSessionMutation.isPending
            }
          >
            {createSessionMutation.isPending
              ? 'Verificando...'
              : 'Ingresar a la encuesta'}
          </button>
        </form>
      </main>
    );
  }

  if (completed) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-hero-glow px-4">
        <div className="colmena-card max-w-md px-8 py-10 text-center">
          <CheckCircle2 size={32} className="mx-auto mb-4 text-turquoise" />
          <p className="text-lg font-bold text-dark">¡Gracias por responder!</p>
          <p className="mt-2 text-sm text-muted">
            Tus respuestas fueron registradas correctamente.
          </p>
          {onCompleted && (
            <button
              type="button"
              onClick={onCompleted}
              className="survey-btn survey-btn-primary"
            >
              Continuar batería
            </button>
          )}
        </div>
      </div>
    );
  }

  if (
    !session &&
    !bundle.requires_invitation &&
    createSessionMutation.isError
  ) {
    return (
      <div role="alert" className="mx-auto max-w-lg p-8 text-red-700">
        No fue posible iniciar el instrumento. Comprueba el enlace.
        <button
          type="button"
          className="survey-btn survey-btn-primary"
          onClick={() => createSessionMutation.mutate()}
        >
          Reintentar
        </button>
      </div>
    );
  }

  const questions = bundle.questions;
  const total = questions.length;
  const answeredCount = Object.keys(answers).length;
  const isReady = Boolean(session);
  const submitError =
    answerMutation.error instanceof ApiError
      ? answerMutation.error.message
      : completeMutation.error instanceof ApiError
        ? completeMutation.error.message
        : answerMutation.isError || completeMutation.isError
          ? 'No se pudo confirmar el envío. Intenta nuevamente; se conservará la misma sesión.'
          : null;
  const theme = resolveSurveyTheme(bundle.theme);
  const isSubmitting = answerMutation.isPending || completeMutation.isPending;

  if (completionPending) {
    return (
      <div className="mx-auto max-w-lg space-y-3 p-8">
        <p>
          Estamos confirmando el envío. Para evitar duplicados, las respuestas
          no se pueden modificar hasta confirmar el resultado.
        </p>
        {submitError && <p role="alert">{submitError}</p>}
        <button
          type="button"
          className="survey-btn survey-btn-primary"
          disabled={completeMutation.isPending}
          onClick={async () => {
            if (submittingRef.current) return;
            submittingRef.current = true;
            try {
              await completeMutation.mutateAsync();
            } catch {
              /* Keep the frozen checkpoint until the server confirms. */
            } finally {
              submittingRef.current = false;
            }
          }}
        >
          Confirmar envío
        </button>
      </div>
    );
  }

  const setAnswer = (questionId, value) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  // Modo "todas las preguntas en pantalla (lista)": un solo Enviar que persiste
  // cada respuesta tocada y luego cierra la sesión (mucho más ágil y fluido).
  if (viewMode === 'all') {
    const handleSubmitAll = async () => {
      if (!session || submittingRef.current) return;
      submittingRef.current = true;
      try {
        if (!completionPending) {
          for (const [questionIdKey, value] of Object.entries(answers)) {
            const question = questions.find(
              (item) => String(item.id) === questionIdKey,
            );
            if (!question) continue;
            const payload = toResponsePayload(question, value);
            // eslint-disable-next-line no-await-in-loop
            await answerMutation.mutateAsync({
              questionId: question.id,
              payload,
            });
          }
        }
        writeProgress(storageKey, {
          session,
          answers,
          index,
          viewMode,
          completionPending: true,
        });
        setCompletionPending(true);
        await completeMutation.mutateAsync();
      } catch {
        // Mutation state presents the API error; retry uses the same session.
      } finally {
        submittingRef.current = false;
      }
    };

    return (
      <div
        className="survey-shell"
        data-survey-skin={theme.style}
        data-survey-align={theme.layout.align}
        style={buildSurveyThemeVars(theme)}
      >
        {batteryContext && (
          <p className="mx-auto max-w-4xl px-4 pt-3 text-xs font-bold text-[#31578d]">
            {batteryContext}
          </p>
        )}
        <SurveyProgressHeader
          studyName={bundle.study_name}
          answered={answeredCount}
          total={total}
          viewMode={viewMode}
          onToggleViewMode={() => setViewMode('single')}
        />
        <SurveyAllQuestionsView
          bundle={bundle}
          answers={answers}
          onAnswerChange={setAnswer}
          onSubmit={handleSubmitAll}
          submitting={!isReady || isSubmitting}
          error={submitError}
        />
      </div>
    );
  }

  const currentQuestion = questions[Math.min(index, Math.max(0, total - 1))];
  if (!currentQuestion)
    return (
      <p role="alert">Este instrumento no contiene preguntas disponibles.</p>
    );
  const currentSection = (bundle.sections || []).find((section) =>
    section.questions.some((question) => question.id === currentQuestion.id),
  );
  const isLast = index === total - 1;
  const isFirst = index === 0;
  const hasCurrentAnswer = hasAnswerValue(answers[currentQuestion.id]);

  const persistCurrentAnswer = async () => {
    if (!session) return;
    const value = answers[currentQuestion.id];
    const payload = toResponsePayload(currentQuestion, value);
    await answerMutation.mutateAsync({
      questionId: currentQuestion.id,
      payload,
    });
  };

  const handleContinue = async () => {
    if (!session || submittingRef.current) return;
    submittingRef.current = true;
    try {
      if (!completionPending) await persistCurrentAnswer();
      if (isLast) {
        writeProgress(storageKey, {
          session,
          answers,
          index,
          viewMode,
          completionPending: true,
        });
        setCompletionPending(true);
        await completeMutation.mutateAsync();
      } else {
        setIndex((value) => value + 1);
      }
    } catch {
      /* Mutation state presents the API error. */
    } finally {
      submittingRef.current = false;
    }
  };

  const handleBack = () => {
    setIndex((value) => Math.max(0, value - 1));
  };

  return (
    <div
      className="survey-shell"
      data-survey-skin={theme.style}
      data-survey-align={theme.layout.align}
      style={buildSurveyThemeVars(theme)}
    >
      <SurveyProgressHeader
        studyName={bundle.study_name}
        answered={answeredCount}
        total={total}
        viewMode={viewMode}
        onToggleViewMode={() => setViewMode('all')}
      />

      <main className="survey-main">
        <div className="survey-card">
          {currentSection ? (
            <div className="survey-section-banner">
              <p className="survey-section-title">{currentSection.title}</p>
              {currentSection.description ? (
                <p className="survey-section-description">
                  {currentSection.description}
                </p>
              ) : null}
              {currentSection.section_kind === 'EXOGENOUS' ? (
                <span className="survey-section-tag">
                  Dato de perfil · no modifica tu puntaje
                </span>
              ) : null}
            </div>
          ) : null}
          <div className="survey-grid">
            <div>
              <p className="survey-label">
                Pregunta {index + 1} de {total}
              </p>
              {currentQuestion.short_label ? (
                <p className="survey-short-label">
                  {currentQuestion.short_label}
                </p>
              ) : null}
            </div>
            <div className="flex flex-col gap-4">
              <p className="survey-question-text">
                {currentQuestion.question_text}
              </p>
              <SurveyQuestionRenderer
                question={currentQuestion}
                value={answers[currentQuestion.id]}
                onChange={(value) => setAnswer(currentQuestion.id, value)}
              />
              {currentQuestion.is_required && !hasCurrentAnswer ? (
                <p className="survey-required-note">
                  Esta pregunta es obligatoria.
                </p>
              ) : null}
              {submitError ? (
                <p className="survey-error-note">{submitError}</p>
              ) : null}
            </div>
          </div>
        </div>

        <div className="survey-footer">
          <button
            type="button"
            className="survey-btn survey-btn-secondary"
            onClick={handleBack}
            disabled={isFirst}
          >
            Atrás
          </button>
          <button
            type="button"
            className="survey-btn survey-btn-primary survey-btn--wide"
            onClick={handleContinue}
            disabled={
              !isReady ||
              isSubmitting ||
              (currentQuestion.is_required && !hasCurrentAnswer)
            }
          >
            {isSubmitting ? 'Procesando...' : isLast ? 'Enviar' : 'Continuar'}
          </button>
        </div>
      </main>
    </div>
  );
}
