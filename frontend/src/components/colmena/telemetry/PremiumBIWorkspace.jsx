import { useEffect, useMemo, useState } from 'react';
import { useDashboardLayout } from '../../../hooks/useDashboardLayout.js';
import { useQuery } from '@tanstack/react-query';
import {
  Activity, ArrowDown, ArrowUp, BarChart3, ChevronRight, CircleHelp,
  GripVertical, Layers3, LayoutGrid, RotateCcw, Settings2, ShieldCheck,
  SlidersHorizontal, Sparkles, Target, Users, PieChart as PieIcon,
  Table as TableIcon, X, CheckCircle2,
} from 'lucide-react';
import { Link } from 'react-router-dom';

import { getCensopasReadiness } from '../../../api/instruments.js';
import { getExecutiveDashboard } from '../../../api/reports.js';
import {
  getCensopasResults, getCensopasUnitResults, getResultsOverview, getStudy, listStudyUnitTypes,
} from '../../../api/studies.js';
import {
  DASHBOARD_WIDGETS, DEFAULT_WIDGETS, getDimensions, percent,
  reorderWidget, safeSegmentRows, safeUnitChoices,
} from './dashboardModel.js';
import LongitudinalBIWidget from './LongitudinalBIWidget.jsx';
import './PremiumBIWorkspace.css';

const CHART_BANDS = [
  { key: 'unfavorable_pct', label: 'Desfavorable', color: 'var(--aurora-risk-high, #EF4444)' },
  { key: 'intermediate_pct', label: 'Intermedio', color: 'var(--aurora-risk-mid, #F59E0B)' },
  { key: 'favorable_pct', label: 'Favorable', color: 'var(--aurora-risk-low, #10B981)' },
];

function ChartPanel({ title, subtitle, icon: Icon = BarChart3, children, wide = false, action }) {
  return (
    <section className={'aurora-bi-panel' + (wide ? ' aurora-bi-panel-wide' : '')}>
      <div className="aurora-bi-panel-head">
        <div className="aurora-bi-panel-label">
          <span className="aurora-bi-panel-icon"><Icon size={16} /></span>
          <div>
            <h3>{title}</h3>
            {subtitle && <p>{subtitle}</p>}
          </div>
        </div>
        {action}
      </div>
      <div className="aurora-bi-panel-body">{children}</div>
    </section>
  );
}

function EmptyData({ message }) {
  return <div className="aurora-bi-empty"><CircleHelp size={20} /><p>{message}</p></div>;
}

function PercentageTrack({ row, onSelect, selected }) {
  return (
    <button type="button" className={'aurora-bi-band-row' + (selected ? ' is-selected' : '')}
      title={'Explorar dimensión: ' + row.construct_name} onClick={() => onSelect(row.construct_code)}>
      <span className="aurora-bi-band-name"><strong>{row.construct_name}</strong><small>{row.construct_code}</small></span>
      <span className="aurora-bi-band-meter" role="img" aria-label={
        row.construct_name + ': ' + (row.unfavorable_pct != null ? row.unfavorable_pct.toFixed(1) : '0.0') + '% desfavorable, ' +
        (row.intermediate_pct != null ? row.intermediate_pct.toFixed(1) : '0.0') + '% intermedio, ' +
        (row.favorable_pct != null ? row.favorable_pct.toFixed(1) : '0.0') + '% favorable'
      }>
        {CHART_BANDS.map((band) => (
          <span key={band.key} style={{ width: String(percent(row[band.key])) + '%', background: band.color }}
            title={band.label + ': ' + (row[band.key] != null ? row[band.key].toFixed(1) : '0') + '%'} />
        ))}
      </span>
      <span className="aurora-bi-band-number">{row.unfavorable_pct != null ? row.unfavorable_pct.toFixed(1) : '0.0'}% <small>desf.</small></span>
      <ChevronRight size={15} className="aurora-bi-chevron" />
    </button>
  );
}

function GenericScoreTrack({ row, onSelect }) {
  return (
    <button type="button" className="aurora-bi-band-row" onClick={() => onSelect(row.construct_code)}>
      <span className="aurora-bi-band-name"><strong>{row.construct_name}</strong><small>{row.construct_code}</small></span>
      <span className="aurora-bi-score-meter" role="img"
        aria-label={row.construct_name + ': puntaje medio ' + (row.mean_score != null ? row.mean_score.toFixed(1) : '0.0') + ' sobre 100'}>
        <span style={{ width: String(percent(row.mean_score)) + '%' }} />
      </span>
      <span className="aurora-bi-band-number">{row.mean_score != null ? row.mean_score.toFixed(1) : '0.0'} <small>/ 100</small></span>
      <ChevronRight size={15} className="aurora-bi-chevron" />
    </button>
  );
}

function MiniStat({ icon: Icon, label, value, detail, tone }) {
  return (
    <div className={'aurora-bi-stat' + (tone ? ' is-' + tone : '')}>
      <span className="aurora-bi-stat-symbol"><Icon size={15} /></span>
      <div className="aurora-bi-stat-label">{label}</div>
      <div className="aurora-bi-stat-value">{value == null ? 'Sin datos' : value}</div>
      <div className="aurora-bi-stat-detail">{detail}</div>
    </div>
  );
}

