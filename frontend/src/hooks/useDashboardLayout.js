import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { DEFAULT_LAYOUT, getDashboardPreferences, saveDashboardPreferences } from '../api/dashboardPreferences.js';

function normalize(raw) {
  const allowed = new Set(DEFAULT_LAYOUT.widgets);
  const list = Array.isArray(raw?.widgets) ? [...new Set(raw.widgets.filter((id) => allowed.has(id)))] : [];
  return {
    widgets: list.length ? list : [...DEFAULT_LAYOUT.widgets],
    density: raw?.density === 'comfortable' ? 'comfortable' : 'compact',
    chart_mode: ['stacked', 'heatmap', 'cards'].includes(raw?.chart_mode) ? raw.chart_mode : 'stacked',
  };
}
function localFallback(key) {
  try { return normalize(JSON.parse(localStorage.getItem(key) || 'null')); }
  catch { return normalize(null); }
}

/** Preferencias por cuenta y empresa en servidor; el cliente solo almacena disposición, nunca resultados. */
export function useDashboardLayout(organizationId, projectId) {
  const scope = `aurora:bi:layout:v2:${organizationId || 'project-' + projectId}`;
  const [layout, setLayout] = useState(() => localFallback(scope));
  const [dirty, setDirty] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const stateRef = useRef(layout);
  const sequence = useRef(0);
  const query = useQuery({
    queryKey: ['dashboard-preferences', organizationId],
    queryFn: () => getDashboardPreferences(organizationId),
    enabled: Boolean(organizationId),
    retry: false,
    staleTime: 120000,
  });

  useEffect(() => {
    const next = localFallback(scope);
    stateRef.current = next;
    setLayout(next);
    setDirty(false);
    setSaveError(false);
    sequence.current += 1;
  }, [scope]);

  useEffect(() => {
    if (!query.data || dirty) return;
    const next = normalize(query.data);
    stateRef.current = next;
    setLayout(next);
  }, [query.data, dirty]);

  useEffect(() => {
    if (!dirty) return undefined;
    const current = sequence.current;
    const timer = setTimeout(async () => {
      const snapshot = stateRef.current;
      try {
        localStorage.setItem(scope, JSON.stringify(snapshot));
        if (organizationId) await saveDashboardPreferences(organizationId, snapshot);
        if (current === sequence.current) { setSaveError(false); setDirty(false); }
      } catch {
        if (current === sequence.current) { setSaveError(true); setDirty(false); }
      }
    }, 550);
    return () => clearTimeout(timer);
  }, [layout, dirty, organizationId, scope]);

  function updateLayout(patch) {
    const next = normalize({ ...stateRef.current, ...patch });
    stateRef.current = next;
    sequence.current += 1;
    setDirty(true);
    setLayout(next);
  }

  return {
    layout, updateLayout,
    loading: Boolean(organizationId && query.isLoading),
    saveError: saveError || Boolean(organizationId && query.isError),
  };
}
