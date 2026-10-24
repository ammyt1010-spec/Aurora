import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, BarChart3, ChevronRight, CircleHelp, Eye, FilterX, ShieldCheck, SlidersHorizontal } from 'lucide-react';
import { Link } from 'react-router-dom';

import { getCensopasReadiness } from '../../../api/instruments.js';
import { getExecutiveDashboard } from '../../../api/reports.js';
import { getCensopasResults, getCensopasUnitResults, getResultsOverview, getStudy, listStudyUnitTypes } from '../../../api/studies.js';
import {
  actionForDimension, comparisonUnits, executiveRows, matrixCells, maxUnfavorable,
  percentText, riskLabel, selectedDimension,
} from './executiveBoardModel.js';
import LongitudinalBIWidget from './LongitudinalBIWidget.jsx';
import './ExecutiveDecisionBoard.css';

const BANDS = [
  { key: 'unfavorable_pct', label: 'Desfavorable', color: '#D85E70' },
  { key: 'intermediate_pct', label: 'Intermedio', color: '#E8AD52' },
  { key: 'favorable_pct', label: 'Favorable', color: '#18A88B' },
];

function Empty({ children }) {
  return <div className="aurora-compact-empty"><CircleHelp size={18} aria-hidden="true"/><span>{children}</span></div>;
}

function PercentBar({ row, isCensopas }) {
  return isCensopas ? (
    <span className="aurora-compact-stacked" role="img"
      aria-label={row.construct_name + ': ' + BANDS.map(b => b.label + ' ' + percentText(row[b.key])).join(', ')}>
      {BANDS.map((band) => <i key={band.key}
        style={{ width: row[band.key] + '%', background: band.color }}
        title={band.label + ': ' + percentText(row[band.key])}/>)}
    </span>
  ) : (
    <span className="aurora-compact-stacked" role="img"
      aria-label={row.construct_name + ': puntuación descriptiva ' + percentText(row.mean_score)}>
      <i style={{ width: row.mean_score + '%', background: '#6366F1' }} />
    </span>
  );
}

/**
 * Vista ejecutiva para UNA pantalla.
 * La matriz y la información de detalle tienen scroll propio. La comparativa
 * utiliza exclusivamente resultados publicables devueltos por el backend.
 */
