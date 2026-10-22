import { useQuery } from '@tanstack/react-query';
import { AlertTriangle } from 'lucide-react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { getProjectLongitudinal } from '../../../api/analytics.js';

/** Una serie solo es interpretable cuando el servidor valida versión y baremo. */
export default function LongitudinalBIWidget({ projectId, dimension }) {
  const query = useQuery({
    queryKey: ['aurora-longitudinal', projectId],
    queryFn: () => getProjectLongitudinal(projectId),
    enabled: Boolean(projectId),
    retry: false,
    staleTime: 120000,
  });
  if (query.isLoading) return <div className="aurora-bi-empty">Calculando comparabilidad longitudinal…</div>;
  if (query.isError) return <p role="alert" className="aurora-bi-help">No se pudo consultar la evolución temporal.</p>;
  const constructs = (query.data?.constructs || []).filter((x) => x.construct_type === 'DIMENSION');
  const selected = constructs.find((x) => x.construct_code === dimension) ||
    constructs.find((x) => x.is_comparable && (x.points || []).length >= 2);
  if (!selected) return <p className="aurora-bi-help">Todavía no hay dimensiones con mediciones comparables.</p>;
  if (!selected.is_comparable || !selected.methodological_equivalence) {
    return (
      <div role="status" className="aurora-bi-help flex items-start gap-2">
        <AlertTriangle size={15} className="shrink-0 text-warning"/>
        No se pueden relacionar las mediciones de {selected.construct_name}: versiones instrumentales o baremos incompatibles.
      </div>
    );
  }
  const points = (selected.points || [])
    .filter((p) => !p.suppressed && typeof p.unfavorable_pct === 'number' && Number.isFinite(p.unfavorable_pct))
    .map((p) => ({
      ...p,
      label: p.date ? new Date(p.date).toLocaleDateString('es-PE', { year: '2-digit', month: 'short' }) : p.study_name,
    }));
  if (points.length < 2) {
    return <p className="aurora-bi-help">Se requieren al menos dos mediciones publicables y equivalentes para mostrar una tendencia.</p>;
  }
  return (
    <div className="aurora-bi-longitudinal">
      <p className="aurora-bi-help"><strong>{selected.construct_name}</strong> · {points.length} mediciones equivalentes · % desfavorable</p>
      <div className="h-[195px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 12, right: 15, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e3e9f2" />
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#65728c' }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#65728c' }} tickFormatter={(v) => v + '%'} />
            <Tooltip formatter={(v) => [Number(v).toFixed(1) + '%', 'Desfavorable']}
              labelFormatter={(label) => label} />
            <Line dataKey="unfavorable_pct" type="monotone" stroke="#d75e6d" strokeWidth={2.5}
              dot={{ r: 4, fill: '#d75e6d' }} activeDot={{ r: 6 }} name="Desfavorable"/>
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="aurora-bi-help">Tendencia descriptiva, no causal. Las mediciones excluidas no se conectan ni se promedian.</p>
    </div>
  );
}
