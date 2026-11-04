import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Check, ClipboardList, QrCode } from 'lucide-react';

import { getCensopasPlans } from '../../api/instruments.js';
import InstrumentCartModal from '../../components/colmena/projects/InstrumentCartModal.jsx';
import { LoadingState } from '../../components/ui/LoadingState.jsx';
import { ErrorState } from '../../components/ui/ErrorState.jsx';
import { EmptyState } from '../../components/ui/EmptyState.jsx';

const VERSION_LABELS = {
  SHORT: 'CENSOPAS-COPSOQ, versión corta',
  MEDIUM: 'CENSOPAS-COPSOQ, versión media',
};
const OFFICIAL_VERSION_CODES = {
  SHORT: 'SHORT-OFICIAL',
  MEDIUM: 'MEDIUM-OFICIAL',
};
const VERSION_ORDER = ['SHORT', 'MEDIUM'];

export function availableInstrumentCards(response) {
  const plans = Array.isArray(response?.plans) ? response.plans : [];
  const byKind = new Map();
  for (const plan of plans) {
    const kind = plan?.version_kind;
    if (!VERSION_LABELS[kind]) continue;
    if (String(plan?.version_code || '').toUpperCase() !== OFFICIAL_VERSION_CODES[kind]) continue;
    if (!byKind.has(kind) || (plan.ready_for_scoring && !byKind.get(kind).ready_for_scoring)) {
      byKind.set(kind, plan);
    }
  }
  return VERSION_ORDER.map((kind) => byKind.get(kind)).filter(Boolean);
}

export default function DashboardPage() {
  const [selectedIds, setSelectedIds] = useState([]);
  const [showGenerator, setShowGenerator] = useState(false);
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['censopas-plans'],
    queryFn: getCensopasPlans,
    retry: false,
    staleTime: 60_000,
  });
  const instruments = availableInstrumentCards(data);
  const selected = useMemo(
    () => instruments.filter((instrument) => selectedIds.includes(instrument.instrument_version_id)),
    [instruments, selectedIds],
  );

  const toggleInstrument = (instrumentId) => {
    setSelectedIds((current) => current.includes(instrumentId)
      ? current.filter((id) => id !== instrumentId)
      : [...current, instrumentId]);
  };

  return (
    <div className="colmena-page !gap-4 !py-4">
      <section aria-label="Instrumentos oficiales disponibles" className="rounded-2xl border border-[#D9E6F1] bg-white p-4 shadow-xs">
        <div className="flex items-start gap-2">
          <ClipboardList size={20} className="mt-0.5 shrink-0 text-[#087D9B]" />
          <div>
            <span className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-[#2B69A5]">Paso 1 de 3</span>
            <h1 className="text-lg font-extrabold text-[#0A1F44]">Elige el instrumento</h1>
            <p className="text-xs text-[#64748B]">Puedes seleccionar uno o ambos. Cada instrumento tendrá su propio enlace e informe.</p>
          </div>
        </div>

        {isLoading ? <LoadingState label="Cargando instrumentos oficiales…" /> : null}
        {isError ? <ErrorState title="No se pudieron cargar los instrumentos" message={error?.message || 'Comprueba la conexión con Aurora.'} /> : null}
        {!isLoading && !isError && !instruments.length ? <EmptyState title="No hay instrumentos oficiales disponibles" description="El administrador debe publicar una versión válida." /> : null}

        {!isLoading && !isError && instruments.length ? (
          <div className="mt-3 divide-y divide-[#E6EDF4] overflow-hidden rounded-xl border border-[#D9E6F1]">
            {instruments.map((instrument) => {
              const checked = selectedIds.includes(instrument.instrument_version_id);
              const title = VERSION_LABELS[instrument.version_kind];
              return (
                <label key={instrument.instrument_version_id} className={`flex cursor-pointer items-center gap-3 px-4 py-3 transition ${checked ? 'bg-[#EDF9FB]' : 'bg-white hover:bg-[#F7FAFD]'}`}>
                  <input type="checkbox" checked={checked} onChange={() => toggleInstrument(instrument.instrument_version_id)} className="h-4 w-4 shrink-0" />
                  <span className="min-w-0 flex-1">
                    <strong className="block text-sm text-[#163A63]">{title}</strong>
                    <small className="block text-xs text-[#64748B]">
                      {instrument.question_count} preguntas · {instrument.scored_item_count} ítems puntuables · {instrument.dimension_count} dimensiones{instrument.subdimension_count ? ` · ${instrument.subdimension_count} subdimensiones` : ''}
                    </small>
                  </span>
                  {checked ? <Check size={17} className="shrink-0 text-[#108B91]"/> : null}
                </label>
              );
            })}
          </div>
        ) : null}
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-[#E6EDF4] pt-3">
          <p className="text-xs font-semibold text-[#526D82]" aria-live="polite">
            {selected.length ? `${selected.length} instrumento${selected.length === 1 ? '' : 's'} seleccionado${selected.length === 1 ? '' : 's'}` : 'Selecciona al menos un instrumento para continuar.'}
          </p>
          <button
            type="button"
            disabled={!selected.length}
            onClick={() => setShowGenerator(true)}
            className="inline-flex items-center gap-2 rounded-xl bg-[#0A1F44] px-4 py-2.5 text-sm font-extrabold text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            <QrCode size={17}/> Continuar · generar enlace y QR
          </button>
        </div>
      </section>

      <InstrumentCartModal
        instruments={selected.map((instrument) => ({ ...instrument, title: VERSION_LABELS[instrument.version_kind] }))}
        isOpen={showGenerator}
        onClose={() => setShowGenerator(false)}
      />
    </div>
  );
}
