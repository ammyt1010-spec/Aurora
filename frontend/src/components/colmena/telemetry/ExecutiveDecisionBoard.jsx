import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart3,
  CircleHelp,
  FilterX,
  RefreshCcw,
  Users,
} from 'lucide-react';
import { getCensopasReadiness } from '../../../api/instruments.js';
import { getExecutiveDashboard } from '../../../api/reports.js';
import {
  getCensopasResults,
  getCensopasUnitResults,
  getResultsOverview,
  getStudy,
  listStudyUnitTypes,
} from '../../../api/studies.js';
import {
  actionForDimension,
  comparisonUnits,
  executiveRows,
  matrixCells,
  maxUnfavorable,
  percentText,
  riskLabel,
  selectedDimension,
  countText,
  rateText,
} from './executiveBoardModel.js';
import LongitudinalBIWidget from './LongitudinalBIWidget.jsx';
import './ExecutiveDecisionBoard.css';

const BANDS = [
  { key: 'favorable_pct', label: 'Favorable', color: '#10B981' },
  { key: 'intermediate_pct', label: 'Intermedio', color: '#F59E0B' },
  { key: 'unfavorable_pct', label: 'Desfavorable', color: '#EF4444' },
];
function Empty({ children }) {
  return (
    <div className="aurora-compact-empty">
      <CircleHelp size={18} aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}
function Card({ title, children }) {
  return (
    <section className="aurora-card-bi">
      <div className="aurora-card-bi-head">
        <h3 className="aurora-card-bi-title">{title}</h3>
      </div>
      {children}
    </section>
  );
}
function Distribution({ row }) {
  let offset = 0;
  return (
    <div className="aurora-donut-content">
      <svg
        width="104"
        height="104"
        viewBox="0 0 104 104"
        role="img"
        aria-label={`Distribución de ${row.construct_name}`}
      >
        {BANDS.map((b) => {
          const length = row[b.key] * 2.513274;
          const start = offset;
          offset += length;
          return (
            <circle
              key={b.key}
              data-band={b.key}
              data-value={row[b.key]}
              cx="52"
              cy="52"
              r="40"
              fill="none"
              stroke={b.color}
              strokeWidth="16"
              strokeDasharray={`${length} ${251.3274 - length}`}
              strokeDashoffset={-start}
              transform="rotate(-90 52 52)"
            />
          );
        })}
        <text x="52" y="55" textAnchor="middle" fontSize="11">
          Dimensión
        </text>
      </svg>
      <div className="aurora-donut-legend-list">
        {BANDS.map((b) => (
          <div className="aurora-donut-legend-item" key={b.key}>
            <span
              className="aurora-legend-sq"
              style={{ background: b.color }}
            />
            {b.label}: {percentText(row[b.key])}
          </div>
        ))}
      </div>
    </div>
  );
}
export default function ExecutiveDecisionBoard({
  projectId,
  studyId,
  telemetry,
  studies,
  setStudyId,
  projectName,
  onRefresh,
  isRefreshing,
}) {
  // Matrix and Segment State
  const [dimension, setDimension] = useState('ALL');
  const [unitTypeId, setUnitTypeId] = useState('');
  const [unitId, setUnitId] = useState('ALL');
  const [focusedCode, setFocusedCode] = useState(null);
  const [analysisView, setAnalysisView] = useState('diagnosis');

  useEffect(() => {
    setDimension('ALL');
    setUnitTypeId('');
    setUnitId('ALL');
    setFocusedCode(null);
    setAnalysisView('diagnosis');
  }, [studyId]);

  const reset = () => {
    setDimension('ALL');
    setUnitTypeId('');
    setUnitId('ALL');
    setFocusedCode(null);
  };

  const studyQuery = useQuery({
    queryKey: ['study', studyId],
    queryFn: () => getStudy(studyId),
    enabled: Boolean(studyId),
    retry: false,
  });
  const readinessQuery = useQuery({
    queryKey: ['censopas-readiness', studyQuery.data?.instrument_version_id],
    queryFn: () => getCensopasReadiness(studyQuery.data.instrument_version_id),
    enabled: Boolean(studyQuery.data?.instrument_version_id),
    retry: false,
  });
  const isCensopas = readinessQuery.data?.is_censopas_instrument === true;
  const classificationKnown =
    Boolean(studyQuery.data) &&
    (!studyQuery.data.instrument_version_id || readinessQuery.isSuccess);
  const genericMode = classificationKnown && !isCensopas;

  const resultQuery = useQuery({
    queryKey: ['compact-censopas', studyId],
    queryFn: () => getCensopasResults(studyId),
    enabled: Boolean(studyId && isCensopas),
    retry: false,
  });
  const genericQuery = useQuery({
    queryKey: ['compact-results', studyId],
    queryFn: () => getResultsOverview(studyId),
    enabled: Boolean(studyId && genericMode),
    retry: false,
  });
  const analysisRunId = (isCensopas ? resultQuery.data : genericQuery.data)
    ?.analysis_run_id;
  const executiveQuery = useQuery({
    queryKey: ['enterprise-executive-dashboard', studyId, analysisRunId],
    queryFn: () => getExecutiveDashboard(studyId, analysisRunId),
    enabled: Boolean(studyId && analysisRunId),
    retry: false,
  });
  const unitTypesQuery = useQuery({
    queryKey: ['studyUnitTypes', studyId],
    queryFn: () => listStudyUnitTypes(studyId),
    enabled: Boolean(studyId && isCensopas),
    retry: false,
  });
  const unitQuery = useQuery({
    queryKey: ['censopasUnitResults', studyId, unitTypeId, analysisRunId],
    queryFn: () => getCensopasUnitResults(studyId, Number(unitTypeId)),
    enabled: Boolean(studyId && isCensopas && unitTypeId),
    retry: false,
  });

  const allRows = useMemo(
    () =>
      executiveRows(
        isCensopas ? resultQuery.data?.results : genericQuery.data?.results,
        isCensopas,
      ),
    [isCensopas, resultQuery.data, genericQuery.data],
  );
  const sameUnitRun = Boolean(
    analysisRunId && unitQuery.data?.analysis_run_id === analysisRunId,
  );
  const allUnits = useMemo(
    () => comparisonUnits(sameUnitRun ? unitQuery.data?.results : []),
    [unitQuery.data, sameUnitRun],
  );
  const safeCells = useMemo(
    () => matrixCells(sameUnitRun ? unitQuery.data?.results : []),
    [unitQuery.data, sameUnitRun],
  );
  const selectedUnit = allUnits.find((x) => x.id === unitId);
  const unitsVisible = unitTypeId
    ? selectedUnit
      ? [selectedUnit]
      : unitId === 'ALL'
        ? allUnits
        : []
    : [];
  const visibleRows = useMemo(
    () =>
      allRows.filter(
        (row) =>
          dimension === 'ALL' ||
          String(row.construct_code) === String(dimension),
      ),
    [allRows, dimension],
  );
  const focused = selectedDimension(visibleRows, focusedCode);
  const sameExecutiveRun = Boolean(
    analysisRunId && executiveQuery.data?.analysis_run_id === analysisRunId,
  );
  const rankings = sameExecutiveRun
    ? executiveQuery.data?.construct_rankings || []
    : [];
  const interpretation =
    focused && !selectedUnit
      ? actionForDimension(rankings, focused.construct_code)
      : null;
  const matchingCell =
    focused && selectedUnit
      ? safeCells.get(focused.construct_code + '::' + selectedUnit.id)
      : null;
  const worstValue = selectedUnit
    ? maxUnfavorable(
        visibleRows
          .map((row) =>
            safeCells.get(row.construct_code + '::' + selectedUnit.id),
          )
          .filter(Boolean),
      )
    : isCensopas
      ? maxUnfavorable(visibleRows)
      : null;

  const loading =
    studyQuery.isLoading ||
    (Boolean(studyQuery.data?.instrument_version_id) &&
      readinessQuery.isLoading) ||
    (isCensopas ? resultQuery.isLoading : genericQuery.isLoading);
  const error =
    studyQuery.isError ||
    readinessQuery.isError ||
    (isCensopas ? resultQuery.isError : genericQuery.isError);
  const comparing = Boolean(unitTypeId);
  const sourceUnavailable =
    comparing && (unitQuery.isLoading || unitQuery.isError || !sameUnitRun);
  const activeFilter = selectedUnit ? selectedUnit.label : 'Empresa completa';

  if (error)
    return (
      <div className="aurora-compact-state" role="alert">
        No se pudo consultar el diagnóstico metodológico. Verifica el estudio y
        vuelve a intentar.
      </div>
    );
  if (loading || !classificationKnown)
    return (
      <div className="aurora-compact-state">
        Cargando diagnóstico ejecutivo…
      </div>
    );

  // Counts are study-wide; dimension/segment filters never imply a filtered headcount.
  const selectionUnavailable =
    sourceUnavailable || (unitId !== 'ALL' && !selectedUnit);
  const contextRow = selectionUnavailable
    ? null
    : selectedUnit
      ? matchingCell
      : focused;
  const displayedRows = selectionUnavailable
    ? []
    : selectedUnit
      ? visibleRows
          .map((row) =>
            safeCells.get(row.construct_code + '::' + selectedUnit.id),
          )
          .filter(Boolean)
      : visibleRows;
  const validCount = countText(telemetry?.valid_count);
  const generatedAt = sameExecutiveRun
    ? executiveQuery.data?.generated_at
    : null;
  const updated =
    generatedAt && Number.isFinite(Date.parse(generatedAt))
      ? new Date(generatedAt).toLocaleString('es-PE')
      : 'N/D';
  const refresh = () => {
    onRefresh?.();
    studyQuery.refetch();
    if (analysisRunId) executiveQuery.refetch();
    if (studyQuery.data?.instrument_version_id) readinessQuery.refetch();
    if (isCensopas) {
      resultQuery.refetch();
      unitTypesQuery.refetch();
      if (unitTypeId) unitQuery.refetch();
    }
    if (genericMode) genericQuery.refetch();
  };
  const metrics = [
    ['Respuestas válidas', validCount, 'Captura actual · estudio completo'],
    [
      'Invitaciones',
      countText(telemetry?.invited_count),
      'Población registrada, si está disponible',
    ],
    [
      'Cobertura válida',
      rateText(telemetry?.valid_rate),
      'Válidas / invitaciones · estudio completo',
    ],
    [
      'Participación',
      rateText(telemetry?.response_rate),
      'Iniciadas / invitaciones · estudio completo',
    ],
    [
      'Dimensiones publicables',
      selectionUnavailable ? 'N/D' : String(displayedRows.length),
      activeFilter,
    ],
    [
      isCensopas ? 'Mayor % desfavorable' : 'Puntuación seleccionada',
      isCensopas
        ? percentText(selectionUnavailable ? null : worstValue)
        : (contextRow?.mean_score?.toFixed(1) ?? 'N/D'),
      isCensopas
        ? 'Máximo entre dimensiones; no personas'
        : 'Escala 0–100; no nivel de riesgo',
    ],
  ];
  return (
    <div
      className="aurora-exec-telemetry-root"
      aria-label="Tablero Ejecutivo de Telemetría Dinámica"
    >
      <header className="aurora-telemetry-topbar">
        <div className="aurora-telemetry-title-group">
          <div className="aurora-telemetry-icon-badge">
            <BarChart3 size={20} />
          </div>
          <div>
            <h1 className="aurora-telemetry-title">Telemetría</h1>
            <div className="aurora-telemetry-subtitle">
              <span>
                {projectName || executiveQuery.data?.company_name || 'Proyecto'}{' '}
                ·{' '}
                {telemetry?.instrument_name ||
                  executiveQuery.data?.instrument_name ||
                  'Instrumento no disponible'}
              </span>
              {studies?.length && setStudyId ? (
                <select
                  className="aurora-telemetry-study-pill"
                  aria-label="Seleccionar estudio de telemetría"
                  value={studyId || ''}
                  onChange={(e) =>
                    setStudyId(e.target.value ? Number(e.target.value) : null)
                  }
                >
                  {studies.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="aurora-telemetry-study-pill">
                  {studyQuery.data?.name ||
                    telemetry?.study_name ||
                    'Estudio seleccionado'}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="aurora-telemetry-top-actions">
          <span className="aurora-telemetry-live-time">
            Informe generado: {updated}
          </span>
          <button
            type="button"
            className="aurora-telemetry-btn-refresh"
            onClick={refresh}
            disabled={isRefreshing}
          >
            <RefreshCcw size={12} />
            Actualizar
          </button>
        </div>
      </header>
      <section
        className="aurora-slicers-bar"
        role="group"
        aria-label="Filtros coordinados"
      >
        <div className="aurora-slicers-group">
          <label className="aurora-slicer-item">
            Dimensión
            <select
              aria-label="Dimensión del diagnóstico"
              value={dimension}
              onChange={(e) => setDimension(e.target.value)}
            >
              <option value="ALL">Todas</option>
              {allRows.map((r) => (
                <option key={r.construct_code} value={r.construct_code}>
                  {r.construct_name}
                </option>
              ))}
            </select>
          </label>
          <label className="aurora-slicer-item">
            Comparar por
            <select
              aria-label="Tipo de segmento"
              value={unitTypeId}
              disabled={!isCensopas || unitTypesQuery.isError}
              onChange={(e) => {
                setUnitTypeId(e.target.value);
                setUnitId('ALL');
              }}
            >
              <option value="">Toda la empresa</option>
              {(unitTypesQuery.data || []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label className="aurora-slicer-item">
            Unidad
            <select
              aria-label="Unidad del segmento"
              value={unitId}
              disabled={!unitTypeId || sourceUnavailable}
              onChange={(e) => setUnitId(e.target.value)}
            >
              <option value="ALL">Todas las publicables</option>
              {allUnits.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.label}
                </option>
              ))}
            </select>
          </label>
          <label className="aurora-slicer-item">
            Sexo / turno / edad
            <select disabled aria-label="Filtros demográficos no disponibles">
              <option>No disponibles</option>
            </select>
          </label>
        </div>
        <button className="aurora-slicer-reset" type="button" onClick={reset}>
          <FilterX size={13} />
          Restablecer
        </button>
      </section>
      <h2 className="aurora-card-bi-title">Diagnóstico ejecutivo</h2>
      {genericMode && (
        <p className="aurora-bi-help">
          Puntuación descriptiva normalizada, no nivel de riesgo
        </p>
      )}
      {executiveQuery.isError && (
        <p role="status">
          N/D: no se pudo consultar el informe ejecutivo; las dimensiones se
          muestran desde su fuente metodológica.
        </p>
      )}
      {unitTypesQuery.isError && (
        <p role="status">No se pudieron consultar los tipos de segmento.</p>
      )}
      <section
        className="aurora-kpi-grid"
        aria-label="Indicadores clave de telemetría"
      >
        {metrics.map(([label, value, note]) => (
          <div className="aurora-kpi-card" key={label}>
            <div className="aurora-kpi-header">
              <div className="aurora-kpi-icon">
                <Users size={16} />
              </div>
              <div className="aurora-kpi-info">
                <span className="aurora-kpi-label">{label}</span>
                <strong
                  className="aurora-kpi-value"
                  data-testid={`metric-${label}`}
                >
                  {value}
                </strong>
                <span className="aurora-kpi-subtext">{note}</span>
              </div>
            </div>
          </div>
        ))}
      </section>
      <div className="aurora-dashboard-canvas">
        <div className="aurora-main-analytics-column">
          <div className="aurora-analytics-row-1">
            <Card title="Resultados por dimensión">
              {!displayedRows.length ? (
                <Empty>N/D · Sin dimensiones publicables</Empty>
              ) : (
                <div className="aurora-dimension-bars-list">
                  {displayedRows.map((row) => (
                    <div
                      className="aurora-dim-bar-row"
                      key={row.construct_code}
                    >
                      <button
                        className="aurora-dim-bar-label"
                        type="button"
                        onClick={() => setFocusedCode(row.construct_code)}
                      >
                        {row.construct_name}
                      </button>
                      <div
                        className="aurora-dim-bar-track"
                        role="img"
                        aria-label={`${row.construct_name}: ${isCensopas ? BANDS.map((b) => `${b.label} ${percentText(row[b.key])}`).join(', ') : `puntaje ${row.mean_score}`}`}
                      >
                        {isCensopas ? (
                          BANDS.map((b) => (
                            <div
                              key={b.key}
                              data-band={b.key}
                              data-value={row[b.key]}
                              className="aurora-dim-bar-seg"
                              style={{
                                width: `${row[b.key]}%`,
                                background: b.color,
                              }}
                              title={`${b.label}: ${percentText(row[b.key])}`}
                            >
                              {row[b.key] >= 14 ? percentText(row[b.key]) : ''}
                            </div>
                          ))
                        ) : (
                          <div
                            className="aurora-dim-bar-seg"
                            data-score={row.mean_score}
                            style={{
                              width: `${row.mean_score}%`,
                              background: '#2563EB',
                            }}
                          />
                        )}
                      </div>
                      <span className="aurora-dim-bar-total">
                        {isCensopas
                          ? percentText(row.unfavorable_pct)
                          : row.mean_score.toFixed(1)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <div className="aurora-card-bi-legend">
                {isCensopas
                  ? BANDS.map((b) => (
                      <span key={b.key}>
                        <span
                          className="aurora-legend-sq"
                          style={{ background: b.color }}
                        />
                        {b.label}
                      </span>
                    ))
                  : 'Puntaje descriptivo 0–100'}
              </div>
            </Card>
            <Card
              title={
                isCensopas
                  ? 'Distribución de dimensión seleccionada'
                  : 'Detalle descriptivo'
              }
            >
              {contextRow ? (
                <>
                  <p className="aurora-bi-help">
                    {contextRow.construct_name} · {activeFilter}
                  </p>
                  {isCensopas ? (
                    <Distribution row={contextRow} />
                  ) : (
                    <strong className="aurora-compact-focusvalue">
                      {contextRow.mean_score.toFixed(1)}
                    </strong>
                  )}
                </>
              ) : (
                <Empty>N/D · Sin distribución publicable</Empty>
              )}
            </Card>
            <Card title="Evolución temporal">
              <div
                className="aurora-compact-views"
                role="group"
                aria-label="Tipo de análisis"
              >
                <button
                  type="button"
                  onClick={() => setAnalysisView('diagnosis')}
                >
                  Diagnóstico
                </button>
                <button
                  type="button"
                  onClick={() => setAnalysisView('heatmap')}
                >
                  Mapa de calor
                </button>
                <button
                  type="button"
                  disabled={!isCensopas || comparing}
                  onClick={() => setAnalysisView('trend')}
                >
                  Evolución
                </button>
              </div>
              {analysisView === 'trend' && isCensopas && !comparing ? (
                <LongitudinalBIWidget
                  projectId={projectId}
                  dimension={focused?.construct_code || 'ALL'}
                />
              ) : (
                <Empty>
                  {comparing
                    ? 'N/D · Evolución por segmento no disponible'
                    : genericMode
                      ? 'N/D · Comparabilidad de este instrumento no disponible'
                      : 'Selecciona Evolución para consultar mediciones equivalentes'}
                </Empty>
              )}
            </Card>
          </div>
          <div className="aurora-analytics-row-2">
            <Card title="Dimensiones y comparaciones">
              {sourceUnavailable ? (
                <Empty>
                  {unitQuery.isError
                    ? 'No se pudieron consultar los segmentos. N/D'
                    : unitQuery.isLoading
                      ? 'Consultando segmentos…'
                      : 'N/D · La corrida del segmento no coincide con los resultados. Actualiza para comparar.'}
                </Empty>
              ) : (
                <div
                  className="overflow-x-auto"
                  role={analysisView === 'heatmap' ? 'group' : undefined}
                  aria-label={
                    analysisView === 'heatmap'
                      ? 'Mapa de calor de dimensiones publicables'
                      : undefined
                  }
                >
                  <p className="aurora-bi-help">
                    {comparing && !selectedUnit
                      ? 'Los gráficos muestran la empresa completa; esta matriz compara unidades por separado, sin agregarlas.'
                      : activeFilter}
                  </p>
                  <table className="aurora-heatmap-table">
                    <thead>
                      <tr>
                        <th scope="col">Dimensión</th>
                        <th scope="col">
                          {isCensopas ? '% desf. empresa' : 'Puntaje'}
                        </th>
                        {unitsVisible.map((u) => (
                          <th scope="col" key={u.id}>
                            {u.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {visibleRows.map((row) => (
                        <tr key={row.construct_code}>
                          <th scope="row">{row.construct_name}</th>
                          <td>
                            {isCensopas
                              ? percentText(row.unfavorable_pct)
                              : row.mean_score.toFixed(1)}
                          </td>
                          {unitsVisible.map((u) => {
                            const c = safeCells.get(
                              row.construct_code + '::' + u.id,
                            );
                            return (
                              <td
                                key={u.id}
                                style={
                                  c && analysisView === 'heatmap'
                                    ? {
                                        background: `rgba(37,99,235,${(c.unfavorable_pct / 100) * 0.6})`,
                                      }
                                    : undefined
                                }
                              >
                                {c ? percentText(c.unfavorable_pct) : 'N/D'}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!visibleRows.length && (
                    <Empty>N/D · Sin resultados publicables</Empty>
                  )}
                  {isCensopas && !comparing && (
                    <p className="aurora-bi-help">
                      Selecciona un tipo de segmento para comparar unidades
                      publicables.
                    </p>
                  )}
                </div>
              )}
            </Card>
            <Card
              title={
                isCensopas
                  ? 'Clasificación por dimensión'
                  : 'Puntajes por dimensión'
              }
            >
              <div className="aurora-persp-card-list">
                {displayedRows.map((row) => (
                  <div className="aurora-persp-item" key={row.construct_code}>
                    <span className="aurora-persp-name">
                      {row.construct_name}
                    </span>
                    <span className="aurora-persp-stat">
                      {isCensopas
                        ? riskLabel(row.collective_classification)
                        : row.mean_score.toFixed(1)}
                    </span>
                  </div>
                ))}
              </div>
              <p className="aurora-bi-help">
                {isCensopas
                  ? 'Clasificación por dimensión, no distribución de personas.'
                  : 'Puntajes descriptivos; no categorías de riesgo.'}
              </p>
            </Card>
            <Card title="Indicadores complementarios">
              <Empty>
                N/D · Indicadores complementarios no disponibles en esta vista
              </Empty>
            </Card>
          </div>
        </div>
        <aside className="aurora-sidebar-analytics-column">
          <Card title="Qué significa">
            {contextRow ? (
              <div className="aurora-compact-insightbody">
                <h4>{contextRow.construct_name}</h4>
                {isCensopas && (
                  <p>
                    Baremo: {contextRow.barem_id ?? 'N/D'} ·{' '}
                    {contextRow.barem_status || 'Estado no disponible'} ·{' '}
                    {contextRow.official_equivalence === true
                      ? 'Equivalencia oficial validada'
                      : 'Equivalencia oficial no acreditada'}
                  </p>
                )}
                {selectedUnit ? (
                  <p>Comparación descriptiva por segmento</p>
                ) : isCensopas && interpretation ? (
                  <p>{interpretation.recommendation}</p>
                ) : (
                  <p>N/D · Sin interpretación metodológica publicada</p>
                )}
              </div>
            ) : (
              <Empty>N/D · Sin resultado seleccionable</Empty>
            )}
          </Card>
          <Card title="Distribución por sexo">
            <Empty>N/D · Sin agregados demográficos publicables</Empty>
          </Card>
        </aside>
      </div>
      <p className="aurora-bi-help">
        Corrida de resultados: {analysisRunId ?? 'N/D'}. La participación
        refleja la captura actual, no la muestra histórica de scoring. N/D: dato
        no disponible o protegido por confidencialidad. Los filtros de dimensión
        y unidad afectan los resultados, no los indicadores de participación del
        estudio.
      </p>
    </div>
  );
}
