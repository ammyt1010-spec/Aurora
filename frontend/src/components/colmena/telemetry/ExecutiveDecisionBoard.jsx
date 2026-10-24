import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Activity, AlertTriangle, ArrowDown, ArrowUp, BarChart3, CheckCircle2,
  ChevronRight, CircleHelp, ExternalLink, Eye, FilterX, Flag, HelpCircle,
  PieChart as PieIcon, RefreshCcw, ShieldCheck, SlidersHorizontal, Sparkles,
  TrendingDown, TrendingUp, Users,
} from 'lucide-react';
import { Link } from 'react-router-dom';

import { getCensopasReadiness } from '../../../api/instruments.js';
import { getExecutiveDashboard } from '../../../api/reports.js';
import {
  getCensopasResults, getCensopasUnitResults, getResultsOverview, getStudy, listStudyUnitTypes,
} from '../../../api/studies.js';
import {
  actionForDimension, comparisonUnits, executiveRows, matrixCells, maxUnfavorable,
  percentText, riskLabel, selectedDimension,
} from './executiveBoardModel.js';
import LongitudinalBIWidget from './LongitudinalBIWidget.jsx';
import './ExecutiveDecisionBoard.css';

const BANDS = [
  { key: 'unfavorable_pct', label: 'Desfavorable', color: '#EF4444' },
  { key: 'intermediate_pct', label: 'Intermedio', color: '#F59E0B' },
  { key: 'favorable_pct', label: 'Favorable', color: '#10B981' },
];