export default function ExecutiveDecisionBoard({ projectId, studyId, telemetry }) {
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

  const reset = () => {
    setDimension('ALL');
    setUnitTypeId('');
    setUnitId('ALL');
    setFocusedCode(null);
  };

  if (error) return <div className="aurora-compact-state" role="alert">No se pudo consultar el diagnóstico metodológico. Verifica el estudio y vuelve a intentar.</div>;
  if (loading || !classificationKnown) return <div className="aurora-compact-state">Cargando diagnóstico ejecutivo…</div>;

  return (
    <section className="aurora-compact" aria-label="Diagnóstico ejecutivo compacto">
      <header className="aurora-compact-titlebar">
        <div className="aurora-compact-brand">
          <span className="aurora-compact-symbol"><BarChart3 size={19}/></span>
          <div>
            <h2>Diagnóstico ejecutivo</h2>
            <p>Prioridades, dimensiones y comparaciones en una vista</p>
          </div>
        </div>
        <div className="aurora-compact-status"><span className="aurora-compact-live"/> {activeFilter}</div>
      </header>

      <div className="aurora-compact-filters" role="group" aria-label="Filtros coordinados">
        <SlidersHorizontal size={16} aria-hidden="true"/>
        <label>Dimensión
          <select aria-label="Dimensión del diagnóstico" value={dimension}
            onChange={(e)=>{setDimension(e.target.value);setFocusedCode(null);}}>
            <option value="ALL">Todas</option>
            {allRows.map(row=><option key={row.construct_code} value={row.construct_code}>{row.construct_name}</option>)}
          </select>
        </label>
        <label>Comparar por
          <select aria-label="Tipo de segmento" value={unitTypeId}
            disabled={!isCensopas || !unitTypesQuery.data?.length}
            onChange={(e)=>{setUnitTypeId(e.target.value);setUnitId('ALL');}}>
            <option value="">Toda la empresa</option>
            {(unitTypesQuery.data || []).map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </label>
        <label>Unidad
          <select aria-label="Unidad del segmento" value={unitId} disabled={!unitTypeId || unitQuery.isLoading}
            onChange={(e)=>setUnitId(e.target.value)}>
            <option value="ALL">Todas las publicables</option>
            {allUnits.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}
          </select>
        </label>
        <button className="aurora-compact-reset" type="button" onClick={reset} title="Limpiar filtros">
          <FilterX size={14}/> Restablecer
        </button>
      </div>

      <div className="aurora-compact-metrics" aria-label="Indicadores esenciales">
        <div className="aurora-compact-metric">
          <span>{selectedUnit ? 'Unidad seleccionada' : 'Respuestas válidas'}</span>
          <strong>{selectedUnit ? selectedUnit.label : telemetry?.valid_count ?? executiveQuery.data?.participation?.valid_count ?? 'Sin datos'}</strong>
          <small>{selectedUnit ? 'Resultados agrupados y protegidos' : 'Total global del estudio'}</small>
        </div>
        <div className="aurora-compact-metric">
          <span>{isCensopas ? 'Mayor proporción desfavorable' : 'Dimensiones publicables'}</span>
          <strong>{isCensopas ? percentText(worstValue) : visibleRows.length}</strong>
          <small>{isCensopas ? 'No equivale por sí solo a un diagnóstico' : 'Puntajes descriptivos del instrumento'}</small>
        </div>
        <div className="aurora-compact-metric">
          <span>{comparing ? 'Unidades comparables' : isCensopas ? 'Dimensiones de riesgo alto' : 'Dimensiones disponibles'}</span>
          <strong>{comparing ? (unitQuery.isError ? 'Sin datos' : unitQuery.isLoading ? 'Cargando' : unitsVisible.length) :
            isCensopas ? visibleRows.filter(row => row.collective_classification === 'RIESGO_ALTO').length : visibleRows.length}</strong>
          <small>{comparing ? 'Solo resultados publicables' : isCensopas ? 'Clasificación según baremo configurado' : 'Sin categorías de riesgo añadidas'}</small>
        </div>
      </div>

      <div className="aurora-compact-main">
        <section className="aurora-compact-matrix" aria-label="Matriz ejecutiva por dimensión">
          <div className="aurora-compact-panelhead">
            <div>
              <h3>Dimensiones y comparaciones</h3>
              <span>{isCensopas ? 'Desfavorable · Intermedio · Favorable' : 'Puntuación descriptiva (0 a 100)'}</span>
            </div>
            <div className="aurora-compact-views" role="group" aria-label="Tipo de análisis">
              <button type="button" aria-pressed={analysisView === 'diagnosis'}
                className={analysisView === 'diagnosis' ? 'is-active' : ''}
                onClick={() => setAnalysisView('diagnosis')}>Diagnóstico</button>
              <button type="button" aria-pressed={analysisView === 'trend'}
                className={analysisView === 'trend' ? 'is-active' : ''}
                onClick={() => setAnalysisView('trend')}>Evolución</button>
            </div>
          </div>
          <div className="aurora-compact-tablewrap" tabIndex={0} aria-label="Matriz desplazable de resultados">
            {analysisView === 'trend' ? (
              <div className="aurora-compact-trend">
                {comparing && <p className="aurora-compact-temporal-note">Evolución global del estudio. No corresponde al filtro de unidad actual.</p>}
                <LongitudinalBIWidget projectId={projectId} dimension={focused?.construct_code || (dimension !== 'ALL' ? dimension : 'ALL')}/>
              </div>
            ) : sourceUnavailable ? (
              <Empty>{unitQuery.isError ? 'No fue posible obtener la segmentación autorizada.' : 'Cargando comparaciones…'}</Empty>
            ) : visibleRows.length === 0 ? (
              <Empty>No hay dimensiones publicables con los filtros actuales.</Empty>
            ) : (
              <table className="aurora-compact-table">
                <thead>
                  <tr>
                    <th scope="col">Dimensión</th>
                    <th scope="col">{isCensopas ? 'Distribución global' : 'Puntaje'}</th>
                    <th scope="col">{isCensopas ? '% desf.' : 'Media'}</th>
                    {unitsVisible.map(u=><th scope="col" key={u.id} title={u.label}>{u.label}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map(row=>{
                    const active=focused?.construct_code === row.construct_code;
                    return <tr key={row.construct_code} className={active ? 'is-active' : undefined}>
                      <th scope="row">
                        <button type="button" aria-pressed={active}
                          onClick={()=>setFocusedCode(row.construct_code)} title={'Ver detalle de '+row.construct_name}>
                          <span className="aurora-compact-code">{row.construct_code}</span>
                          <span>{row.construct_name}</span>
                          <ChevronRight size={13} aria-hidden="true"/>
                        </button>
                      </th>
                      <td><PercentBar row={row} isCensopas={isCensopas}/></td>
                      <td className="aurora-compact-number">{percentText(isCensopas ? row.unfavorable_pct : row.mean_score)}</td>
                      {unitsVisible.map(u=>{
                        const cell=safeCells.get(row.construct_code + '::' + u.id);
                        return <td key={u.id} className="aurora-compact-number">
                          {cell ? <span className="aurora-compact-cell" title={'% desfavorable '+cell.unfavorable_pct.toFixed(1)+' · n='+cell.n_valid}>
                            {percentText(cell.unfavorable_pct)}</span>
                            : <span className="aurora-compact-suppressed" title="No disponible por privacidad o falta de resultados">N/D</span>}
                        </td>;
                      })}
                    </tr>;
                  })}
                </tbody>
              </table>
            )}
          </div>
          <div className="aurora-compact-legend">
            {isCensopas ? BANDS.map(b=><span key={b.key}><i style={{background:b.color}}/>{b.label}</span>) :
              <span>Resultados descriptivos, sin inferencias ni clasificación añadidas</span>}
            {comparing && <span className="aurora-compact-note"><ShieldCheck size={12}/> Grupos pequeños ocultos</span>}
          </div>
        </section>
        <aside className="aurora-compact-insights" aria-label="Hallazgo principal y acción">
          <div className="aurora-compact-panelhead">
            <div><h3>Qué significa</h3><span>Detalle contextual de la selección</span></div>
            <Activity size={17} aria-hidden="true"/>
          </div>
          {focused ? <div className="aurora-compact-insightbody">
            <div className="aurora-compact-focuscode">{focused.construct_code}</div>
            <h4>{focused.construct_name}</h4>
            {isCensopas ? (
              <>
                <strong className="aurora-compact-focusvalue">{percentText(matchingCell?.unfavorable_pct ?? (!selectedUnit ? focused.unfavorable_pct : null))}</strong>
                <span className="aurora-compact-detail">
                  {selectedUnit ? 'Desfavorable en la unidad seleccionada' : '% desfavorable del estudio'}
                </span>
                <span className="aurora-compact-classification">
                  {selectedUnit ? 'Comparación descriptiva por segmento' : riskLabel(focused.collective_classification)}
                </span>
              </>
            ) : (
              <>
                <strong className="aurora-compact-focusvalue">{percentText(focused.mean_score)}</strong>
                <span className="aurora-compact-detail">Puntuación descriptiva normalizada, no nivel de riesgo</span>
              </>
            )}
            <div className="aurora-compact-insightdivider"/>
            <h5>Hallazgo e intervención</h5>
            {selectedUnit ? (
              <p>La segmentación permite localizar diferencias descriptivas. No se trasladan recomendaciones globales a una unidad sin análisis autorizado.</p>
            ) : interpretation ? (
              <p>{interpretation.recommendation}</p>
            ) : (
              <p>Consulta el análisis técnico para interpretar esta dimensión según sus baremos y evidencia disponible.</p>
            )}
            {isCensopas && !selectedUnit && focused.priority_rank != null &&
              <p className="aurora-compact-priority">Prioridad registrada por el motor: #{focused.priority_rank}</p>}
          </div> : <Empty>Selecciona una dimensión para consultar su interpretación.</Empty>}
          <div className="aurora-compact-next">
            <Link to={projectId ? '/colmena/project/'+projectId+'/results' : '/colmena/telemetry'}>
              <Eye size={14}/> Ver evidencia técnica <ChevronRight size={13}/>
            </Link>
          </div>
        </aside>
      </div>
      <div className="aurora-compact-footer">
        <span><ShieldCheck size={13}/> Solo agregados publicables; los filtros no recalculan baremos.</span>
        <span>Selecciona una fila para enfocar el diagnóstico.</span>
      </div>
    </section>
  );
}
