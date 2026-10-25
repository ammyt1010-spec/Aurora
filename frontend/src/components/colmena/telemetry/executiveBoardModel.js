/**
 * Modelo de una sola vista. Todas las cifras provienen de resultados
 * publicables del backend; nunca recompone puntajes ni baremos.
 */
const validPercent = (v) =>
  typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 100;

export function executiveRows(results, isCensopas) {
  return (Array.isArray(results) ? results : [])
    .map((row) => {
      if (!row) return null;
      let r = { ...row };
      if (r.favorable_pct == null && Array.isArray(r.bands)) {
        r.favorable_pct = r.bands.find((b) => b.code === 'FAVORABLE')?.pct;
        r.intermediate_pct = r.bands.find(
          (b) => b.code === 'INTERMEDIATE',
        )?.pct;
        r.unfavorable_pct = r.bands.find((b) => b.code === 'UNFAVORABLE')?.pct;
      }
      return r;
    })
    .filter((row) => {
      if (!row || row.suppressed || row.construct_type !== 'DIMENSION')
        return false;
      if (isCensopas) {
        if (row.n_valid === 0 || row.bands?.some((b) => b.suppressed))
          return false;
        return (
          ['favorable_pct', 'intermediate_pct', 'unfavorable_pct'].every(
            (key) => validPercent(row[key]),
          ) &&
          Math.abs(
            row.favorable_pct +
              row.intermediate_pct +
              row.unfavorable_pct -
              100,
          ) <= 2.0
        );
      }
      return validPercent(row.mean_score);
    })
    .sort((a, b) => {
      if (isCensopas) {
        const pa = a.priority_rank == null ? Infinity : a.priority_rank;
        const pb = b.priority_rank == null ? Infinity : b.priority_rank;
        if (pa !== pb) return pa - pb;
        return b.unfavorable_pct - a.unfavorable_pct;
      }
      return String(a.construct_name || '').localeCompare(
        String(b.construct_name || ''),
        'es',
      );
    });
}

export function comparisonUnits(unitResults) {
  const unique = new Map();
  for (const row of executiveRows(unitResults, true)) {
    if (
      row.unit_id != null &&
      row.unit_name &&
      !unique.has(String(row.unit_id))
    ) {
      unique.set(String(row.unit_id), {
        id: String(row.unit_id),
        label: row.unit_name,
      });
    }
  }
  return [...unique.values()].sort((a, b) =>
    a.label.localeCompare(b.label, 'es'),
  );
}

export function matrixCells(rows) {
  const cells = new Map();
  for (const row of executiveRows(rows, true)) {
    cells.set(String(row.construct_code) + '::' + String(row.unit_id), row);
  }
  return cells;
}

export function selectedDimension(rows, code) {
  if (!rows.length) return null;
  return (
    rows.find((row) => String(row.construct_code) === String(code)) || rows[0]
  );
}

export function riskLabel(code) {
  const labels = {
    RIESGO_ALTO: 'Riesgo alto',
    RIESGO_MEDIO: 'Riesgo medio',
    FACTOR_PROTECTOR: 'Factor protector',
    REVISION: 'En revisión',
  };
  return labels[code] || 'Sin clasificación';
}

export function maxUnfavorable(rows) {
  const safe = rows.filter((row) => validPercent(row?.unfavorable_pct));
  return safe.length ? Math.max(...safe.map((r) => r.unfavorable_pct)) : null;
}

export function actionForDimension(rankings, code) {
  return (
    (Array.isArray(rankings) ? rankings : []).find(
      (r) =>
        String(r.construct_code) === String(code) &&
        typeof r.recommendation === 'string',
    ) || null
  );
}

export function percentText(value) {
  return validPercent(value) ? value.toFixed(1) + '%' : 'N/D';
}

export function countText(value) {
  return Number.isInteger(value) && value >= 0 ? String(value) : 'N/D';
}
export function rateText(value) {
  return typeof value === 'number' &&
    Number.isFinite(value) &&
    value >= 0 &&
    value <= 1
    ? (value * 100).toFixed(1) + '%'
    : 'N/D';
}