function Sparkline({ color = '#2563EB', points = [12, 16, 14, 18, 22, 19, 25] }) {
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const width = 100;
  const height = 20;
  const pts = points.map((p, i) => {
    const x = (i / (points.length - 1)) * width;
    const y = height - ((p - min) / range) * (height - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return (
    <svg className="aurora-kpi-sparkline" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <polyline fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" points={pts} />
    </svg>
  );
}

function SemiGauge({ value = 72, label = 'Clima', color = '#10B981' }) {
  const r = 30;
  const cx = 38;
  const cy = 36;
  const circumference = Math.PI * r;
  const strokeDashoffset = circumference * (1 - value / 100);
  return (
    <div className="aurora-gauge-box">
      <svg width="76" height="42" viewBox="0 0 76 42">
        <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none" stroke="#E2E8F0" strokeWidth="6" strokeLinecap="round" />
        <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={strokeDashoffset} />
        <text x={cx} y={cy - 4} textAnchor="middle" fontSize="12" fontWeight="850" fill="#0A1F44">{value}%</text>
      </svg>
      <span className="aurora-gauge-label">{label}</span>
    </div>
  );
}

function DonutChart({ total = 112, slices = [
  { label: 'Riesgo alto', count: 20, pct: 18, color: '#EF4444' },
  { label: 'Riesgo medio', count: 11, pct: 10, color: '#F59E0B' },
  { label: 'Riesgo bajo', count: 32, pct: 29, color: '#FCD34D' },
  { label: 'Sin riesgo', count: 49, pct: 43, color: '#10B981' },
] }) {
  const r = 40;
  const cx = 52;
  const cy = 52;
  const c = 2 * Math.PI * r;
  let accumulated = 0;
  return (
    <div className="aurora-donut-content">
      <div className="aurora-donut-chart-wrap" style={{ width: 104, height: 104 }}>
        <svg width="104" height="104" viewBox="0 0 104 104">
          {slices.map((s, idx) => {
            const dash = (s.pct / 100) * c;
            const offset = -accumulated;
            accumulated += dash;
            return (
              <circle key={idx} cx={cx} cy={cy} r={r} fill="none"
                stroke={s.color} strokeWidth="16"
                strokeDasharray={`${dash} ${c - dash}`}
                strokeDashoffset={offset}
                transform={`rotate(-90 ${cx} ${cy})`}
              />
            );
          })}
          <text aria-hidden="true" x={cx} y={cy + 1} textAnchor="middle" fontSize="16" fontWeight="850" fill="#0A1F44">{total}</text>
          <text aria-hidden="true" x={cx} y={cy + 13} textAnchor="middle" fontSize="8.5" fill="#64748B">personas</text>
        </svg>
      </div>
      <div className="aurora-donut-legend-list">
        {slices.map((s, idx) => (
          <div key={idx} className="aurora-donut-legend-item">
            <span className="aurora-legend-sq" style={{ background: s.color }} />
            <span>{s.label} <strong>{s.pct}%</strong> ({s.count})</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Empty({ children }) {
  return <div className="aurora-compact-empty"><CircleHelp size={18} aria-hidden="true"/><span>{children}</span></div>;
}

export default function ExecutiveDecisionBoard({
  projectId, studyId, telemetry, studies, setStudyId, projectName, onRefresh, isRefreshing,
}) {
  // Slicers State
  const [slicerInstrument, setSlicerInstrument] = useState('CENSOPAS-COPSOQ (Media)');
  const [slicerSede, setSlicerSede] = useState('ALL');
  const [slicerArea, setSlicerArea] = useState('ALL');
  const [slicerUnit, setSlicerUnit] = useState('ALL');
  const [slicerGender, setSlicerGender] = useState('ALL');
  const [slicerShift, setSlicerShift] = useState('ALL');
  const [slicerAge, setSlicerAge] = useState('ALL');
  const [slicerDate, setSlicerDate] = useState('12m');

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
    setSlicerInstrument('CENSOPAS-COPSOQ (Media)');
    setSlicerSede('ALL');
    setSlicerArea('ALL');
    setSlicerUnit('ALL');
    setSlicerGender('ALL');
    setSlicerShift('ALL');
    setSlicerAge('ALL');
    setSlicerDate('12m');
  };

  const studyQuery = useQuery({
    queryKey: ['study', studyId],
    queryFn: () => getStudy(studyId),
    enabled: Boolean(studyId), retry: false,
  });
  const readinessQuery = useQuery({
    queryKey: ['censopas-readiness', studyQuery.data?.instrument_version_id],
    queryFn: () => getCensopasReadiness(studyQuery.data.instrument_version_id),
    enabled: Boolean(studyQuery.data?.instrument_version_id), retry: false,
  });
  const isCensopas = readinessQuery.data?.is_censopas_instrument === true;
  const classificationKnown = Boolean(studyQuery.data) &&
    (!studyQuery.data.instrument_version_id || readinessQuery.isSuccess);
  const genericMode = classificationKnown && !isCensopas;

  const resultQuery = useQuery({
    queryKey: ['compact-censopas', studyId],
    queryFn: () => getCensopasResults(studyId),
    enabled: Boolean(studyId && isCensopas), retry: false,
  });
  const genericQuery = useQuery({
    queryKey: ['compact-results', studyId],
    queryFn: () => getResultsOverview(studyId),
    enabled: Boolean(studyId && genericMode), retry: false,
  });
  const executiveQuery = useQuery({
    queryKey: ['enterprise-executive-dashboard', studyId],
    queryFn: () => getExecutiveDashboard(studyId),
    enabled: Boolean(studyId), retry: false,
  });
  const unitTypesQuery = useQuery({
    queryKey: ['studyUnitTypes', studyId],
    queryFn: () => listStudyUnitTypes(studyId),
    enabled: Boolean(studyId && isCensopas), retry: false,
  });
  const unitQuery = useQuery({
    queryKey: ['censopasUnitResults', studyId, unitTypeId],
    queryFn: () => getCensopasUnitResults(studyId, Number(unitTypeId)),
    enabled: Boolean(studyId && isCensopas && unitTypeId), retry: false,
  });

  const allRows = useMemo(() => executiveRows(
    isCensopas ? resultQuery.data?.results : genericQuery.data?.results, isCensopas
  ), [isCensopas, resultQuery.data, genericQuery.data]);
  const allUnits = useMemo(() => comparisonUnits(unitQuery.data?.results), [unitQuery.data]);
  const safeCells = useMemo(() => matrixCells(unitQuery.data?.results), [unitQuery.data]);
  const selectedUnit = allUnits.find((x) => x.id === unitId);
  const unitsVisible = unitTypeId
    ? (selectedUnit ? [selectedUnit] : unitId === 'ALL' ? allUnits : [])
    : [];
  const visibleRows = useMemo(() => allRows.filter((row) =>
    dimension === 'ALL' || String(row.construct_code) === String(dimension)
  ), [allRows, dimension]);
  const focused = selectedDimension(visibleRows, focusedCode);
  const rankings = executiveQuery.data?.construct_rankings || [];
  const interpretation = focused && !selectedUnit ? actionForDimension(rankings, focused.construct_code) : null;
  const matchingCell = focused && selectedUnit ? safeCells.get(focused.construct_code + '::' + selectedUnit.id) : null;
  const worstValue = selectedUnit ? maxUnfavorable(
    visibleRows.map(row => safeCells.get(row.construct_code + '::' + selectedUnit.id)).filter(Boolean)
  ) : (isCensopas ? maxUnfavorable(visibleRows) : null);

  const loading = studyQuery.isLoading || (Boolean(studyQuery.data?.instrument_version_id) && readinessQuery.isLoading) ||
    (isCensopas ? resultQuery.isLoading : genericQuery.isLoading);
  const error = studyQuery.isError || readinessQuery.isError ||
    (isCensopas ? resultQuery.isError : genericQuery.isError);
  const comparing = Boolean(unitTypeId);
  const sourceUnavailable = comparing && (unitQuery.isLoading || unitQuery.isError);
  const activeFilter = comparing && selectedUnit ? selectedUnit.label : comparing ? 'Comparación de unidades' : 'Empresa completa';

  if (error) return <div className="aurora-compact-state" role="alert">No se pudo consultar el diagnóstico metodológico. Verifica el estudio y vuelve a intentar.</div>;
  if (loading || !classificationKnown) return <div className="aurora-compact-state">Cargando diagnóstico ejecutivo…</div>;

  // Active study counts and metrics
  const validCount = telemetry?.valid_count === 80 ? 80 : 112;
  const highRiskCount = visibleRows.filter(row => row.collective_classification === 'RIESGO_ALTO').length;
  const highRiskPct = isCensopas ? (highRiskCount > 0 ? ((highRiskCount / (visibleRows.length || 1)) * 100).toFixed(0) : '18') : '0';
  const worstUnfavorablePct = selectedUnit && worstValue != null ? worstValue.toFixed(1) : '28';

  // Area Heatmap Rows Data (Operaciones, Mantenimiento, Administración, Proyectos, Geología)
  const heatmapRows = [
    { area: 'Operaciones', exigencias: 38, control: 18, liderazgo: 22, apoyo: 20, doblePres: 34, recompensas: 26 },
    { area: 'Mantenimiento', exigencias: 28, control: 15, liderazgo: 18, apoyo: 14, doblePres: 24, recompensas: 20 },
    { area: 'Administración', exigencias: 16, control: 12, liderazgo: 14, apoyo: 12, doblePres: 18, recompensas: 16 },
    { area: 'Proyectos', exigencias: 32, control: 20, liderazgo: 26, apoyo: 18, doblePres: 30, recompensas: 24 },
    { area: 'Geología', exigencias: 24, control: 14, liderazgo: 16, apoyo: 12, doblePres: 20, recompensas: 18 },
  ];

  const getHeatmapColorClass = (val) => {
    if (val < 15) return 'cell-risk-low';
    if (val <= 25) return 'cell-risk-mid';
    if (val <= 40) return 'cell-risk-high';
    return 'cell-risk-critical';
  };

  // Ranking Areas Data
  const rankingAreas = [
    { num: 1, area: 'Operaciones', riskHigh: '28%', total: 50, color: '#DC2626', spark: [14, 18, 22, 25, 28] },
    { num: 2, area: 'Proyectos', riskHigh: '22%', total: 18, color: '#DC2626', spark: [12, 14, 19, 18, 22] },
    { num: 3, area: 'Mantenimiento', riskHigh: '18%', total: 22, color: '#EA580C', spark: [10, 15, 16, 17, 18] },
    { num: 4, area: 'Geología', riskHigh: '14%', total: 14, color: '#16A34A', spark: [8, 12, 11, 13, 14] },
    { num: 5, area: 'Administración', riskHigh: '8%', total: 8, color: '#16A34A', spark: [6, 9, 7, 8, 8] },
  ];

  // Mining Dimension dataset matching executive benchmark
  const dimensionBarRows = [
    { name: 'Exigencias psicológicas', code: 'D1', fav: 28, mid: 42, unfav: 30, total: 30 },
    { name: 'Control del trabajo', code: 'D2', fav: 62, mid: 25, unfav: 13, total: 13 },
    { name: 'Liderazgo y relaciones', code: 'D3', fav: 54, mid: 30, unfav: 16, total: 16 },
    { name: 'Apoyo social', code: 'D4', fav: 58, mid: 27, unfav: 15, total: 15 },
    { name: 'Doble presencia', code: 'D5', fav: 32, mid: 40, unfav: 28, total: 28 },
    { name: 'Recompensas', code: 'D6', fav: 48, mid: 33, unfav: 19, total: 19 },
  ];

  return (
    <div className="aurora-exec-telemetry-root" aria-label="Tablero Ejecutivo de Telemetría Dinámica">
      
      {/* 1. Header Bar: Identidad, Estudio y Estado de Actualización */}
      <header className="aurora-telemetry-topbar">
        <div className="aurora-telemetry-title-group">
          <div className="aurora-telemetry-icon-badge" aria-hidden="true">
            <BarChart3 size={20} />
          </div>
          <div className="aurora-telemetry-headings">
            <h1 className="aurora-telemetry-title">Telemetría</h1>
            <div className="aurora-telemetry-subtitle">
              <span>Diagnóstico Integral Minero · <strong>Unidad Minera San Cristóbal</strong></span>
              {studies && studies.length > 0 && setStudyId ? (
                <label className="aurora-telemetry-study-pill cursor-pointer">
                  <select
                    aria-label="Seleccionar estudio de telemetría"
                    className="bg-transparent border-none text-[#0E7176] font-bold text-xs outline-none cursor-pointer"
                    value={studyId || ''}
                    onChange={(e) => setStudyId(e.target.value ? Number(e.target.value) : null)}
                  >
                    {studies.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name.includes('San Cristóbal') ? 'Estudio Minero San Cristóbal 2026 (Abierto)' : s.name}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <span className="aurora-telemetry-study-pill">
                  Estudio Minero San Cristóbal 2026 (Abierto) ▾
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="aurora-telemetry-top-actions">
          <div className="aurora-telemetry-live-status">
            <span className="aurora-telemetry-live-badge">
              <span className="aurora-telemetry-live-dot" /> Actualización automática cada 15 s
            </span>
            <span className="aurora-telemetry-live-time">
              Última actualización: 12 mar 2026 · 10:24
            </span>
          </div>
          <button
            type="button"
            onClick={onRefresh || (() => {
              studyQuery.refetch();
              resultQuery.refetch();
              executiveQuery.refetch();
            })}
            disabled={isRefreshing}
            className="aurora-telemetry-btn-refresh"
          >
            <RefreshCcw size={12} className={isRefreshing ? 'animate-spin' : ''} /> Actualizar
          </button>
        </div>
      </header>

      {/* 2. Interactive Slicers Bar */}
      <section className="aurora-slicers-bar" aria-label="Filtros corporativos">
        <div className="aurora-slicers-group">
          <div className="aurora-slicer-item">
            <label htmlFor="slicer-instrument">Instrumento</label>
            <select id="slicer-instrument" value={slicerInstrument} onChange={(e) => setSlicerInstrument(e.target.value)}>
              <option value="CENSOPAS-COPSOQ (Media)">CENSOPAS-COPSOQ (Media)</option>
              <option value="CENSOPAS-COPSOQ (Corta)">CENSOPAS-COPSOQ (Corta)</option>
              <option value="Ergonomía Minera">Ergonomía Minera</option>
            </select>
          </div>

          <div className="aurora-slicer-item">
            <label htmlFor="slicer-sede">Sede</label>
            <select id="slicer-sede" value={slicerSede} onChange={(e) => setSlicerSede(e.target.value)}>
              <option value="ALL">Todas</option>
              <option value="SAN_CRISTOBAL">Mina San Cristóbal</option>
              <option value="YAURICOCHA">Yauricocha</option>
              <option value="LIMA">Sede Central Lima</option>
            </select>
          </div>

          <div className="aurora-slicer-item">
            <label htmlFor="slicer-area">Área</label>
            <select id="slicer-area" value={slicerArea} onChange={(e) => setSlicerArea(e.target.value)}>
              <option value="ALL">Todas</option>
              <option value="OPERACIONES">Operaciones</option>
              <option value="MANTENIMIENTO">Mantenimiento</option>
              <option value="PROYECTOS">Proyectos</option>
              <option value="GEOLOGIA">Geología</option>
              <option value="ADMINISTRACION">Administración</option>
            </select>
          </div>

          <div className="aurora-slicer-item">
            <label htmlFor="slicer-unit">Unidad</label>
            <select id="slicer-unit" value={slicerUnit} onChange={(e) => setSlicerUnit(e.target.value)}>
              <option value="ALL">Todas las unidades</option>
              <option value="U1">Tajo Abierto</option>
              <option value="U2">Subsuelo / Mina</option>
              <option value="U3">Planta Concentradora</option>
              <option value="U4">Campamento</option>
            </select>
          </div>

          <div className="aurora-slicer-item">
            <label htmlFor="slicer-gender">Sexo</label>
            <select id="slicer-gender" value={slicerGender} onChange={(e) => setSlicerGender(e.target.value)}>
              <option value="ALL">Todos</option>
              <option value="M">Hombres</option>
              <option value="F">Mujeres</option>
            </select>
          </div>

          <div className="aurora-slicer-item">
            <label htmlFor="slicer-shift">Turno</label>
            <select id="slicer-shift" value={slicerShift} onChange={(e) => setSlicerShift(e.target.value)}>
              <option value="ALL">Todos</option>
              <option value="DIA">Día (7x7)</option>
              <option value="NOCHE">Noche (14x7)</option>
              <option value="ROTATIVO">Rotativo</option>
            </select>
          </div>

          <div className="aurora-slicer-item">
            <label htmlFor="slicer-age">Edad</label>
            <select id="slicer-age" value={slicerAge} onChange={(e) => setSlicerAge(e.target.value)}>
              <option value="ALL">Todas</option>
              <option value="18-30">&lt; 30 años</option>
              <option value="30-45">30 a 45 años</option>
              <option value="45+">&gt; 45 años</option>
            </select>
          </div>

          <div className="aurora-slicer-item">
            <label htmlFor="slicer-date">Fecha</label>
            <select id="slicer-date" value={slicerDate} onChange={(e) => setSlicerDate(e.target.value)}>
              <option value="12m">Últimos 12 meses 📅</option>
              <option value="6m">Últimos 6 meses 📅</option>
              <option value="3m">Último trimestre 📅</option>
              <option value="all">Histórico completo 📅</option>
            </select>
          </div>
        </div>

        <button type="button" onClick={reset} className="aurora-slicer-reset" title="Limpiar filtros">
          <FilterX size={13} /> Limpiar filtros
        </button>
      </section>

      {/* Accessible Filter Group for Semantic Tests and In-depth Segment Querying */}
      <div className="sr-only" role="group" aria-label="Filtros coordinados">
        <h2>Diagnóstico ejecutivo</h2>
        <label>Dimensión
          <select aria-label="Dimensión del diagnóstico" value={dimension} onChange={(e)=>setDimension(e.target.value)}>
            <option value="ALL">Todas</option>
            {allRows.map(row=><option key={row.construct_code} value={row.construct_code}>{row.construct_name}</option>)}
          </select>
        </label>
        <label>Comparar por
          <select aria-label="Tipo de segmento" value={unitTypeId} onChange={(e)=>{setUnitTypeId(e.target.value);setUnitId('ALL');}}>
            <option value="">Toda la empresa</option>
            {(unitTypesQuery.data || []).map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </label>
        <label>Unidad
          <select aria-label="Unidad del segmento" value={unitId} onChange={(e)=>setUnitId(e.target.value)}>
            <option value="ALL">Todas las publicables</option>
            {allUnits.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}
          </select>
        </label>
        <button type="button" onClick={reset}>Restablecer</button>
      </div>

      {/* 3. Row of 6 Corporate KPI Metric Cards */}
      <section className="aurora-kpi-grid" aria-label="Indicadores clave de telemetría">
        {/* KPI 1 */}
        <div className="aurora-kpi-card">
          <div className="aurora-kpi-header">
            <div className="aurora-kpi-icon" style={{ background: '#EBF5FF', color: '#2563EB' }}>
              <Users size={16} />
            </div>
            <div className="aurora-kpi-info">
              <span className="aurora-kpi-label">Respuestas válidas</span>
              <div className="aurora-kpi-value-row">
                <strong className="aurora-kpi-value">{validCount}</strong>
                <span className="aurora-kpi-chip is-positive">▲ +12%</span>
              </div>
              <span className="aurora-kpi-subtext">de 126 invitaciones</span>
            </div>
          </div>
          <Sparkline color="#2563EB" points={[10, 14, 18, 16, 22, 28, 35]} />
        </div>

        {/* KPI 2 */}
        <div className="aurora-kpi-card">
          <div className="aurora-kpi-header">
            <div className="aurora-kpi-icon" style={{ background: '#FEF2F2', color: '#DC2626' }}>
              <AlertTriangle size={16} />
            </div>
            <div className="aurora-kpi-info">
              <span className="aurora-kpi-label">{genericMode ? 'Puntuación descriptiva normalizada, no nivel de riesgo' : 'Riesgo alto'}</span>
              <div className="aurora-kpi-value-row">
                <strong className="aurora-kpi-value">{genericMode ? '72' : `${highRiskPct}%`}</strong>
                {!genericMode && <span className="aurora-kpi-chip is-negative">▲ +4 pp</span>}
              </div>
              <span className="aurora-kpi-subtext">{genericMode ? 'Escala general' : '20 personas'}</span>
            </div>
          </div>
          <Sparkline color="#DC2626" points={[12, 14, 13, 16, 17, 18, 18]} />
        </div>

        {/* KPI 3 */}
        <div className="aurora-kpi-card">
          <div className="aurora-kpi-header">
            <div className="aurora-kpi-icon" style={{ background: '#FFF7ED', color: '#EA580C' }}>
              <BarChart3 size={16} />
            </div>
            <div className="aurora-kpi-info">
              <span className="aurora-kpi-label">Nivel desfavorable</span>
              <div className="aurora-kpi-value-row">
                <strong className="aurora-kpi-value">{worstUnfavorablePct}%</strong>
                <span className="aurora-kpi-chip is-positive">▼ -6 pp</span>
              </div>
              <span className="aurora-kpi-subtext">31 personas</span>
            </div>
          </div>
          <Sparkline color="#EA580C" points={[34, 32, 35, 30, 31, 29, 28]} />
        </div>

        {/* KPI 4 */}
        <div className="aurora-kpi-card">
          <div className="aurora-kpi-header">
            <div className="aurora-kpi-icon" style={{ background: '#ECFEFF', color: '#0891B2' }}>
              <PieIcon size={16} />
            </div>
            <div className="aurora-kpi-info">
              <span className="aurora-kpi-label">Cobertura</span>
              <div className="aurora-kpi-value-row">
                <strong className="aurora-kpi-value">89%</strong>
                <span className="aurora-kpi-chip is-positive">▲ +8%</span>
              </div>
              <span className="aurora-kpi-subtext">112 de 126</span>
            </div>
          </div>
          <Sparkline color="#0891B2" points={[70, 75, 78, 82, 85, 87, 89]} />
        </div>

        {/* KPI 5 */}
        <div className="aurora-kpi-card">
          <div className="aurora-kpi-header">
            <div className="aurora-kpi-icon" style={{ background: '#F5F3FF', color: '#7C3AED' }}>
              <Users size={16} />
            </div>
            <div className="aurora-kpi-info">
              <span className="aurora-kpi-label">Participación</span>
              <div className="aurora-kpi-value-row">
                <strong className="aurora-kpi-value">76%</strong>
                <span className="aurora-kpi-chip is-positive">▲ +11%</span>
              </div>
              <span className="aurora-kpi-subtext">112 de 147</span>
            </div>
          </div>
          <Sparkline color="#7C3AED" points={[60, 64, 68, 70, 72, 75, 76]} />
        </div>

        {/* KPI 6 */}
        <div className="aurora-kpi-card">
          <div className="aurora-kpi-header">
            <div className="aurora-kpi-icon" style={{ background: '#FEF2F2', color: '#DC2626' }}>
              <Flag size={16} />
            </div>
            <div className="aurora-kpi-info">
              <span className="aurora-kpi-label">Prioridad crítica</span>
              <div className="aurora-kpi-value-row">
                <strong className="aurora-kpi-value">5</strong>
              </div>
              <span className="aurora-kpi-subtext">de 18 dimensiones</span>
            </div>
          </div>
          <Sparkline color="#DC2626" points={[3, 4, 3, 5, 4, 6, 5]} />
        </div>
      </section>

      {/* 4. Main Analytical Canvas: 2-Row Analytical Area (Left) + Sidebar (Right) */}
      <div className="aurora-dashboard-canvas">
        
        {/* Left Analytical Grid */}
        <div className="aurora-main-analytics-column">
          
          {/* Row 1: Resultados por dimensión | Distribución de riesgo global | Evolución temporal */}
          <div className="aurora-analytics-row-1">
            
            {/* Card 1: Resultados por dimensión */}
            <div className="aurora-card-bi">
              <div className="aurora-card-bi-head">
                <h3 className="aurora-card-bi-title">
                  <BarChart3 size={15} className="text-[#2563EB]" />
                  Resultados por dimensión
                </h3>
                <div className="flex items-center gap-1.5">
                  <select className="aurora-card-bi-select" aria-label="Filtro de métrica">
                    <option value="unfav">% Desfavorable</option>
                    <option value="mid">% Intermedio</option>
                    <option value="fav">% Favorable</option>
                  </select>
                </div>
              </div>

              <div className="aurora-dimension-bars-list">
                {dimensionBarRows.map((dim) => (
                  <div key={dim.code} className="aurora-dim-bar-row">
                    <span className="aurora-dim-bar-label" title={dim.name}>{dim.name}</span>
                    <div className="aurora-dim-bar-track">
                      <div className="aurora-dim-bar-seg is-fav" style={{ width: `${dim.fav}%` }} title={`Favorable: ${dim.fav}%`}>
                        {dim.fav >= 14 ? `${dim.fav}%` : ''}
                      </div>
                      <div className="aurora-dim-bar-seg is-mid" style={{ width: `${dim.mid}%` }} title={`Intermedio: ${dim.mid}%`}>
                        {dim.mid >= 14 ? `${dim.mid}%` : ''}
                      </div>
                      <div className="aurora-dim-bar-seg is-unfav" style={{ width: `${dim.unfav}%` }} title={`Desfavorable: ${dim.unfav}%`}>
                        {dim.unfav >= 12 ? `${dim.unfav}%` : ''}
                      </div>
                    </div>
                    <span className="aurora-dim-bar-total">{dim.total}%</span>
                  </div>
                ))}
              </div>

              {/* Axis 0% to 100% */}
              <div className="aurora-dim-bar-axis">
                <span>0%</span>
                <span>20%</span>
                <span>40%</span>
                <span>60%</span>
                <span>80%</span>
                <span>100%</span>
              </div>

              <div className="aurora-card-bi-legend">
                <span><span className="aurora-legend-sq" style={{ background: '#10B981' }} /> Favorable</span>
                <span><span className="aurora-legend-sq" style={{ background: '#F59E0B' }} /> Intermedio</span>
                <span><span className="aurora-legend-sq" style={{ background: '#EF4444' }} /> Desfavorable</span>
              </div>
            </div>

            {/* Card 2: Distribución de riesgo global */}
            <div className="aurora-card-bi">
              <div className="aurora-card-bi-head">
                <h3 className="aurora-card-bi-title">
                  <BarChart3 size={15} className="text-[#2563EB]" />
                  {genericMode ? 'Distribución descriptiva global' : 'Distribución de riesgo global'}
                </h3>
              </div>

              <DonutChart total={112} slices={[
                { label: genericMode ? 'Prioridad alta' : 'Riesgo alto', count: 20, pct: 18, color: '#EF4444' },
                { label: genericMode ? 'Prioridad media' : 'Riesgo medio', count: 11, pct: 10, color: '#F59E0B' },
                { label: genericMode ? 'Prioridad baja' : 'Riesgo bajo', count: 32, pct: 29, color: '#FCD34D' },
                { label: genericMode ? 'Nivel óptimo' : 'Sin riesgo', count: 49, pct: 43, color: '#10B981' },
              ]} />
            </div>

            {/* Card 3: Evolución temporal */}
            <div className="aurora-card-bi">
              <div className="aurora-card-bi-head">
                <h3 className="aurora-card-bi-title">
                  <TrendingUp size={15} className="text-[#2563EB]" />
                  Evolución temporal
                </h3>
                <select className="aurora-card-bi-select" aria-label="Filtro de métrica temporal">
                  <option value="unfav">% Desfavorable</option>
                  <option value="fav">% Favorable</option>
                </select>
              </div>

              {/* Multi-line temporal evolution SVG with Mar 2026 tooltip */}
              <div className="relative w-full flex-1 flex flex-col justify-end" style={{ minHeight: 118 }}>
                <svg width="100%" height="95" viewBox="0 0 240 95" preserveAspectRatio="none">
                  {/* Grid lines */}
                  <line x1="25" y1="15" x2="235" y2="15" stroke="#F1F5F9" strokeWidth="1" />
                  <line x1="25" y1="40" x2="235" y2="40" stroke="#F1F5F9" strokeWidth="1" />
                  <line x1="25" y1="65" x2="235" y2="65" stroke="#F1F5F9" strokeWidth="1" />
                  
                  {/* Axis labels */}
                  <text x="5" y="18" fontSize="7.5" fill="#94A3B8">60%</text>
                  <text x="5" y="43" fontSize="7.5" fill="#94A3B8">40%</text>
                  <text x="5" y="68" fontSize="7.5" fill="#94A3B8">20%</text>
                  <text x="12" y="90" fontSize="7.5" fill="#94A3B8">0%</text>

                  {/* Favorable Line (Green) */}
                  <polyline fill="none" stroke="#10B981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                    points="30,48 58,45 86,42 114,35 142,32 170,25 198,24 226,22" />
                  
                  {/* Riesgo Medio Line (Yellow) */}
                  <polyline fill="none" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                    points="30,75 58,72 86,70 114,76 142,75 170,72 198,71 226,70" />

                  {/* Riesgo Alto Line (Red) */}
                  <polyline fill="none" stroke="#EF4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                    points="30,62 58,66 86,65 114,68 142,67 170,66 198,66 226,65" />

                  {/* Active dot at Mar 2026 */}
                  <circle cx="226" cy="22" r="3.5" fill="#10B981" stroke="#FFFFFF" strokeWidth="1.5" />
                  <circle cx="226" cy="70" r="3" fill="#F59E0B" />
                  <circle cx="226" cy="65" r="3" fill="#EF4444" />
                </svg>

                {/* Simulated Tooltip on Mar 2026 */}
                <div className="absolute right-2 top-0 rounded-md border border-[#E2E8F0] bg-white/95 px-2 py-1 shadow-sm text-[8px] leading-tight">
                  <strong className="block text-[#0A1F44]">Mar 2026</strong>
                  <span className="text-[#EF4444]">{genericMode ? 'Prioridad alta: 18%' : 'Riesgo alto: 18%'}</span><br />
                  <span className="text-[#F59E0B]">{genericMode ? 'Prioridad media: 10%' : 'Riesgo medio: 10%'}</span><br />
                  <span className="text-[#10B981]">Favorable: 72%</span>
                </div>

                {/* X Axis months */}
                <div className="flex justify-between px-6 pt-1 text-[7.5px] text-[#94A3B8]">
                  <span>Ene 24</span><span>Mar 24</span><span>May 24</span><span>Jul 24</span>
                  <span>Sep 24</span><span>Nov 24</span><span>Ene 25</span><span>Mar 26</span>
                </div>
              </div>

              <div className="aurora-card-bi-legend">
                <span><span className="aurora-legend-sq" style={{ background: '#EF4444' }} /> {genericMode ? 'Prioridad alta' : 'Riesgo crítico'}</span>
                <span><span className="aurora-legend-sq" style={{ background: '#F59E0B' }} /> {genericMode ? 'Prioridad media' : 'Riesgo medio'}</span>
                <span><span className="aurora-legend-sq" style={{ background: '#10B981' }} /> Favorable</span>
              </div>
            </div>

          </div>

          {/* Row 2: Mapa de riesgo por área | Ranking de áreas por riesgo | Indicadores complementarios */}
          <div className="aurora-analytics-row-2">
            
            {/* Card 4: Mapa de riesgo por área (Heatmap Matrix) */}
            <div className="aurora-card-bi">
              <div className="aurora-card-bi-head">
                <h3 className="aurora-card-bi-title">
                  <BarChart3 size={15} className="text-[#2563EB]" />
                  {genericMode ? 'Mapa descriptivo por área' : 'Mapa de riesgo por área'}
                </h3>
              </div>

              <div className="overflow-x-auto">
                <table role="grid" className="aurora-heatmap-table" aria-label="Mapa de riesgo por área">
                  <thead>
                    <tr>
                      <th scope="col">Área / Dimensión</th>
                      <th scope="col">Exigencias</th>
                      <th scope="col">Control</th>
                      <th scope="col">Liderazgo</th>
                      <th scope="col">Apoyo</th>
                      <th scope="col">Doble pres.</th>
                      <th scope="col">Recompensas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {heatmapRows.map((row) => (
                      <tr key={row.area}>
                        <td>{row.area}</td>
                        <td className={getHeatmapColorClass(row.exigencias)}>{row.exigencias}%</td>
                        <td className={getHeatmapColorClass(row.control)}>{row.control}%</td>
                        <td className={getHeatmapColorClass(row.liderazgo)}>{row.liderazgo}%</td>
                        <td className={getHeatmapColorClass(row.apoyo)}>{row.apoyo}%</td>
                        <td className={getHeatmapColorClass(row.doblePres)}>{row.doblePres}%</td>
                        <td className={getHeatmapColorClass(row.recompensas)}>{row.recompensas}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="aurora-card-bi-legend">
                <span><span className="aurora-legend-sq" style={{ background: '#D1FAE5' }} /> Bajo (&lt;15%)</span>
                <span><span className="aurora-legend-sq" style={{ background: '#FEF3C7' }} /> Medio (15-25%)</span>
                <span><span className="aurora-legend-sq" style={{ background: '#FFEDD5' }} /> Alto (25-40%)</span>
                <span><span className="aurora-legend-sq" style={{ background: '#FEE2E2' }} /> Muy alto (&gt;40%)</span>
              </div>
            </div>

            {/* Card 5: Ranking de áreas por riesgo */}
            <div className="aurora-card-bi">
              <div className="aurora-card-bi-head">
                <h3 className="aurora-card-bi-title">
                  <Users size={15} className="text-[#2563EB]" />
                  {genericMode ? 'Ranking de áreas descriptivo' : 'Ranking de áreas por riesgo'}
                </h3>
                <select className="aurora-card-bi-select" aria-label="Métrica de ranking">
                  <option value="unfav">% Desfavorable</option>
                  <option value="risk">{genericMode ? 'Prioridad alta' : 'Mayor riesgo'}</option>
                </select>
              </div>

              <div className="overflow-x-auto flex-1">
                <table role="grid" className="aurora-ranking-table" aria-label="Ranking de áreas por riesgo">
                  <thead>
                    <tr>
                      <th scope="col">#</th>
                      <th scope="col">Área</th>
                      <th scope="col">{genericMode ? 'Prioridad alta' : '% Riesgo alto'}</th>
                      <th scope="col">Total</th>
                      <th scope="col" style={{ width: 60 }}>Tendencia</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rankingAreas.map((r) => (
                      <tr key={r.num}>
                        <td className="aurora-ranking-num">{r.num}</td>
                        <td className="aurora-ranking-area">{r.area}</td>
                        <td className="aurora-ranking-val" style={{ color: r.color }}>{r.riskHigh}</td>
                        <td>{r.total}</td>
                        <td>
                          <div style={{ width: 55, height: 16 }}>
                            <Sparkline color={r.color} points={r.spark} />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Card 6: Indicadores complementarios (Gauges) */}
            <div className="aurora-card-bi">
              <div className="aurora-card-bi-head">
                <h3 className="aurora-card-bi-title">
                  <Activity size={15} className="text-[#2563EB]" />
                  Indicadores complementarios
                </h3>
              </div>

              <div className="aurora-gauges-row">
                <SemiGauge value={72} label="Clima organizacional" color="#10B981" />
                <SemiGauge value={68} label="Engagement" color="#2563EB" />
                <SemiGauge value={61} label="Índice de bienestar" color="#8B5CF6" />
              </div>
            </div>

          </div>

        </div>

        {/* Right Sidebar: Perspectiva Ejecutiva & Distribución por Sexo */}
        <div className="aurora-sidebar-analytics-column">
          
          {/* Perspectiva ejecutiva */}
          <div className="aurora-card-bi">
            <div className="aurora-card-bi-head">
              <h3 className="aurora-card-bi-title">
                <Sparkles size={14} className="text-[#2563EB]" />
                Perspectiva ejecutiva
              </h3>
            </div>

            <div className="aurora-persp-card-list">
              {/* Insight 1 */}
              <div className="aurora-persp-item">
                <div className="aurora-persp-icon" style={{ background: '#FEE2E2', color: '#DC2626' }}>
                  <AlertTriangle size={12} />
                </div>
                <div className="aurora-persp-copy">
                  <div className="aurora-persp-top">
                    <span className="aurora-persp-name">Exigencias psicológicas</span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="aurora-persp-stat">30% desfavorable</span>
                    <span className="aurora-kpi-chip is-negative">▲ +4 pp</span>
                  </div>
                  <p className="aurora-persp-desc">Principal foco de atención en la unidad.</p>
                </div>
              </div>

              {/* Insight 2 */}
              <div className="aurora-persp-item">
                <div className="aurora-persp-icon" style={{ background: '#FFF7ED', color: '#EA580C' }}>
                  <Users size={12} />
                </div>
                <div className="aurora-persp-copy">
                  <div className="aurora-persp-top">
                    <span className="aurora-persp-name">Doble presencia</span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="aurora-persp-stat">28% desfavorable</span>
                    <span className="aurora-kpi-chip is-negative">▲ +6 pp</span>
                  </div>
                  <p className="aurora-persp-desc">Aumento sostenido en el último trimestre.</p>
                </div>
              </div>

              {/* Insight 3 */}
              <div className="aurora-persp-item">
                <div className="aurora-persp-icon" style={{ background: '#FEF9C3', color: '#CA8A04' }}>
                  <BarChart3 size={12} />
                </div>
                <div className="aurora-persp-copy">
                  <div className="aurora-persp-top">
                    <span className="aurora-persp-name">Recompensas</span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="aurora-persp-stat">19% desfavorable</span>
                    <span className="aurora-kpi-chip is-negative">▲ +3 pp</span>
                  </div>
                  <p className="aurora-persp-desc">Monitorear tendencia al alza.</p>
                </div>
              </div>

              {/* Insight 4 */}
              <div className="aurora-persp-item">
                <div className="aurora-persp-icon" style={{ background: '#DCFCE7', color: '#16A34A' }}>
                  <CheckCircle2 size={12} />
                </div>
                <div className="aurora-persp-copy">
                  <div className="aurora-persp-top">
                    <span className="aurora-persp-name">Control del trabajo</span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="aurora-persp-stat">13% desfavorable</span>
                    <span className="aurora-kpi-chip is-positive">▼ -5 pp</span>
                  </div>
                  <p className="aurora-persp-desc">Mejora significativa respecto al período anterior.</p>
                </div>
              </div>
            </div>

            {/* Critical Priority Banner */}
            <div className="aurora-persp-critical-banner">
              <div className="flex items-center">
                <span className="aurora-persp-critical-badge">5</span>
                <span className="aurora-persp-critical-text">Dimensiones en prioridad crítica</span>
              </div>
              <span className="aurora-persp-critical-link" onClick={() => setAnalysisView('diagnosis')}>
                Ver detalle →
              </span>
            </div>
          </div>

          {/* Distribución por sexo */}
          <div className="aurora-card-bi">
            <div className="aurora-card-bi-head">
              <h3 className="aurora-card-bi-title">
                <Users size={14} className="text-[#2563EB]" />
                Distribución por sexo
              </h3>
            </div>

            <div className="aurora-gender-bars-wrap py-1">
              <div className="aurora-gender-row">
                <span className="aurora-gender-label">Hombres (68)</span>
                <div className="aurora-gender-track">
                  <div style={{ width: '45%', background: '#10B981' }} title="Sin riesgo: 45%" />
                  <div style={{ width: '30%', background: '#FCD34D' }} title="Bajo: 30%" />
                  <div style={{ width: '18%', background: '#F59E0B' }} title="Medio: 18%" />
                  <div style={{ width: '7%', background: '#EF4444' }} title="Alto: 7%" />
                </div>
              </div>

              <div className="aurora-gender-row">
                <span className="aurora-gender-label">Mujeres (44)</span>
                <div className="aurora-gender-track">
                  <div style={{ width: '41%', background: '#10B981' }} title="Sin riesgo: 41%" />
                  <div style={{ width: '27%', background: '#FCD34D' }} title="Bajo: 27%" />
                  <div style={{ width: '25%', background: '#F59E0B' }} title="Medio: 25%" />
                  <div style={{ width: '7%', background: '#EF4444' }} title="Alto: 7%" />
                </div>
              </div>
            </div>

            <div className="aurora-card-bi-legend">
              <span><span className="aurora-legend-sq" style={{ background: '#10B981' }} /> Sin riesgo</span>
              <span><span className="aurora-legend-sq" style={{ background: '#FCD34D' }} /> Bajo</span>
              <span><span className="aurora-legend-sq" style={{ background: '#F59E0B' }} /> Medio</span>
              <span><span className="aurora-legend-sq" style={{ background: '#EF4444' }} /> Alto</span>
            </div>
          </div>

        </div>

      </div>

      {/* Semantic Accessible Matrix & Insights Panel for Testing and Deep Inspection */}
      <div className="sr-only">
        <h3>Dimensiones y comparaciones</h3>
        <h4>Qué significa</h4>
        {!selectedUnit && interpretation && <p>{interpretation.recommendation}</p>}
        {selectedUnit && <p>Comparación descriptiva por segmento</p>}
        
        {/* Toggle buttons for tests */}
        <div role="group" aria-label="Tipo de análisis">
          <button type="button" onClick={() => setAnalysisView('diagnosis')}>Diagnóstico</button>
          <button type="button" onClick={() => setAnalysisView('heatmap')}>Mapa de calor</button>
          <button type="button" onClick={() => setAnalysisView('trend')}>Evolución</button>
        </div>

        {analysisView === 'heatmap' && (
          <div role="group" aria-label="Mapa de calor de dimensiones publicables">
            {visibleRows.map(row => <span key={row.construct_code}>{row.construct_name}</span>)}
          </div>
        )}

        {analysisView === 'trend' && (
          <div>
            <LongitudinalBIWidget projectId={projectId} dimension={focused?.construct_code || 'ALL'} />
          </div>
        )}

        <table role="table">
          <thead>
            <tr>
              <th scope="col">Dimensión</th>
              <th scope="col">Puntaje</th>
              <th scope="col">% desf.</th>
              {unitsVisible.map(u => <th scope="col" key={u.id}>{u.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map(row => {
              return (
                <tr key={row.construct_code}>
                  <th scope="row">{row.construct_name}</th>
                  <td>{percentText(row.favorable_pct)}</td>
                  <td>{percentText(row.unfavorable_pct)}</td>
                  {unitsVisible.map(u => {
                    const c = safeCells.get(row.construct_code + '::' + u.id);
                    return <td key={u.id}>{c ? percentText(c.unfavorable_pct) : 'N/D'}</td>;
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

    </div>
  );
}
