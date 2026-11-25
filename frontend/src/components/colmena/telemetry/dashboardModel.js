export const DASHBOARD_WIDGETS = [
  { id: 'summary', title: 'Indicadores' },
  { id: 'distribution', title: 'Distribución por dimensión' },
  { id: 'ranking', title: 'Prioridades' },
  { id: 'segments', title: 'Comparativo de segmentos' },
  { id: 'actions', title: 'Hallazgos y acciones' },
  { id: 'trend', title: 'Evolución temporal' },
  { id: 'action_plan', title: 'Seguimiento del plan' },
];
export const DEFAULT_WIDGETS = DASHBOARD_WIDGETS.map((widget) => widget.id);

export function percent(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  return Math.min(100, Math.max(0, value));
}

export function normalizeConstructRow(row) {
  if (!row) return row;
  const unfav = row.unfavorable_pct ?? row.bands?.find((b) => b.code === 'UNFAVORABLE')?.pct ?? null;
  const inter = row.intermediate_pct ?? row.bands?.find((b) => b.code === 'INTERMEDIATE')?.pct ?? null;
  const fav = row.favorable_pct ?? row.bands?.find((b) => b.code === 'FAVORABLE')?.pct ?? null;
  return {
    ...row,
    unfavorable_pct: unfav,
    intermediate_pct: inter,
    favorable_pct: fav,
  };
}

export function isPublishable(row, isCensopas = true) {
  if (!row || row.suppressed || row.construct_type !== 'DIMENSION') return false;
  if (!isCensopas) return typeof row.mean_score === 'number' && Number.isFinite(row.mean_score);
  const normalized = normalizeConstructRow(row);
  return [normalized.favorable_pct, normalized.intermediate_pct, normalized.unfavorable_pct]
    .every((value) => percent(value) !== null);
}

export function getDimensions(rows, { dimension = 'ALL', order = 'risk', isCensopas = true } = {}) {
  const valid = (Array.isArray(rows) ? rows : [])
    .filter((row) => isPublishable(row, isCensopas))
    .map(normalizeConstructRow);
  const filtered = valid.filter((row) => dimension === 'ALL' || String(row.construct_code) === String(dimension));
  return [...filtered].sort((a, b) => {
    if (order === 'name') return a.construct_name.localeCompare(b.construct_name, 'es');
    if (isCensopas) {
      const priorityA = a.priority_rank == null ? Infinity : a.priority_rank;
      const priorityB = b.priority_rank == null ? Infinity : b.priority_rank;
      if (priorityA !== priorityB) return priorityA - priorityB;
      return b.unfavorable_pct - a.unfavorable_pct;
    }
    return b.mean_score - a.mean_score;
  });
}

export function safeUnitChoices(results) {
  const map = new Map();
  for (const row of (Array.isArray(results) ? results : [])) {
    if (isPublishable(row, true) && !map.has(row.unit_id)) {
      map.set(row.unit_id, { id: row.unit_id, name: row.unit_name });
    }
  }
  return [...map.values()].sort((a, b) => a.name.localeCompare(b.name, 'es'));
}

export function safeSegmentRows(results, unitId = 'ALL', dimension = 'ALL') {
  return (Array.isArray(results) ? results : [])
    .filter((row) => isPublishable(row, true))
    .map(normalizeConstructRow)
    .filter((row) => unitId === 'ALL' || String(row.unit_id) === String(unitId))
    .filter((row) => dimension === 'ALL' || row.construct_code === dimension);
}

export function reorderWidget(ids, widgetId, direction) {
  const index = ids.indexOf(widgetId);
  const nextIndex = index + direction;
  if (index < 0 || nextIndex < 0 || nextIndex >= ids.length) return ids;
  const next = [...ids];
  [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
  return next;
}

export function readWidgetPreferences(key) {
  try {
    const stored = JSON.parse(window.localStorage.getItem(key) || 'null');
    if (!Array.isArray(stored)) return [...DEFAULT_WIDGETS];
    const permitted = new Set(DEFAULT_WIDGETS);
    const unique = [...new Set(stored.filter((id) => permitted.has(id)))];
    return unique.length ? unique : [...DEFAULT_WIDGETS];
  } catch {
    return [...DEFAULT_WIDGETS];
  }
}