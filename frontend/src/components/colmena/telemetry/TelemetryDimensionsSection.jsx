import { Card } from '../../ui/Card.jsx';
import { EmptyState } from '../../ui/EmptyState.jsx';
import { LoadingState } from '../../ui/LoadingState.jsx';

function QuestionFrequencies({ question, minPublishableN }) {
  const isOrdinal = question.measurement_level === 'ORDINAL';
  const frequencies = isOrdinal
    ? [...question.frequencies].sort((a, b) => a.order - b.order)
    : [...question.frequencies].sort((a, b) => b.n - a.n || a.order - b.order);
  const maxPercentage = Math.max(1, ...frequencies.map((item) => item.percentage));

  return (
    <Card className="overflow-hidden" padded={false}>
      <div className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <p className="min-w-0 text-sm font-semibold leading-5 text-dark">{question.question_text}</p>
          <span className="shrink-0 rounded-lg bg-amber/10 px-2 py-1 text-[10px] font-bold text-yellowDark">
            n = {question.valid_n}
          </span>
        </div>
      </div>
      {question.valid_n > 0 && question.valid_n < minPublishableN ? (
        <div className="p-4 text-sm text-muted">Distribución protegida hasta reunir al menos {minPublishableN} respuestas válidas.</div>
      ) : frequencies.length ? (
        <div className="space-y-2.5 p-4">
          {frequencies.map((item) => (
            <div key={item.code}>
              <div className="mb-1 flex items-center justify-between gap-3 text-xs">
                <span className="truncate font-medium text-dark">{item.label}</span>
                <span className="shrink-0 text-muted">{item.n} · {item.percentage.toFixed(1)}%</span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-[#F1F3F5]">
                <div
                  className={`h-full rounded-full ${isOrdinal ? 'bg-amber' : 'bg-turquoise'}`}
                  style={{ width: `${(item.percentage / maxPercentage) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="p-4 text-sm text-muted">Sin respuestas todavía.</div>
      )}
    </Card>
  );
}

/**
 * Preguntas y sus respuestas, agrupadas por dimensión: dimensión[preguntas]
 * [respuestas de cada pregunta], repetido por cada dimensión. Usa
 * `descriptives` (`GET /studies/{id}/response-descriptives`), que ya trae
 * cada pregunta puntuada con su dimensión (`group_type === 'DIMENSION'`) —
 * separado del perfil sociolaboral y los módulos complementarios.
 */
export default function TelemetryDimensionsSection({ descriptives, isLoading }) {
  if (isLoading) return <LoadingState label="Cargando dimensiones…" />;

  const groups = (descriptives?.groups || []).filter((group) => group.group_type === 'DIMENSION');
  const questions = descriptives?.questions || [];

  if (groups.length === 0) {
    return <EmptyState title="Sin dimensiones" description="Este instrumento no tiene preguntas puntuadas por dimensión." />;
  }

  return (
    <div className="flex flex-col gap-6">
      {groups.map((group) => {
        const groupQuestions = questions.filter((question) => question.group_key === group.key);
        return (
          <section key={group.key} className="space-y-3">
            <h3 className="text-sm font-bold text-dark">{group.label}</h3>
            <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
              {groupQuestions.map((question) => <QuestionFrequencies key={question.question_id} question={question} minPublishableN={descriptives?.min_publishable_n || 5} />)}
            </div>
          </section>
        );
      })}
    </div>
  );
}
