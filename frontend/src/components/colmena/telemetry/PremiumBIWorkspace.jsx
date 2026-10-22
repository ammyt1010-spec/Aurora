import { useEffect, useMemo, useState } from 'react';
import { useDashboardLayout } from '../../../hooks/useDashboardLayout.js';
import { useQuery } from '@tanstack/react-query';
import {
  Activity, ArrowDown, ArrowUp, BarChart3, ChevronRight, CircleHelp,
  GripVertical, Layers3, LayoutGrid, RotateCcw, Settings2, ShieldCheck,
  SlidersHorizontal, Sparkles, Target, Users,
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
import './PremiumBIWorkspace.css';

const CHART_BANDS = [
  { key: 'unfavorable_pct', label: 'Desfavorable', color: 'var(--aurora-risk-high)' },
  { key: 'intermediate_pct', label: 'Intermedio', color: 'var(--aurora-risk-mid)' },
  { key: 'favorable_pct', label: 'Favorable', color: 'var(--aurora-risk-low)' },
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
        row.construct_name + ': ' + row.unfavorable_pct.toFixed(1) + '% desfavorable, ' +
        row.intermediate_pct.toFixed(1) + '% intermedio, ' + row.favorable_pct.toFixed(1) + '% favorable'
      }>
        {CHART_BANDS.map((band) => (
          <span key={band.key} style={{ width: String(percent(row[band.key])) + '%', background: band.color }}
            title={band.label + ': ' + row[band.key].toFixed(1) + '%'} />
        ))}
      </span>
      <span className="aurora-bi-band-number">{row.unfavorable_pct.toFixed(1)}% <small>desf.</small></span>
      <ChevronRight size={15} className="aurora-bi-chevron" />
    </button>
  );
}

