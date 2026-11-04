import { executiveRows } from './executiveBoardModel.js';

const segmentId = (row) => String(row.group_value || row.unit_id || '');
const segmentLabel = (row) => row.group_value || row.unit_name;

export function segmentOptions(results) {
  const choices = new Map();
  for (const row of executiveRows(results, true)) {
    const id = segmentId(row);
    const label = segmentLabel(row);
    if (id && label && !choices.has(id)) choices.set(id, { id, label });
  }
  return [...choices.values()].sort((a, b) => a.label.localeCompare(b.label, 'es'));
}

export function filteredDimensionRows(baseRows, results, selectedId) {
  if (selectedId === 'ALL') return baseRows;
  const matching = new Map(executiveRows(results, true)
    .filter((row) => segmentId(row) === selectedId)
    .map((row) => [row.construct_code, row]));
  return baseRows.map((base) => matching.get(base.construct_code) || {
    ...base,
    suppressed: true,
    n_valid: null,
    favorable_n: null,
    intermediate_n: null,
    unfavorable_n: null,
    favorable_pct: null,
    intermediate_pct: null,
    unfavorable_pct: null,
    collective_classification: null,
  }).sort((a, b) => {
    if (a.suppressed !== b.suppressed) return a.suppressed ? 1 : -1;
    return (b.unfavorable_pct ?? -1) - (a.unfavorable_pct ?? -1);
  });
}

export function dimensionComparisons(results, constructCode) {
  return executiveRows(results, true)
    .filter((row) => row.construct_code === constructCode)
    .map((row) => ({
      id: segmentId(row),
      label: segmentLabel(row),
      n: row.n_valid,
      unfavorable: row.unfavorable_pct,
    }))
    .filter((row) => row.id && row.label)
    .sort((a, b) => b.unfavorable - a.unfavorable);
}
