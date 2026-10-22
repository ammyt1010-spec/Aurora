import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, BarChart3, RefreshCw, ShieldCheck } from 'lucide-react';

import { getExecutiveDashboard } from '../../../api/reports.js';
import { Card } from '../../ui/Card.jsx';

const INDICATOR = {
  RED: { label: 'Prioritario', className: 'bg-red-500/10 text-red-600' },
  AMBER: { label: 'Seguimiento', className: 'bg-amber/15 text-yellowDark' },
  GREEN: { label: 'Favorable', className: 'bg-emerald-500/10 text-emerald-600' },
  GRAY: { label: 'Sin clasificar', className: 'bg-surfaceSoft text-muted' },
};

function SummaryValue({ label, value }) {
  return (
    <div className="rounded-xl border border-border bg-surfaceSoft/60 p-3">
      <p className="text-xs font-medium text-muted">{label}</p>
      <p className="mt-1 text-xl font-bold tabular-nums text-dark">{value ?? '—'}</p>
    </div>
  );
}

export default function ExecutiveReportDashboard({ studyId }) {
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['enterprise-executive-dashboard', studyId],
    queryFn: () => getExecutiveDashboard(studyId),
    enabled: Boolean(studyId),
    retry: false,
  });

  if (!studyId) return null;

  const risks = data?.risk_distribution || {};
  const participation = data?.participation || {};
  const ranks = data?.construct_rankings || [];

  return (
    <Card className="p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber/10 text-amber">
            <BarChart3 size={20} />
          </div>
          <div>
            <h2 className="text-base font-bold text-dark">Resumen ejecutivo empresarial</h2>
            <p className="text-xs text-muted">Resultados colectivos verificados por la API y controles de anonimato</p>
          </div>
        </div>
        <button type="button" onClick={() => refetch()} disabled={isFetching}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-semibold text-muted hover:text-dark disabled:opacity-60">
          <RefreshCw size={14} /> Actualizar
        </button>
      </div>

      {isLoading && <p className="text-sm text-muted">Consultando indicadores…</p>}
      {isError && (
        <div role="alert" className="flex items-start gap-2 rounded-xl border border-border p-3 text-sm text-muted">
          <AlertTriangle size={17} className="shrink-0" />
          No hay resultados consolidados disponibles para este estudio o no fue posible consultarlos.
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <SummaryValue label="Respuestas válidas" value={participation.valid_count} />
            <SummaryValue label="Riesgos prioritarios" value={risks.high_risk_count} />
            <SummaryValue label="En seguimiento" value={risks.medium_risk_count} />
            <SummaryValue label="Clasificación favorable" value={risks.low_risk_count} />
          </div>
          <p className="rounded-xl border border-border bg-surfaceSoft p-3 text-sm font-medium text-dark">
            {data.headline}
          </p>
          {ranks.length === 0 ? (
            <p className="flex items-start gap-2 text-sm text-muted">
              <ShieldCheck size={17} className="shrink-0" />
              No se publican puntuaciones para grupos sin muestra suficiente o sin clasificación metodológica válida.
            </p>
          ) : (
            <div className="space-y-2">
              <p className="text-xs font-bold uppercase tracking-wide text-muted">Constructos evaluados</p>
              {ranks.map((item) => {
                const indicator = INDICATOR[item.traffic_light] || INDICATOR.GRAY;
                return (
                  <div key={item.construct_code} className="rounded-xl border border-border px-3 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-dark">{item.construct_name}</p>
                      <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${indicator.className}`}>
                        {indicator.label}
                      </span>
                    </div>
                    {typeof item.unfavorable_pct === 'number' && Number.isFinite(item.unfavorable_pct) ? (
                      <div className="mt-2 flex items-center gap-3">
                        <div role="img" aria-label={`Porcentaje desfavorable: ${item.unfavorable_pct.toFixed(1)}%`}
                          className="h-2.5 flex-1 overflow-hidden rounded-full bg-surfaceSoft">
                          <div className={`h-full rounded-full ${item.traffic_light === 'RED' ? 'bg-red-500' : item.traffic_light === 'AMBER' ? 'bg-amber' : 'bg-emerald-500'}`}
                            style={{ width: `${Math.max(0, Math.min(100, item.unfavorable_pct))}%` }} />
                        </div>
                        <span className="shrink-0 text-xs font-bold tabular-nums text-dark">
                          {item.unfavorable_pct.toFixed(1)}% desfavorable
                        </span>
                      </div>
                    ) : null}
                    <details className="mt-2">
                      <summary className="cursor-pointer text-xs font-semibold text-muted hover:text-dark">
                        Interpretación y acción sugerida
                      </summary>
                      <p className="mt-2 text-xs leading-relaxed text-muted">{item.recommendation}</p>
                    </details>
                  </div>
                );
              })}
            </div>
          )}
          <p className="text-[11px] text-muted">
            La clasificación solo se presenta cuando existen datos publicables y baremos aplicables.
            La información agregada no autoriza decisiones individuales sobre trabajadores.
          </p>
        </>
      )}
    </Card>
  );
}
