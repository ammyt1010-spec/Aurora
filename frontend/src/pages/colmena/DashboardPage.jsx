import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  Gauge,
  HeartPulse,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

import InstrumentConfirmModal from '../../components/colmena/projects/InstrumentConfirmModal.jsx';

const CATALOG_INSTRUMENTS = [
  {
    id: 'censopas_short',
    title: 'CENSOPAS Corta (42 ítems)',
    version: 'SHORT',
    badge: 'Oficial SUNAFIL · PYMEs (<25 trab.)',
    badgeColor: 'bg-amber/10 text-amber border-amber/20',
    items: 42,
    duration: '10 min',
    description: 'Evaluación oficial de riesgos psicosociales obligatoria para pequeñas empresas y centros de trabajo con menos de 25 trabajadores.',
    icon: ShieldCheck,
  },
  {
    id: 'censopas_medium',
    title: 'CENSOPAS Media (112 ítems)',
    version: 'MEDIUM',
    badge: 'Oficial SUNAFIL · Minería e Industria (≥25 trab.)',
    badgeColor: 'bg-turquoise/10 text-turquoise border-turquoise/20',
    items: 112,
    duration: '20 min',
    description: 'Estándar completo para minería, hidrocarburos y gran industria. Evalúa 20 subdimensiones de exigencias, autonomía y apoyo social.',
    icon: Gauge,
  },
  {
    id: 'safety_climate',
    title: 'Clima de Seguridad Industrial',
    version: 'SHORT',
    badge: 'Prevención Minero-Industrial',
    badgeColor: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
    items: 35,
    duration: '8 min',
    description: 'Medición de la percepción del compromiso de la alta dirección, supervisión de campo y cultura de prevención en operaciones.',
    icon: Activity,
  },
  {
    id: 'occupational_health',
    title: 'Salud Ocupacional & Ergonomía',
    version: 'SHORT',
    badge: 'Carga Física y Fatiga',
    badgeColor: 'bg-purple-500/10 text-purple-600 border-purple-500/20',
    items: 28,
    duration: '6 min',
    description: 'Tamizaje de sintomatología musculoesquelética (Cuestionario Nórdico adaptado) y fatiga laboral en turnos de minería.',
    icon: HeartPulse,
  },
];

export default function DashboardPage() {
  const navigate = useNavigate();
  const [selectedInstrument, setSelectedInstrument] = useState(null);

  return (
    <div className="colmena-page space-y-4 text-xs">
      {/* High-Density Header Banner */}
      <div className="rounded-xl border border-border bg-surface p-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber/10 text-amber text-[11px] font-bold uppercase tracking-wider mb-1">
              <Sparkles size={12} /> AURORA PRO — Menú de Instrumentos
            </div>
            <h1 className="text-lg font-bold tracking-tight text-dark">
              Catálogo de Instrumentos de Evaluación
            </h1>
            <p className="text-xs text-muted">
              Selecciona el instrumento para tu empresa, confirma la solicitud y genera directamente el enlace o código QR.
            </p>
          </div>
        </div>
      </div>

      {/* Main Instrument Catalog Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-wider text-muted">
            Catálogo de Instrumentos Disponibles para Solicitar
          </h2>
          <span className="text-[11px] text-muted">Selección rápida en 1 clic</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {CATALOG_INSTRUMENTS.map((inst) => {
            const Icon = inst.icon;
            return (
              <div
                key={inst.id}
                className="flex flex-col justify-between rounded-xl border border-border bg-surface p-4 space-y-3 hover:border-amber/50 hover:shadow-md transition"
              >
                <div className="space-y-2">
                  <div className="flex items-start justify-between gap-1.5">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${inst.badgeColor}`}>
                      {inst.badge}
                    </span>
                    <Icon size={18} className="text-muted shrink-0" />
                  </div>

                  <h3 className="text-sm font-bold text-dark leading-tight">{inst.title}</h3>
                  <p className="text-[11px] text-muted leading-relaxed">{inst.description}</p>
                </div>

                <div className="pt-3 border-t border-border/60 flex items-center justify-between gap-2">
                  <span className="text-[10px] font-semibold text-muted">
                    {inst.items} preguntas · ~{inst.duration}
                  </span>
                  <button
                    type="button"
                    onClick={() => setSelectedInstrument(inst)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-amber hover:bg-amber-600 text-dark font-bold text-xs shadow-sm transition transform active:scale-95 shrink-0"
                  >
                    ⚡ Solicitar
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Confirmation Modal */}
      {selectedInstrument ? (
        <InstrumentConfirmModal
          instrument={selectedInstrument}
          isOpen={Boolean(selectedInstrument)}
          onClose={() => setSelectedInstrument(null)}
          onCreated={(data) => {
            setSelectedInstrument(null);
            navigate(`/colmena/project/${data.project_id}/telemetry`);
          }}
        />
      ) : null}
    </div>
  );
}
