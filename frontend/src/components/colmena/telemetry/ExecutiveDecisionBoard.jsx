import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, BarChart3, RefreshCcw, RotateCcw, ShieldCheck, Users } from 'lucide-react';
import { getCensopasReadiness } from '../../../api/instruments.js';
import { getExecutiveDashboard } from '../../../api/reports.js';
import { getCensopasAreaResults, getCensopasResults, getCensopasSexResults, getResultsOverview, getStudy } from '../../../api/studies.js';
import { executiveRows, percentText, riskLabel } from './executiveBoardModel.js';
import { dimensionComparisons, filteredDimensionRows, segmentOptions } from './segmentDashboardModel.js';
import './ExecutiveDecisionBoard.css';

const BANDS = [
  { key: 'favorable_pct', label: 'Favorable', color: '#23bd99' },
  { key: 'intermediate_pct', label: 'Intermedio', color: '#f3b84d' },
  { key: 'unfavorable_pct', label: 'Desfavorable', color: '#f2707a' },
];

function Metric({ icon: Icon, label, value, detail, tone = 'blue' }) {
  return <div className={`aurora-liquid-metric is-${tone}`}>
    <span className="aurora-liquid-metric-icon"><Icon size={19} aria-hidden="true" /></span>
    <div><span className="aurora-liquid-metric-label">{label}</span><strong>{value}</strong><small>{detail}</small></div>
  </div>;
}