function GenericScoreTrack({ row, onSelect }) {
  return (
    <button type="button" className="aurora-bi-band-row" onClick={() => onSelect(row.construct_code)}>
      <span className="aurora-bi-band-name"><strong>{row.construct_name}</strong><small>{row.construct_code}</small></span>
      <span className="aurora-bi-score-meter" role="img"
        aria-label={row.construct_name + ': puntaje medio ' + row.mean_score.toFixed(1) + ' sobre 100'}>
        <span style={{ width: String(percent(row.mean_score)) + '%' }} />
      </span>
      <span className="aurora-bi-band-number">{row.mean_score.toFixed(1)} <small>/ 100</small></span>
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

export default function PremiumBIWorkspace({ projectId, organizationId, studyId, telemetry }) {
  const { layout, updateLayout, loading: loadingLayout, saveError: layoutSaveError } = useDashboardLayout(organizationId, projectId);
  const widgets = layout.widgets;
  const density = layout.density;
  const chartMode = layout.chart_mode;
  const setWidgets = (next) => updateLayout({ widgets: typeof next === 'function' ? next(widgets) : next });
  const setDensity = (next) => updateLayout({ density: typeof next === 'function' ? next(density) : next });
  const setChartMode = (next) => updateLayout({ chart_mode: next });
  const [customize, setCustomize] = useState(false);
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
  const maxRisk = riskRows.length ? Math.max(...riskRows.map((row) => row.unfavorable_pct)) : null;
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

  if (isLoading) return <div className="aurora-bi-loading">Preparando el tablero de diagnóstico…</div>;
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

  const sectionContent = {
    summary: (
      <ChartPanel title={showSegment ? 'Indicadores del segmento' : 'Pulso ejecutivo'}
        subtitle={showSegment ? 'Sin mezclar datos globales con el filtro actual' : 'Lectura corporativa a primera vista'}
        icon={Activity} wide>
        <div className="aurora-bi-stats">
          {showSegment ? (
            <>
              <MiniStat icon={Layers3} label="Segmento" value={selectedUnit?.name || 'Sin selección'}
                detail={currentUnitType?.name || 'Unidad seleccionada'} />
              <MiniStat icon={BarChart3} label="Dimensiones publicables" value={publishable}
                detail="Umbral de privacidad respetado" tone="blue" />
              <MiniStat icon={Target} label="Máximo desfavorable" value={maxRisk == null ? 'No disponible' : maxRisk.toFixed(1) + '%'}
                detail="Entre dimensiones publicables" tone="red" />
            </>
          ) : (
            <>
              <MiniStat icon={Users} label="Respuestas válidas" value={telemetry?.valid_count ?? executive?.participation?.valid_count ?? null}
                detail="Participación del estudio" />
              <MiniStat icon={Target} label="Riesgos prioritarios" value={executive?.risk_distribution?.high_risk_count ?? null}
                detail="Clasificación del motor" tone="red" />
              <MiniStat icon={Activity} label="Seguimiento" value={executive?.risk_distribution?.medium_risk_count ?? null}
                detail="Categorías intermedias" tone="amber" />
              <MiniStat icon={ShieldCheck} label="Resultados favorables" value={executive?.risk_distribution?.low_risk_count ?? null}
                detail="Categorías verificadas" tone="green" />
            </>
          )}
        </div>
        {!showSegment && executive?.headline && <p className="aurora-bi-insight"><Sparkles size={15} />{executive.headline}</p>}
        {showSegment && <p className="aurora-bi-help">Los indicadores del estudio completo no se recalculan para un segmento: solo se muestran resultados segmentados autorizados por el servidor.</p>}
        {!executive && !showSegment && <p className="aurora-bi-help">El resumen ejecutivo se mostrará cuando el análisis esté disponible.</p>}
      </ChartPanel>
    ),
    distribution: (
      <ChartPanel title={isCensopas ? 'Mapa de riesgos por dimensión' : 'Dimensiones evaluadas'}
        subtitle={isCensopas ? 'Distribución completa, escala fija de 0 a 100 %' : 'Puntaje descriptivo, sin equivalencia automática a riesgo'}
        icon={Layers3} wide>
        {dimensions.length ? (
          <div className="aurora-bi-chart-rows">
            {dimensions.map((row) => isCensopas
              ? <PercentageTrack key={row.construct_code} row={row}
                  onSelect={(value) => setDimension(dimension === value ? 'ALL' : value)} selected={dimension === row.construct_code}/>
              : <GenericScoreTrack key={row.construct_code} row={row} onSelect={(value) => setDimension(dimension === value ? 'ALL' : value)}/>)}
            <Legend isCensopas={isCensopas} />
          </div>
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
              const value = isCensopas ? row.unfavorable_pct : row.mean_score;
              return (
                <button type="button" className="aurora-bi-rank-row" key={row.construct_code}
                  onClick={() => setDimension(dimension === row.construct_code ? 'ALL' : row.construct_code)}>
                  <span className="aurora-bi-rank-position">{index + 1}</span>
                  <span className="aurora-bi-rank-content">
                    <span>{row.construct_name}</span>
                    <i><b style={{ width: String(percent(value)) + '%', background: isCensopas ? 'var(--aurora-risk-high)' : 'var(--aurora-accent)' }} /></i>
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
                  <strong>{row.unfavorable_pct.toFixed(1)}%</strong>
                </div>
              ))}
            {!safeSegmentRows(unitResultsQuery.data?.results, unitId, dimension).length &&
              <EmptyData message="Sin resultados segmentados publicables. Los grupos pequeños permanecen ocultos." />}
            <p className="aurora-bi-help">Comparación exploratoria por dimensión. No reemplaza pruebas de significancia ni sus conclusiones.</p>
          </div>
        )}
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
      <header className="aurora-bi-hero">
        <div className="aurora-bi-hero-copy">
          <span className="aurora-bi-overline"><Sparkles size={13} /> CENTRO DE INTELIGENCIA EMPRESARIAL</span>
          <h2>Diagnóstico que se entiende.</h2>
          <p>Explora dimensiones, compara segmentos y localiza prioridades. Todos los resultados proceden del análisis autorizado.</p>
        </div>
        <div className="aurora-bi-hero-mark" aria-hidden="true"><LayoutGrid size={43}/><span>BI</span></div>
      </header>

      <div className="aurora-bi-controls">
        {layoutSaveError && <p role="alert" className="aurora-bi-help">La configuración se conserva localmente, pero no se pudo sincronizar con la empresa.</p>}
        <div className="aurora-bi-controls-title"><SlidersHorizontal size={15}/><strong>Filtros y segmentación</strong></div>
        <div className="aurora-bi-filter-grid">
          <label>Dimensión
            <select value={dimension} onChange={(event) => setDimension(event.target.value)}>
              <option value="ALL">Todas las dimensiones</option>
              {getDimensions(sourceRows, { isCensopas }).map((row) =>
                <option key={row.construct_code} value={row.construct_code}>{row.construct_name}</option>)}
            </select>
          </label>
          <label>Orden
            <select value={order} onChange={(event) => setOrder(event.target.value)}>
              <option value="risk">{isCensopas ? 'Prioridad y desfavorable' : 'Mayor puntaje'}</option>
              <option value="name">Nombre de dimensión</option>
            </select>
          </label>
          <label>Segmento
            <select value={unitTypeId} disabled={!isCensopas || !unitTypesQuery.data?.length}
              onChange={(event) => { setUnitTypeId(event.target.value); setUnitId('ALL'); setDimension('ALL'); }}>
              <option value="">Toda la empresa</option>
              {(unitTypesQuery.data || []).map((type) =>
                <option key={type.id} value={type.id}>{type.name}</option>)}
            </select>
          </label>
          <label>Unidad
            <select value={unitId} disabled={!unitTypeId || unitResultsQuery.isLoading}
              onChange={(event) => { setUnitId(event.target.value); setDimension('ALL'); }}>
              <option value="ALL">Todas las unidades</option>
              {unitChoices.map((unit) =>
                <option key={unit.id} value={unit.id}>{unit.name}</option>)}
            </select>
          </label>
        </div>
        <div className="aurora-bi-toolrow">
          <span className="aurora-bi-filter-caption">
            <ShieldCheck size={13}/> {showSegment ? 'Filtro activo: ' + (selectedUnit?.name || 'unidad') : 'Vista global'} · Grupos privados no visibles
          </span>
          <div className="aurora-bi-toolbar">
            <button type="button" onClick={() => { setDimension('ALL'); setUnitTypeId(''); setUnitId('ALL'); setOrder('risk'); }}
              className="aurora-bi-toolbutton"><RotateCcw size={14}/> Limpiar filtros</button>
            <button type="button" onClick={() => setDensity((value) => value === 'compact' ? 'comfortable' : 'compact')}
              className="aurora-bi-toolbutton"><GripVertical size={14}/> {density === 'compact' ? 'Ampliar' : 'Compactar'}</button>
            <button type="button" onClick={() => setCustomize((value) => !value)}
              aria-expanded={customize} className="aurora-bi-toolbutton is-primary"><Settings2 size={14}/> Elegir cuadros</button>
          </div>
        </div>
        {customize && (
          <div className="aurora-bi-customize">
            <div className="aurora-bi-customize-title">
              <strong>Configura tu tablero</strong><span>Mostrar, ocultar y ordenar. Preferencias guardadas en este navegador.</span>
            </div>
            <div className="aurora-bi-widget-options">
              {DASHBOARD_WIDGETS.map((widget) => (
                <div key={widget.id} className="aurora-bi-widget-choice">
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
            <button className="aurora-bi-toolbutton" type="button" onClick={() => setWidgets([...DEFAULT_WIDGETS])}>
              <RotateCcw size={14}/> Restablecer paneles
            </button>
          </div>
        )}
      </div>

      <div className="aurora-bi-section-head">
        <div><h3>Panel ejecutivo</h3><span>{showSegment ? 'Vista filtrada por segmento' : 'Resumen de la evaluación'}</span></div>
        <div className="aurora-bi-live"><span/> Fuente: datos del servidor</div>
      </div>
      <div className="aurora-bi-grid">
        {widgets.map((id) => <div key={id} className="aurora-bi-grid-item">{sectionContent[id]}</div>)}
      </div>

      <footer className="aurora-bi-footer">
        <span><ShieldCheck size={14}/> Las categorías dependen del baremo de cada instrumento. La supresión de privacidad no puede anularse mediante filtros.</span>
        <Link to={'/colmena/project/' + projectId + '/results'}>Abrir análisis técnico <ChevronRight size={13}/></Link>
      </footer>
    </div>
  );
}