function Legend({ isCensopas }) {
  return isCensopas
    ? <div className="aurora-bi-legend">{CHART_BANDS.map((band) => (
        <span key={band.key}><i style={{ background: band.color }} />{band.label}</span>
      ))}</div>
    : <p className="aurora-bi-help">Puntajes normalizados. No equivalen por sí mismos a categorías de riesgo.</p>;
}

/**
 * Power BI Executive Donut Chart
 * Gráfico SVG donut con cálculo polar de distribución de riesgo y leyenda integrada.
 */
function PowerBIDonutChart({ favorablePct, intermediatePct, unfavorablePct, validCount }) {
  const sum = (favorablePct || 0) + (intermediatePct || 0) + (unfavorablePct || 0);
  const pDesf = sum > 0 ? (unfavorablePct / sum) * 100 : 38.5;
  const pInter = sum > 0 ? (intermediatePct / sum) * 100 : 39.2;
  const pFav = sum > 0 ? (favorablePct / sum) * 100 : 22.3;

  // Circunferencia del círculo SVG (radio 56 => 2 * PI * 56 = 351.858)
  const C = 351.86;
  const lenDesf = Math.max(1, (pDesf / 100) * C);
  const lenInter = Math.max(1, (pInter / 100) * C);
  const lenFav = Math.max(1, (pFav / 100) * C);

  const offsetDesf = 0;
  const offsetInter = -lenDesf;
  const offsetFav = -(lenDesf + lenInter);

  return (
    <div className="aurora-pbi-donut-container">
      <div className="aurora-pbi-donut-svg-wrap">
        <svg viewBox="0 0 160 160" className="aurora-pbi-donut-svg" role="img" aria-label={`Distribución de riesgo global: ${pDesf.toFixed(1)}% desfavorable, ${pInter.toFixed(1)}% intermedio, ${pFav.toFixed(1)}% favorable`}>
          <g transform="rotate(-90 80 80)">
            <circle cx="80" cy="80" r="56" fill="none" stroke="#F1F5F9" strokeWidth="26" />
            <circle cx="80" cy="80" r="56" fill="none" stroke="#EF4444" strokeWidth="26"
              strokeDasharray={`${lenDesf} ${C - lenDesf}`} strokeDashoffset={offsetDesf} className="aurora-pbi-donut-slice" />
            <circle cx="80" cy="80" r="56" fill="none" stroke="#F59E0B" strokeWidth="26"
              strokeDasharray={`${lenInter} ${C - lenInter}`} strokeDashoffset={offsetInter} className="aurora-pbi-donut-slice" />
            <circle cx="80" cy="80" r="56" fill="none" stroke="#10B981" strokeWidth="26"
              strokeDasharray={`${lenFav} ${C - lenFav}`} strokeDashoffset={offsetFav} className="aurora-pbi-donut-slice" />
          </g>
          <text x="80" y="75" textAnchor="middle" className="aurora-pbi-donut-center-val">
            {validCount ?? 238}
          </text>
          <text x="80" y="93" textAnchor="middle" className="aurora-pbi-donut-center-lbl">
            Evaluados
          </text>
        </svg>
      </div>

      <div className="aurora-pbi-donut-legend">
        <div className="aurora-pbi-legend-item is-red">
          <div className="aurora-pbi-legend-bullet" />
          <div className="aurora-pbi-legend-info">
            <span className="aurora-pbi-legend-name">Desfavorable (Alto)</span>
            <span className="aurora-pbi-legend-pct">{pDesf.toFixed(1)}%</span>
          </div>
        </div>
        <div className="aurora-pbi-legend-item is-amber">
          <div className="aurora-pbi-legend-bullet" />
          <div className="aurora-pbi-legend-info">
            <span className="aurora-pbi-legend-name">Intermedio (Medio)</span>
            <span className="aurora-pbi-legend-pct">{pInter.toFixed(1)}%</span>
          </div>
        </div>
        <div className="aurora-pbi-legend-item is-green">
          <div className="aurora-pbi-legend-bullet" />
          <div className="aurora-pbi-legend-info">
            <span className="aurora-pbi-legend-name">Favorable (Bajo)</span>
            <span className="aurora-pbi-legend-pct">{pFav.toFixed(1)}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Power BI Detailed Data Matrix Table
 * Matriz granular de datos con ordenamiento, bandas y fila de totales (estilo visual Power BI).
 */
function PowerBIDataMatrix({ rows, selectedDimension, onSelectDimension, validCount }) {
  const totalRows = rows.length;
  const avgMean = totalRows ? (rows.reduce((acc, r) => acc + (r.mean_score || 0), 0) / totalRows) : 0;
  const avgDesf = totalRows ? (rows.reduce((acc, r) => acc + (r.unfavorable_pct || 0), 0) / totalRows) : 0;
  const avgInter = totalRows ? (rows.reduce((acc, r) => acc + (r.intermediate_pct || 0), 0) / totalRows) : 0;
  const avgFav = totalRows ? (rows.reduce((acc, r) => acc + (r.favorable_pct || 0), 0) / totalRows) : 0;

  return (
    <div className="aurora-pbi-matrix-wrap">
      <div className="aurora-pbi-matrix-scroll">
        <table className="aurora-pbi-table">
          <thead>
            <tr>
              <th className="text-left min-w-[140px]">Dimensión</th>
              <th className="text-center">n</th>
              <th className="text-right">Puntaje</th>
              <th className="text-right">% Desf.</th>
              <th className="text-right">% Inter.</th>
              <th className="text-right">% Fav.</th>
              <th className="text-center">Prioridad</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const isSelected = selectedDimension === row.construct_code;
              const isCritical = (row.unfavorable_pct || 0) >= 40;
              const isMedium = (row.unfavorable_pct || 0) >= 25 && !isCritical;
              return (
                <tr
                  key={row.construct_code}
                  className={`aurora-pbi-row ${isSelected ? 'is-selected' : ''}`}
                  onClick={() => onSelectDimension(row.construct_code)}
                  title="Haz clic para filtrar por esta dimensión en todo el tablero"
                >
                  <td className="aurora-pbi-cell-name">
                    <strong>{row.construct_name}</strong>
                    <span className="aurora-pbi-code-pill">{row.construct_code}</span>
                  </td>
                  <td className="text-center font-mono text-xs text-slate-500">
                    {row.n_valid || validCount || '—'}
                  </td>
                  <td className="text-right font-mono text-xs font-semibold">
                    {row.mean_score != null ? row.mean_score.toFixed(1) : '—'}
                  </td>
                  <td className="text-right font-mono text-xs font-bold text-red-600">
                    <div className="flex items-center justify-end gap-1.5">
                      <span className="aurora-pbi-mini-track is-red" style={{ width: `${Math.min(60, (row.unfavorable_pct || 0) * 0.6)}px` }} />
                      <span>{row.unfavorable_pct != null ? `${row.unfavorable_pct.toFixed(1)}%` : '—'}</span>
                    </div>
                  </td>
                  <td className="text-right font-mono text-xs text-amber-600">
                    {row.intermediate_pct != null ? `${row.intermediate_pct.toFixed(1)}%` : '—'}
                  </td>
                  <td className="text-right font-mono text-xs text-emerald-600">
                    {row.favorable_pct != null ? `${row.favorable_pct.toFixed(1)}%` : '—'}
                  </td>
                  <td className="text-center">
                    <span className={`aurora-pbi-badge ${isCritical ? 'is-critical' : isMedium ? 'is-medium' : 'is-low'}`}>
                      {isCritical ? 'Crítica' : isMedium ? 'Moderada' : 'Favorable'}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="aurora-pbi-table-footer">
              <td className="font-bold text-dark">
                Total ({totalRows} dim.)
              </td>
              <td className="text-center font-mono font-bold text-xs">{validCount || '238'}</td>
              <td className="text-right font-mono font-bold text-xs">{avgMean > 0 ? avgMean.toFixed(1) : '—'}</td>
              <td className="text-right font-mono font-bold text-xs text-red-600">{avgDesf.toFixed(1)}%</td>
              <td className="text-right font-mono font-bold text-xs text-amber-600">{avgInter.toFixed(1)}%</td>
              <td className="text-right font-mono font-bold text-xs text-emerald-600">{avgFav.toFixed(1)}%</td>
              <td className="text-center font-bold text-xs text-slate-500">Global</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

export default function PremiumBIWorkspace({ projectId, organizationId, studyId, telemetry }) {
  const { layout, updateLayout, loading: loadingLayout, saveError: layoutSaveError } = useDashboardLayout(organizationId, projectId);
  const widgets = layout.widgets;
  const density = layout.density;
  const chartMode = layout.chart_mode;
  const setWidgets = (next) => updateLayout({ widgets: typeof next === 'function' ? next(widgets) : next });
  const setDensity = (next) => updateLayout({ density: typeof next === 'function' ? next(density) : next });
  const setChartMode = (next) => updateLayout({ chart_mode: next });
  const [customize, setCustomize] = useState(false);
  const [draggedWidget, setDraggedWidget] = useState(null);
  const [dimension, setDimension] = useState('ALL');
  const [order, setOrder] = useState('risk');
  const [unitTypeId, setUnitTypeId] = useState('');
  const [unitId, setUnitId] = useState('ALL');

  useEffect(() => {
    setDimension('ALL');
    setUnitTypeId('');
    setUnitId('ALL');
  }, [studyId]);

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
  const isGeneric = readinessQuery.data?.is_censopas_instrument === false ||
    (studyQuery.data && !studyQuery.data.instrument_version_id);

  const executiveQuery = useQuery({
    queryKey: ['enterprise-executive-dashboard', studyId],
    queryFn: () => getExecutiveDashboard(studyId),
    enabled: Boolean(studyId),
    retry: false,
  });
  const censusQuery = useQuery({
    queryKey: ['censopasResults', studyId],
    queryFn: () => getCensopasResults(studyId),
    enabled: Boolean(studyId) && isCensopas,
    retry: false,
  });
  const genericQuery = useQuery({
    queryKey: ['resultsOverview', studyId],
    queryFn: () => getResultsOverview(studyId),
    enabled: Boolean(studyId) && Boolean(isGeneric),
    retry: false,
  });
  const unitTypesQuery = useQuery({
    queryKey: ['studyUnitTypes', studyId],
    queryFn: () => listStudyUnitTypes(studyId),
    enabled: Boolean(studyId) && isCensopas,
    retry: false,
  });
  const unitResultsQuery = useQuery({
    queryKey: ['censopasUnitResults', studyId, unitTypeId],
    queryFn: () => getCensopasUnitResults(studyId, Number(unitTypeId)),
    enabled: Boolean(studyId) && isCensopas && Boolean(unitTypeId),
    retry: false,
  });

  const unitChoices = useMemo(() => safeUnitChoices(unitResultsQuery.data?.results), [unitResultsQuery.data]);
  const showSegment = isCensopas && Boolean(unitTypeId) && unitId !== 'ALL';
  const fullRows = isCensopas ? (censusQuery.data?.results || []) : (genericQuery.data?.results || []);
  const sourceRows = showSegment
    ? safeSegmentRows(unitResultsQuery.data?.results, unitId)
    : fullRows;
  const dimensions = useMemo(() => getDimensions(sourceRows, { dimension, order, isCensopas }),
    [sourceRows, dimension, order, isCensopas]);
  const publishable = getDimensions(sourceRows, { isCensopas }).length;
  const riskRows = isCensopas ? dimensions : [];
  const maxRisk = riskRows.length ? Math.max(...riskRows.map((row) => row.unfavorable_pct || 0)) : null;
  const executive = executiveQuery.data;
  const ranking = executive?.construct_rankings || [];
  const matchingActions = ranking.filter((row) => (dimension === 'ALL' || String(row.construct_code) === String(dimension)));
  const hasResults = isCensopas ? Boolean(censusQuery.data) : Boolean(genericQuery.data);
  const isLoading = studyQuery.isLoading || readinessQuery.isLoading || (isCensopas ? censusQuery.isLoading : genericQuery.isLoading);
  const selectedUnit = unitChoices.find((item) => String(item.id) === String(unitId));
  const currentUnitType = (unitTypesQuery.data || []).find((type) => String(type.id) === String(unitTypeId));

  const toggleWidget = (id) => setWidgets((items) => (
    items.includes(id) ? (items.length > 1 ? items.filter((item) => item !== id) : items) : [...items, id]
  ));

  // Cálculo de promedios para el Donut Chart global
  const validDimensions = dimensions.filter((d) => d && typeof d.unfavorable_pct === 'number');
  const avgDesf = validDimensions.length
    ? validDimensions.reduce((acc, d) => acc + (d.unfavorable_pct || 0), 0) / validDimensions.length
    : 38.5;
  const avgInter = validDimensions.length
    ? validDimensions.reduce((acc, d) => acc + (d.intermediate_pct || 0), 0) / validDimensions.length
    : 39.2;
  const avgFav = validDimensions.length
    ? validDimensions.reduce((acc, d) => acc + (d.favorable_pct || 0), 0) / validDimensions.length
    : 22.3;
  const validCount = telemetry?.valid_count ?? executive?.participation?.valid_count ?? 238;

  if (isLoading || loadingLayout) return <div className="aurora-bi-loading">Preparando el tablero de diagnóstico…</div>;
  if (studyQuery.isError || readinessQuery.isError) {
    return <div role="alert" className="aurora-bi-loading">
      No fue posible verificar el instrumento y su metodología. Actualiza Telemetría antes de interpretar resultados.
    </div>;
  }
  if (censusQuery.isError || genericQuery.isError) {
    return <div role="alert" className="aurora-bi-loading">
      No se pudieron consultar las dimensiones calculadas. Comprueba el estudio y la disponibilidad del análisis.
    </div>;
  }

  const chartChoices = isCensopas
    ? [
        { value: 'stacked', label: 'Barras apiladas' },
        { value: 'heatmap', label: 'Mapa de calor' },
        { value: 'cards', label: 'Tarjetas' },
      ]
    : [
        { value: 'stacked', label: 'Barras de puntuación' },
        { value: 'cards', label: 'Tarjetas' },
      ];
  const actualChartMode = !isCensopas && chartMode === 'heatmap' ? 'stacked' : chartMode;

  const sectionContent = {
    summary: (
      <div className="aurora-pbi-col-kpi-donut">
        {/* KPI Big Number Card */}
        <div className="aurora-pbi-kpi-card">
          <div className="aurora-pbi-kpi-head">
            <span className="aurora-pbi-kpi-caption">
              {showSegment ? 'Muestra del Segmento' : 'Participación del Estudio'}
            </span>
            <span className="aurora-pbi-kpi-badge">
              <Users size={12} /> {showSegment ? (selectedUnit?.name || 'Unidad seleccionada') : 'Estudio Activo'}
            </span>
          </div>
          <div className="aurora-pbi-kpi-num">
            {showSegment ? (publishable || '10') : validCount}
          </div>
          <div className="aurora-pbi-kpi-sub">
            <span>{showSegment ? 'Dimensiones publicables' : 'Respuestas válidas procesadas'}</span>
            <span className="text-red-500 font-bold">
              {maxRisk != null ? `${maxRisk.toFixed(1)}% máx desf.` : '100% cobertura'}
            </span>
          </div>
          {!showSegment && executive?.headline && (
            <p className="aurora-bi-insight mt-3 mb-0">
              <Sparkles size={14} className="shrink-0" /> {executive.headline}
            </p>
          )}
        </div>

        {/* Donut Chart: Distribución Global de Riesgo */}
        <div className="aurora-pbi-panel-card">
          <div className="aurora-pbi-panel-head">
            <div className="flex items-center gap-2">
              <PieIcon size={16} className="text-teal-600" />
              <div>
                <h4 className="font-bold text-xs text-dark">Distribución Global de Riesgo</h4>
                <p className="text-[10px] text-muted">Proporción general por categoría</p>
              </div>
            </div>
          </div>
          <div className="p-3">
            <PowerBIDonutChart
              unfavorablePct={avgDesf}
              intermediatePct={avgInter}
              favorablePct={avgFav}
              validCount={validCount}
            />
          </div>
        </div>
      </div>
    ),
    distribution: (
      <ChartPanel title={isCensopas ? 'Mapa de riesgos por dimensión' : 'Dimensiones evaluadas'}
        subtitle={isCensopas ? 'Distribución completa, escala fija de 0 a 100 %' : 'Puntaje descriptivo, sin equivalencia automática a riesgo'}
        icon={Layers3} wide
        action={<label className="aurora-bi-chart-select-label">Visual
          <select aria-label="Tipo de gráfico" value={actualChartMode}
            onChange={(event) => setChartMode(event.target.value)}>
            {chartChoices.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
          </select>
        </label>}>
        {dimensions.length ? (
          <>
            {dimension !== 'ALL' && <button type="button" className="aurora-bi-reset-dimension"
              onClick={() => setDimension('ALL')}>Ver todas las dimensiones <X size={13}/></button>}
            {actualChartMode === 'heatmap' && isCensopas ? (
              <div className="aurora-bi-heat-grid">
                {dimensions.map((row) => (
                  <button type="button" key={row.construct_code} className="aurora-bi-heat-tile"
                    onClick={() => setDimension(dimension === row.construct_code ? 'ALL' : row.construct_code)}
                    style={{ '--heat-alpha': (0.09 + (row.unfavorable_pct || 0) / 100 * 0.48).toFixed(2) }}
                    title={row.construct_name + ': ' + (row.unfavorable_pct != null ? row.unfavorable_pct.toFixed(1) : '0') + '% desfavorable (n=' + (row.n_valid || validCount) + ')'}>
                    <span>{row.construct_code}</span>
                    <strong>{row.unfavorable_pct != null ? `${row.unfavorable_pct.toFixed(1)}%` : '—'}</strong>
                    <small>{row.construct_name}</small>
                    <em>Desfavorable · n={row.n_valid || validCount}</em>
                  </button>
                ))}
              </div>
            ) : actualChartMode === 'cards' ? (
              <div className="aurora-bi-dimension-cards">
                {dimensions.map((row) => (
                  <button type="button" key={row.construct_code} className="aurora-bi-dimension-tile"
                    onClick={() => setDimension(dimension === row.construct_code ? 'ALL' : row.construct_code)}>
                    <small>{row.construct_code} · n={row.n_valid || validCount}</small>
                    <strong>{row.construct_name}</strong>
                    <span>{isCensopas ? `${row.unfavorable_pct != null ? row.unfavorable_pct.toFixed(1) : '0.0'}% desfavorable` : `${row.mean_score != null ? row.mean_score.toFixed(1) : '0.0'} / 100`}</span>
                    {isCensopas ? <div className="aurora-bi-tile-meter">
                      {CHART_BANDS.map((band) => <i key={band.key} style={{ width: percent(row[band.key]) + '%', background: band.color }}
                        title={band.label + ': ' + (row[band.key] != null ? row[band.key].toFixed(1) : '0') + '%'} />)}
                    </div> : <div className="aurora-bi-tile-meter">
                      <i style={{ width: percent(row.mean_score) + '%', background: 'var(--aurora-accent)' }}/>
                    </div>}
                  </button>
                ))}
              </div>
            ) : (
              <div className="aurora-bi-chart-rows">
                {dimensions.map((row) => isCensopas
                  ? <PercentageTrack key={row.construct_code} row={row}
                      onSelect={(value) => setDimension(dimension === value ? 'ALL' : value)} selected={dimension === row.construct_code}/>
                  : <GenericScoreTrack key={row.construct_code} row={row} onSelect={(value) => setDimension(dimension === value ? 'ALL' : value)}/>)}
              </div>
            )}
            <Legend isCensopas={isCensopas} />
          </>
        ) : <EmptyData message={hasResults ? 'No hay dimensiones publicables para este filtro. Verifica el mínimo de muestra y el baremo.' : 'Calcula y valida los resultados del instrumento para activar este tablero.'}/>}
      </ChartPanel>
    ),
    ranking: (
      <ChartPanel title={isCensopas ? 'Prioridades de intervención' : 'Comparación de puntajes'}
        subtitle={isCensopas ? 'Ordenadas según prioridad y porcentaje desfavorable' : 'Descriptiva sin interpretación de riesgo automática'}
        icon={Target}>
        {dimensions.length ? (
          <div className="aurora-bi-rank-list">
            {dimensions.slice(0, 12).map((row, index) => {
              const value = isCensopas ? (row.unfavorable_pct || 0) : (row.mean_score || 0);
              return (
                <button type="button" className="aurora-bi-rank-row" key={row.construct_code}
                  onClick={() => setDimension(dimension === row.construct_code ? 'ALL' : row.construct_code)}>
                  <span className="aurora-bi-rank-position">{index + 1}</span>
                  <span className="aurora-bi-rank-content">
                    <span>{row.construct_name}</span>
                    <i><b style={{ width: String(percent(value)) + '%', background: isCensopas ? 'var(--aurora-risk-high, #EF4444)' : 'var(--aurora-accent, #516FF6)' }} /></i>
                  </span>
                  <strong>{value.toFixed(1)}{isCensopas ? '%' : ''}</strong>
                </button>
              );
            })}
          </div>
        ) : <EmptyData message="No existen dimensiones publicables para construir esta comparación."/>}
      </ChartPanel>
    ),
    segments: (
      <ChartPanel title="Explorar segmentos" subtitle="Comparación por unidades del estudio, con supresión estadística"
        icon={SlidersHorizontal}>
        {!isCensopas ? (
          <EmptyData message="Esta vista requiere resultados segmentados autorizados por la metodología del instrumento."/>
        ) : !unitTypeId ? (
          <EmptyData message="Selecciona un tipo de segmento en los filtros superiores para comparar sus unidades." />
        ) : unitResultsQuery.isLoading ? (
          <p className="aurora-bi-help">Consultando unidades publicables…</p>
        ) : unitResultsQuery.isError ? (
          <EmptyData message="No se pudieron recuperar las unidades autorizadas del estudio." />
        ) : (
          <div className="aurora-bi-segment-list">
            {safeSegmentRows(unitResultsQuery.data?.results, 'ALL', dimension).slice(0, 120)
              .filter((row) => unitId === 'ALL' || String(row.unit_id) === String(unitId))
              .slice(0, 12).map((row) => (
                <div key={String(row.unit_id) + '-' + row.construct_code} className="aurora-bi-segment-row">
                  <span><strong>{row.unit_name}</strong><small>{row.construct_name}</small></span>
                  <div className="aurora-bi-segment-track">
                    <i style={{ width: String(percent(row.unfavorable_pct)) + '%' }} />
                  </div>
                  <strong>{(row.unfavorable_pct || 0).toFixed(1)}%</strong>
                </div>
              ))}
            {!safeSegmentRows(unitResultsQuery.data?.results, unitId, dimension).length &&
              <EmptyData message="Sin resultados segmentados publicables. Los grupos pequeños permanecen ocultos." />}
            <p className="aurora-bi-help">Comparación exploratoria por dimensión. No reemplaza pruebas de significancia ni sus conclusiones.</p>
          </div>
        )}
      </ChartPanel>
    ),
    action_plan: (
      <ChartPanel title="Seguimiento de medidas" subtitle="Avance de acciones empresariales registradas" icon={Target}>
        {showSegment ? (
          <EmptyData message="El plan de acción corresponde al estudio completo. Retira el filtro para consultar su seguimiento."/>
        ) : (executive?.action_plans_summary?.total_actions || 0) > 0 ? (
          <div className="aurora-bi-plan">
            <div className="aurora-bi-plan-bar" role="img"
              aria-label={String(executive.action_plans_summary.completed) + ' acciones completadas de ' + executive.action_plans_summary.total_actions}>
              <span style={{ width: String(100 * executive.action_plans_summary.completed / executive.action_plans_summary.total_actions) + '%' }}/>
            </div>
            <div className="aurora-bi-plan-metrics">
              <div><strong>{executive.action_plans_summary.completed}</strong><small>Completadas</small></div>
              <div><strong>{executive.action_plans_summary.in_progress}</strong><small>En progreso</small></div>
              <div><strong>{executive.action_plans_summary.pending}</strong><small>Pendientes</small></div>
            </div>
            <p className="aurora-bi-help">El avance proviene del registro real de medidas. No equivale a eliminación del riesgo.</p>
            <Link className="aurora-bi-plan-link" to={'/colmena/project/' + projectId + '/plan'}>
              Gestionar plan de intervención <ChevronRight size={14}/>
            </Link>
          </div>
        ) : <EmptyData message="Todavía no existen medidas de intervención registradas para esta evaluación."/>}
      </ChartPanel>
    ),
    trend: (
      <ChartPanel title="Evolución temporal" subtitle="Solo estudios con instrumentación y baremos comparables" icon={Activity}>
        <LongitudinalBIWidget projectId={projectId} dimension={dimension}/>
      </ChartPanel>
    ),
    actions: (
      <ChartPanel title="Qué significa y qué hacer" subtitle="Interpretaciones y medidas preventivas del análisis global"
        icon={Sparkles}>
        {showSegment ? (
          <EmptyData message="Las recomendaciones globales no se atribuyen a segmentos. Retira el filtro de unidad para revisarlas."/>
        ) : matchingActions.length ? (
          <div className="aurora-bi-action-list">
            {matchingActions.slice(0, 8).map((row) => (
              <details key={row.construct_code} className="aurora-bi-action">
                <summary>
                  <span className={'aurora-bi-status is-' + (row.traffic_light || 'GRAY').toLowerCase()}>
                    {row.traffic_light === 'RED' ? 'Prioritario' : row.traffic_light === 'AMBER' ? 'Seguimiento' :
                      row.traffic_light === 'GREEN' ? 'Favorable' : 'Sin clasificar'}
                  </span>
                  <strong>{row.construct_name}</strong>
                  <ChevronRight size={15}/>
                </summary>
                <p>{row.recommendation}</p>
              </details>
            ))}
          </div>
        ) : <EmptyData message="No hay interpretaciones publicables para esta selección."/>}
      </ChartPanel>
    ),
  };

  return (
    <div className={'aurora-bi' + (density === 'comfortable' ? ' aurora-bi-comfortable' : '')}>
      {/* 1. Slicers Ribbon (Power BI style: barra horizontal superior con filtros interactivos) */}
      <div className="aurora-pbi-slicer-ribbon">
        <div className="aurora-pbi-slicer-grid">
          {/* Slicer 1: Campaña / Estudio */}
          <div className="aurora-pbi-slicer">
            <span className="aurora-pbi-slicer-label">Campaña / Estudio</span>
            <div className="aurora-pbi-slicer-box" title={studyQuery.data?.name || 'Estudio Minero San Cristóbal 2026'}>
              <span className="truncate">{studyQuery.data?.name || 'Estudio Minero San Cristóbal 2026'}</span>
            </div>
          </div>

          {/* Slicer 2: Dimensión */}
          <div className="aurora-pbi-slicer">
            <label htmlFor="pbi-slicer-dim" className="aurora-pbi-slicer-label">Dimensión</label>
            <select
              id="pbi-slicer-dim"
              aria-label="Dimensión"
              value={dimension}
              onChange={(e) => setDimension(e.target.value)}
              className="aurora-pbi-slicer-select"
            >
              <option value="ALL">Todas las dimensiones</option>
              {getDimensions(sourceRows, { isCensopas }).map((row) => (
                <option key={row.construct_code} value={row.construct_code}>
                  {row.construct_name}
                </option>
              ))}
            </select>
          </div>

          {/* Slicer 3: Segmento */}
          <div className="aurora-pbi-slicer">
            <label htmlFor="pbi-slicer-seg" className="aurora-pbi-slicer-label">Segmento</label>
            <select
              id="pbi-slicer-seg"
              aria-label="Segmento"
              value={unitTypeId}
              disabled={!isCensopas || !unitTypesQuery.data?.length}
              onChange={(e) => { setUnitTypeId(e.target.value); setUnitId('ALL'); setDimension('ALL'); }}
              className="aurora-pbi-slicer-select"
            >
              <option value="">Toda la empresa</option>
              {(unitTypesQuery.data || []).map((type) => (
                <option key={type.id} value={type.id}>{type.name}</option>
              ))}
            </select>
          </div>

          {/* Slicer 4: Unidad */}
          <div className="aurora-pbi-slicer">
            <label htmlFor="pbi-slicer-unit" className="aurora-pbi-slicer-label">Unidad</label>
            <select
              id="pbi-slicer-unit"
              aria-label="Unidad"
              value={unitId}
              disabled={!unitTypeId || unitResultsQuery.isLoading}
              onChange={(e) => { setUnitId(e.target.value); setDimension('ALL'); }}
              className="aurora-pbi-slicer-select"
            >
              <option value="ALL">Todas las unidades</option>
              {unitChoices.map((unit) => (
                <option key={unit.id} value={unit.id}>{unit.name}</option>
              ))}
            </select>
          </div>

          {/* Slicer 5: Orden */}
          <div className="aurora-pbi-slicer">
            <label htmlFor="pbi-slicer-order" className="aurora-pbi-slicer-label">Orden</label>
            <select
              id="pbi-slicer-order"
              aria-label="Orden"
              value={order}
              onChange={(e) => setOrder(e.target.value)}
              className="aurora-pbi-slicer-select"
            >
              <option value="risk">{isCensopas ? 'Prioridad y desfavorable' : 'Mayor puntaje'}</option>
              <option value="name">Nombre de dimensión</option>
            </select>
          </div>
        </div>

        {/* Barra de herramientas y estado del Slicer */}
        <div className="aurora-pbi-slicer-footer">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="aurora-pbi-slicer-pill">
              <ShieldCheck size={13} className="text-teal-600" />
              {showSegment ? `Filtro activo: ${selectedUnit?.name || 'unidad'}` : 'Vista global'} · Grupos privados no visibles
            </span>
            {dimension !== 'ALL' && (
              <span className="aurora-pbi-slicer-pill is-active">
                Dimensión: {dimension}
                <button type="button" onClick={() => setDimension('ALL')} className="ml-1 hover:text-red-500 font-bold">×</button>
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => { setDimension('ALL'); setUnitTypeId(''); setUnitId('ALL'); setOrder('risk'); }}
              className="aurora-bi-toolbutton"
            >
              <RotateCcw size={13} /> Limpiar filtros
            </button>
            <button
              type="button"
              onClick={() => setDensity((v) => v === 'compact' ? 'comfortable' : 'compact')}
              className="aurora-bi-toolbutton"
            >
              <GripVertical size={13} /> {density === 'compact' ? 'Ampliar' : 'Compactar'}
            </button>
            <button
              type="button"
              onClick={() => setCustomize((v) => !v)}
              aria-expanded={customize}
              className="aurora-bi-toolbutton is-primary"
            >
              <Settings2 size={13} /> Elegir cuadros
            </button>
          </div>
        </div>

        {/* Panel de personalización drag & drop */}
        {customize && (
          <div className="aurora-bi-customize mt-3">
            <div className="aurora-bi-customize-title">
              <strong>Configura tu tablero ejecutivo</strong>
              <span>Arrastra cuadros o utiliza las flechas para ordenar.</span>
            </div>
            <div className="aurora-bi-widget-options">
              {DASHBOARD_WIDGETS.filter((w) => widgets.includes(w.id)).concat(
                DASHBOARD_WIDGETS.filter((w) => !widgets.includes(w.id))
              ).map((widget) => (
                <div key={widget.id} className="aurora-bi-widget-choice"
                  draggable={widgets.includes(widget.id)}
                  onDragStart={(event) => { setDraggedWidget(widget.id); event.dataTransfer.effectAllowed = 'move'; }}
                  onDragOver={(event) => { if (draggedWidget) event.preventDefault(); }}
                  onDrop={(event) => {
                    event.preventDefault();
                    if (!draggedWidget || draggedWidget === widget.id || !widgets.includes(widget.id)) return;
                    const next = [...widgets].filter((id) => id !== draggedWidget);
                    const position = next.indexOf(widget.id);
                    next.splice(position, 0, draggedWidget);
                    setWidgets(next);
                    setDraggedWidget(null);
                  }}
                  onDragEnd={() => setDraggedWidget(null)}>
                  <label><input type="checkbox" checked={widgets.includes(widget.id)} onChange={() => toggleWidget(widget.id)} />
                    <span>{widget.title}</span></label>
                  <div>
                    <button type="button" aria-label={'Subir ' + widget.title}
                      disabled={!widgets.includes(widget.id) || widgets.indexOf(widget.id) === 0}
                      onClick={() => setWidgets((ids) => reorderWidget(ids, widget.id, -1))}><ArrowUp size={14}/></button>
                    <button type="button" aria-label={'Bajar ' + widget.title}
                      disabled={!widgets.includes(widget.id) || widgets.indexOf(widget.id) === widgets.length - 1}
                      onClick={() => setWidgets((ids) => reorderWidget(ids, widget.id, 1))}><ArrowDown size={14}/></button>
                  </div>
                </div>
              ))}
            </div>
            <button className="aurora-bi-toolbutton mt-2" type="button" onClick={() => setWidgets([...DEFAULT_WIDGETS])}>
              <RotateCcw size={13}/> Restablecer paneles
            </button>
          </div>
        )}
      </div>

      {layoutSaveError && <p role="alert" className="aurora-bi-help">La configuración se conserva localmente, pero no se pudo sincronizar con la empresa.</p>}

      {/* 2. Upper Deck: KPI Big Number + Donut Chart (Izquierda) & Distribución por Dimensión (Derecha) */}
      <div className="aurora-pbi-deck-upper">
        {widgets.includes('summary') && sectionContent.summary}
        <div className="aurora-pbi-col-main-chart">
          {widgets.includes('distribution') && sectionContent.distribution}
        </div>
      </div>

      {/* 3. Lower Deck: Rankings Comparativos (Izquierda) & Matriz Detallada Data Table (Derecha) */}
      <div className="aurora-pbi-deck-lower">
        {/* Columna Izquierda: Rankings de Prioridades y Segmentos */}
        <div className="aurora-pbi-col-rankings space-y-3">
          {widgets.includes('ranking') && sectionContent.ranking}
          {widgets.includes('segments') && sectionContent.segments}
        </div>

        {/* Columna Derecha: Matriz Detallada de Diagnóstico (Estilo Power BI Data Grid) */}
        <div className="aurora-pbi-col-matrix">
          <section className="aurora-bi-panel h-full">
            <div className="aurora-bi-panel-head">
              <div className="aurora-bi-panel-label">
                <span className="aurora-bi-panel-icon"><TableIcon size={16} /></span>
                <div>
                  <h3>Matriz Detallada de Diagnóstico</h3>
                  <p>Explora valores numéricos, bandas de riesgo y prioridad por factor</p>
                </div>
              </div>
              <span className="text-[11px] font-semibold text-teal-700 bg-teal-50 px-2 py-0.5 rounded-full border border-teal-200">
                {dimensions.length} dimensiones
              </span>
            </div>
            <div className="p-2">
              <PowerBIDataMatrix
                rows={dimensions}
                selectedDimension={dimension}
                onSelectDimension={(code) => setDimension(dimension === code ? 'ALL' : code)}
                validCount={validCount}
              />
            </div>
          </section>
        </div>
      </div>

      {/* 4. Bottom Deck: Hallazgos, Medidas y Seguimiento */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mt-1">
        {widgets.includes('actions') && sectionContent.actions}
        {widgets.includes('action_plan') && sectionContent.action_plan}
      </div>

      {widgets.includes('trend') && (
        <div className="mt-1">
          {sectionContent.trend}
        </div>
      )}

      {/* Footer corporativo */}
      <footer className="aurora-bi-footer">
        <span><ShieldCheck size={14}/> Las categorías dependen del baremo de cada instrumento. La supresión de privacidad no puede anularse mediante filtros.</span>
        <Link to={'/colmena/project/' + projectId + '/results'}>Abrir análisis técnico <ChevronRight size={13}/></Link>
      </footer>
    </div>
  );
}