export default function ExecutiveDecisionBoard({ projectId, studyId, telemetry, studies, setStudyId, projects, onProjectChange, onRefresh, isRefreshing, technicalControl }) {
  const [dimensionCode, setDimensionCode] = useState(null);
  const [segmentMode, setSegmentMode] = useState('area');
  const [selectedSegmentId, setSelectedSegmentId] = useState('ALL');
  useEffect(() => { setDimensionCode(null); setSegmentMode('area'); setSelectedSegmentId('ALL'); }, [studyId]);

  const studyQuery = useQuery({ queryKey: ['study', studyId], queryFn: () => getStudy(studyId), enabled: Boolean(studyId), retry: false });
  const readinessQuery = useQuery({
    queryKey: ['censopas-readiness', studyQuery.data?.instrument_version_id],
    queryFn: () => getCensopasReadiness(studyQuery.data.instrument_version_id),
    enabled: Boolean(studyQuery.data?.instrument_version_id), retry: false,
  });
  const classified = Boolean(studyQuery.data) && (!studyQuery.data.instrument_version_id || readinessQuery.isSuccess);
  const isCensopas = readinessQuery.data?.is_censopas_instrument === true;
  const resultsQuery = useQuery({
    queryKey: ['liquid-censopas', studyId], queryFn: () => getCensopasResults(studyId),
    enabled: Boolean(studyId && isCensopas), retry: false, refetchInterval: 15000,
  });
  const genericQuery = useQuery({
    queryKey: ['liquid-results', studyId], queryFn: () => getResultsOverview(studyId),
    enabled: Boolean(studyId && classified && !isCensopas), retry: false, refetchInterval: 15000,
  });
  const executiveQuery = useQuery({
    queryKey: ['enterprise-executive-dashboard', studyId], queryFn: () => getExecutiveDashboard(studyId),
    enabled: Boolean(studyId), retry: false, refetchInterval: 15000,
  });
  const areaQuery = useQuery({
    queryKey: ['censopasAreaResults', studyId],
    queryFn: () => getCensopasAreaResults(studyId),
    enabled: Boolean(studyId && isCensopas), retry: false, refetchInterval: 15000,
  });
  const sexQuery = useQuery({
    queryKey: ['censopasSexResults', studyId],
    queryFn: () => getCensopasSexResults(studyId),
    enabled: Boolean(studyId && isCensopas), retry: false, refetchInterval: 15000,
  });

  const baseRows = useMemo(() => executiveRows(isCensopas ? resultsQuery.data?.results : genericQuery.data?.results, isCensopas),
    [isCensopas, resultsQuery.data, genericQuery.data]);
  const areaOptions = useMemo(() => segmentOptions(areaQuery.data?.results), [areaQuery.data]);
  const sexOptions = useMemo(() => segmentOptions(sexQuery.data?.results), [sexQuery.data]);
  const segmentResults = segmentMode === 'sex' ? sexQuery.data?.results : areaQuery.data?.results;
  const choices = segmentMode === 'sex' ? sexOptions : areaOptions;
  const selectedSegment = choices.find((choice) => choice.id === selectedSegmentId);
  const rows = useMemo(() => isCensopas ? filteredDimensionRows(baseRows, segmentResults, selectedSegmentId) : baseRows,
    [isCensopas, baseRows, segmentResults, selectedSegmentId]);
  const focused = rows.find((row) => row.construct_code === dimensionCode) || rows[0];
  const focusedBase = baseRows.find((row) => row.construct_code === focused?.construct_code);
  const focusValue = focused?.suppressed ? null : focused;
  const comparisons = useMemo(() => dimensionComparisons(segmentResults, focused?.construct_code),
    [segmentResults, focused?.construct_code]);
  const valid = telemetry?.valid_count ?? executiveQuery.data?.participation?.valid_count;
  const invited = telemetry?.invited_count;
  const completed = telemetry?.completed_count;
  const validRate = Number.isFinite(valid) && Number.isFinite(invited) && invited > 0 ? (valid / invited) * 100 : null;
  const publishable = rows.filter((row) => !row.suppressed).length;
  const critical = rows.filter((row) => !row.suppressed && row.collective_classification === 'RIESGO_ALTO').length;
  const maxUnfavorable = rows.filter((row) => !row.suppressed && Number.isFinite(row.unfavorable_pct))
    .reduce((maximum, row) => Math.max(maximum, row.unfavorable_pct), -1);
  const selectedStudy = studies?.find((study) => String(study.id) === String(studyId));
  const instrumentName = telemetry?.instrument_name || executiveQuery.data?.instrument_name || 'Instrumento en evaluación';
  const instrumentVersion = telemetry?.instrument_version_code || '';
  const instrumentCounts = readinessQuery.data?.actual;
  const versionLabel = readinessQuery.data?.version_kind === 'SHORT' ? 'Versión corta'
    : readinessQuery.data?.version_kind === 'MEDIUM' ? 'Versión media' : instrumentVersion;
  const loading = studyQuery.isLoading || (studyQuery.data?.instrument_version_id && readinessQuery.isLoading) ||
    (isCensopas ? resultsQuery.isLoading : genericQuery.isLoading);
  const error = studyQuery.isError || readinessQuery.isError || (isCensopas ? resultsQuery.isError : genericQuery.isError);
  const comparisonQuery = segmentMode === 'sex' ? sexQuery : areaQuery;

  if (error) return <div className="aurora-compact-state" role="alert">No se pudo consultar el diagnóstico metodológico. Verifica el estudio y vuelve a intentar.</div>;
  if (loading || !classified) return <div className="aurora-compact-state">Cargando dimensiones del instrumento…</div>;

  return <div className="aurora-liquid" aria-label="Telemetría del instrumento">
    <header className="aurora-liquid-head">
      <div className="aurora-liquid-heading"><span className="aurora-liquid-emblem"><Activity size={23} aria-hidden="true" /></span>
        <div><span className="aurora-liquid-eyebrow">PASO 2 DE 3 · RESPUESTAS</span><h1>{instrumentName}</h1>
          <p>{versionLabel}{Number.isFinite(instrumentCounts?.questions) ? ` · ${instrumentCounts.questions} preguntas` : ''}
            {Number.isFinite(instrumentCounts?.scored) ? ` · ${instrumentCounts.scored} puntuables` : ''}
            {studies?.length <= 1 && selectedStudy?.name ? ` · ${selectedStudy.name}` : ''}</p></div></div>
      <div className="aurora-liquid-actions">
        {technicalControl}
        {projects?.length > 1 && onProjectChange && <select aria-label="Seleccionar evaluación empresarial" value={projectId}
          onChange={(event) => onProjectChange(Number(event.target.value))}>
          {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>}
        {studies?.length > 1 && setStudyId && <select aria-label="Seleccionar estudio de telemetría" value={studyId}
          onChange={(event) => setStudyId(Number(event.target.value))}>
          {studies.map((study) => <option key={study.id} value={study.id}>{study.name}</option>)}
        </select>}
        <button type="button" onClick={() => { onRefresh?.(); if (isCensopas) { resultsQuery.refetch(); areaQuery.refetch(); sexQuery.refetch(); } else genericQuery.refetch(); executiveQuery.refetch(); }} disabled={isRefreshing} aria-label="Actualizar telemetría" title="Actualizar telemetría">
          <RefreshCcw size={18} className={isRefreshing ? 'animate-spin' : ''} /></button>
      </div>
    </header>

    <section className="aurora-liquid-metrics" aria-label="Indicadores clave de telemetría">
      <Metric icon={Users} label={selectedSegment ? `Muestra · ${focused?.construct_code || 'dimensión'}` : 'Respuestas válidas'}
        value={selectedSegment ? (focusValue?.n_valid ?? '—') : (valid ?? '—')}
        detail={selectedSegment ? selectedSegment.label : (invited != null ? `de ${invited} convocados` : 'Enlace abierto · sin denominador de invitación')} />
      {isCensopas ? <>
        <Metric icon={BarChart3} label="Mayor proporción desfavorable" value={maxUnfavorable >= 0 ? percentText(maxUnfavorable) : '—'}
          detail={selectedSegment ? `En ${selectedSegment.label}` : 'Entre las dimensiones publicables'} tone="cyan" />
        <Metric icon={ShieldCheck} label="Dimensiones en riesgo alto" value={critical}
          detail={`${publishable} de ${baseRows.length} dimensiones publicables`} tone="violet" />
      </> : <>
        <Metric icon={BarChart3} label={validRate != null ? 'Cobertura válida' : 'Cuestionarios completados'}
          value={validRate != null ? percentText(validRate) : completed ?? '—'}
          detail={validRate != null ? 'Válidas / convocados' : 'Captura del instrumento'} tone="cyan" />
        <Metric icon={ShieldCheck} label="Dimensiones publicables" value={rows.length}
          detail="Sin categorías de riesgo CENSOPAS" tone="violet" />
      </>}
    </section>

    <div className="aurora-liquid-content">
      <section className="aurora-liquid-dimensions" aria-label="Resultados por dimensión">
        <div className="aurora-liquid-section-head"><div><span className="aurora-liquid-eyebrow">LECTURA PRINCIPAL</span>
          <h2>Dimensiones del instrumento</h2><p>{isCensopas ? (selectedSegment ? `Filtro activo: ${selectedSegment.label} · distribución favorable, intermedia y desfavorable.` : 'Distribución colectiva favorable, intermedia y desfavorable.') : 'Puntajes descriptivos normalizados; no equivalen a nivel de riesgo.'}</p></div>
          {isCensopas ? <div className="aurora-liquid-filters">
            <label>Sexo<select aria-label="Filtrar por sexo" value={segmentMode === 'sex' ? selectedSegmentId : 'ALL'}
              title="Filtro individual: seleccionar sexo restablece el filtro de área"
              onChange={(event) => { setSegmentMode('sex'); setSelectedSegmentId(event.target.value); }} disabled={!sexOptions.length}>
              <option value="ALL">Todos</option>
              {sexOptions.map((choice) => <option key={choice.id} value={choice.id}>{choice.label}</option>)}
            </select></label>
            <label>Área<select aria-label="Filtrar por área" value={segmentMode === 'area' ? selectedSegmentId : 'ALL'}
              title="Filtro individual: seleccionar área restablece el filtro de sexo"
              onChange={(event) => { setSegmentMode('area'); setSelectedSegmentId(event.target.value); }} disabled={!areaOptions.length}>
              <option value="ALL">Todas</option>
              {areaOptions.map((choice) => <option key={choice.id} value={choice.id}>{choice.label}</option>)}
            </select></label>
          </div> : <span className="aurora-liquid-count">{rows.length} dimensiones</span>}</div>
        {rows.length ? <div className="aurora-liquid-rows">
          {rows.map((row) => <button type="button" key={row.construct_code}
            aria-pressed={focused?.construct_code === row.construct_code}
            className="aurora-liquid-dimension" onClick={() => setDimensionCode(row.construct_code)}>
            <span className="aurora-liquid-dimension-name"><strong>{row.construct_name}</strong><small>{row.construct_code}</small></span>
            {isCensopas && row.suppressed ? <><span className="aurora-liquid-unavailable">Sin resultado publicable para este grupo</span><span className="aurora-liquid-value is-unavailable">—<small>privacidad</small></span></>
              : isCensopas ? <><span className="aurora-liquid-track" role="img" aria-label={`${row.construct_name}: ${percentText(row.favorable_pct)} favorable, ${percentText(row.intermediate_pct)} intermedio, ${percentText(row.unfavorable_pct)} desfavorable`}>
              {BANDS.map((band) => <i key={band.key} style={{ width: `${row[band.key]}%`, backgroundColor: band.color }} />)}
            </span><span className="aurora-liquid-value">{percentText(row.unfavorable_pct)}<small>desfavorable</small></span></>
              : <><span className="aurora-liquid-track is-generic"><i style={{ width: `${row.mean_score}%` }} /></span>
                <span className="aurora-liquid-value">{row.mean_score.toFixed(1)}<small>de 100</small></span></>}
          </button>)}
        </div> : <p className="aurora-liquid-empty">Aún no hay dimensiones publicables. La muestra puede ser insuficiente o la puntuación estar pendiente.</p>}
        {isCensopas && rows.length > 0 && <div className="aurora-liquid-legend">{BANDS.map((band) => <span key={band.key}><i style={{ backgroundColor: band.color }} />{band.label}</span>)}</div>}
      </section>

      <aside className="aurora-liquid-focus" aria-label="Detalle de la dimensión">
        {focused ? <><div className="aurora-liquid-focus-summary">
          <div className="aurora-liquid-focus-info"><span className="aurora-liquid-eyebrow">DIMENSIÓN SELECCIONADA</span>
            <h2>{focused.construct_name}</h2><p className="aurora-liquid-focus-code">{focused.construct_code}</p>
            {isCensopas && focusValue && <span className="aurora-liquid-classification">{riskLabel(focusValue.collective_classification)}</span>}
          </div>
          <div className="aurora-liquid-focus-number">{isCensopas ? (focusValue ? percentText(focusValue.unfavorable_pct) : '—') : focused.mean_score.toFixed(1)}
            <small>{isCensopas ? (focusValue ? 'desfavorable' : 'grupo no publicable') : 'puntos de 100'}</small></div>
        </div>
          {isCensopas && focusValue && <p className="aurora-liquid-recommendation">
            {percentText(focusValue.favorable_pct)} favorable · {percentText(focusValue.intermediate_pct)} intermedio
            {Number.isFinite(focusValue.n_valid) ? ` · n=${focusValue.n_valid}` : ''}
          </p>}
          {selectedSegment && !focusValue && <p className="aurora-liquid-recommendation">Esta dimensión no alcanza el mínimo de publicación en {selectedSegment.label}.</p>}
        </> : <p className="aurora-liquid-empty">Selecciona una dimensión cuando haya resultados.</p>}
        {isCensopas && <div className="aurora-liquid-comparison" aria-label={`Comparación por ${segmentMode === 'sex' ? 'sexo' : 'área'}`}>
          <div className="aurora-liquid-comparison-head">
            <div><h3>{segmentMode === 'sex' ? 'Por sexo' : 'Por área'}</h3>
              <p>{focusedBase ? `${focusedBase.construct_code} · empresa ${percentText(focusedBase.unfavorable_pct)} desfavorable` : 'Selecciona una dimensión'}</p></div>
            {selectedSegmentId !== 'ALL' && <button type="button" className="aurora-liquid-reset" onClick={() => setSelectedSegmentId('ALL')}>
              <RotateCcw size={12} />Toda la empresa</button>}
          </div>
          {comparisonQuery.isLoading ? <p className="aurora-liquid-comparison-state">Cargando grupos…</p>
            : comparisonQuery.isError ? <p className="aurora-liquid-comparison-state">No se pudo cargar esta comparación.</p>
              : !comparisons.length ? <p className="aurora-liquid-comparison-state">
                {segmentMode === 'sex' && sexQuery.data?.available === false ? 'Este estudio no tiene una pregunta de sexo vinculada.' : 'No hay grupos publicables para esta dimensión.'}
              </p> : <div className="aurora-liquid-comparison-rows">
                {comparisons.map((group) => <button type="button" key={group.id}
                  aria-pressed={selectedSegmentId === group.id}
                  aria-label={`${group.label}: ${percentText(group.unfavorable)} desfavorable, n=${group.n}`}
                  title={`${group.label} · ${percentText(group.unfavorable)} desfavorable · n=${group.n}`}
                  onClick={() => setSelectedSegmentId(selectedSegmentId === group.id ? 'ALL' : group.id)}
                  className="aurora-liquid-comparison-row">
                  <span className="aurora-liquid-comparison-label"><strong>{group.label}</strong><small>n={group.n}</small></span>
                  <span className="aurora-liquid-comparison-track"><i style={{ width: `${group.unfavorable}%` }} /></span>
                  <strong className="aurora-liquid-comparison-value">{percentText(group.unfavorable)}</strong>
                </button>)}
              </div>}
        </div>}
      </aside>
    </div>
  </div>;
}
