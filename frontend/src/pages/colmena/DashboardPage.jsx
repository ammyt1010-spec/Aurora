import { useState } from 'react';
import {
  Activity,
  ArrowRight,
  BarChart3,
  Check,
  FileCheck2,
  Gauge,
  HeartPulse,
  LockKeyhole,
  Radar,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react';

import InstrumentConfirmModal from '../../components/colmena/projects/InstrumentConfirmModal.jsx';
import { BrandMark } from '../../brand/BrandMark.jsx';

const CATALOG_INSTRUMENTS = [
  {
    id: 'censopas_short',
    title: 'CENSOPAS · Versión corta',
    version: 'SHORT',
    badge: 'Hasta 24 trabajadores',
    accent: 'from-cyan-400 via-sky-500 to-indigo-500',
    items: 42,
    duration: '10 min',
    description: 'Aplicación ágil para pequeñas empresas, con baremación, telemetría anónima y expediente técnico consolidado.',
    icon: ShieldCheck,
    highlights: ['6 dimensiones', 'Resultados por nivel', 'Reporte técnico'],
  },
  {
    id: 'censopas_medium',
    title: 'CENSOPAS · Versión media',
    version: 'MEDIUM',
    badge: 'Desde 25 trabajadores',
    accent: 'from-violet-500 via-fuchsia-500 to-rose-500',
    items: 112,
    duration: '20 min',
    description: 'Evaluación ampliada para minería, industria y organizaciones complejas, con lectura por 20 subdimensiones.',
    icon: Gauge,
    recommended: true,
    highlights: ['20 subdimensiones', 'Pruebas avanzadas', 'Analítica multivariable'],
  },
];

const ROADMAP_INSTRUMENTS = [
  {
    id: 'safety_climate',
    title: 'Clima de Seguridad Industrial',
    badge: 'Próxima incorporación',
    description: 'Cultura preventiva, liderazgo visible y prácticas críticas de operación.',
    icon: Activity,
  },
  {
    id: 'occupational_health',
    title: 'Salud ocupacional y ergonomía',
    badge: 'Próxima incorporación',
    description: 'Carga física, fatiga laboral y factores ergonómicos asociados al puesto.',
    icon: HeartPulse,
  },
];

const CORPORATE_CAPABILITIES = [
  { icon: LockKeyhole, title: 'Anonimato protegido', copy: 'Supresión de grupos pequeños y acceso por enlace seguro.' },
  { icon: BarChart3, title: 'Telemetría en vivo', copy: 'Participación, avance y calidad de respuesta sin identificar personas.' },
  { icon: Radar, title: 'Analítica profunda', copy: 'Confiabilidad, normalidad, efecto, correlaciones y segmentación.' },
  { icon: FileCheck2, title: 'Expediente técnico', copy: 'Informe estructurado con anexos, firmas y plan preventivo.' },
];

export default function DashboardPage() {
  const [selectedInstrument, setSelectedInstrument] = useState(null);

  return (
    <div className="aurora-page-shell colmena-page gap-6 px-4 py-5 text-xs sm:px-6 lg:px-8">
      <section className="aurora-hero relative overflow-hidden rounded-[28px] border border-white/60 px-5 py-6 shadow-[0_24px_80px_rgba(35,30,90,0.12)] sm:px-8 sm:py-8 lg:px-10">
        <div className="aurora-orb aurora-orb-one" />
        <div className="aurora-orb aurora-orb-two" />
        <div className="relative z-[1] grid items-center gap-8 lg:grid-cols-[1.25fr_.75fr]">
          <div className="max-w-3xl">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-violet-200/70 bg-white/70 px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.16em] text-violet-700 shadow-sm backdrop-blur-xl">
              <Sparkles size={13} /> Plataforma de inteligencia psicosocial
            </div>
            <h1 className="max-w-[760px] text-[30px] font-black leading-[1.08] tracking-[-0.04em] text-slate-950 sm:text-[40px] lg:text-[48px]">
              Del cuestionario a una decisión corporativa clara.
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-600 sm:text-[15px]">
              Aurora integra aplicación anónima, telemetría, estadística avanzada y expediente técnico en un solo flujo preparado para empresas peruanas.
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => setSelectedInstrument(CATALOG_INSTRUMENTS[1])}
                className="aurora-primary-action"
              >
                Crear mi informe gratuito <ArrowRight size={16} />
              </button>
              <span className="inline-flex items-center gap-2 text-[11px] font-semibold text-slate-600">
                <ShieldCheck size={15} className="text-emerald-500" /> Sin tarjeta · 1 informe completo por empresa
              </span>
            </div>
          </div>

          <div className="relative mx-auto flex min-h-[220px] w-full max-w-[330px] items-center justify-center">
            <div className="absolute h-44 w-44 rounded-full bg-violet-400/20 blur-3xl" />
            <BrandMark className="relative h-48 w-40 drop-shadow-[0_22px_35px_rgba(93,75,210,0.28)]" />
            <div className="absolute bottom-3 left-0 rounded-2xl border border-white/70 bg-white/75 px-4 py-3 shadow-xl backdrop-blur-xl">
              <p className="text-[9px] font-black uppercase tracking-[0.14em] text-slate-400">Cobertura inicial</p>
              <p className="mt-1 text-lg font-black text-slate-950">250 trabajadores</p>
            </div>
            <div className="absolute right-0 top-4 rounded-2xl border border-white/70 bg-white/75 px-4 py-3 shadow-xl backdrop-blur-xl">
              <p className="text-[9px] font-black uppercase tracking-[0.14em] text-slate-400">Privacidad</p>
              <p className="mt-1 flex items-center gap-1.5 text-sm font-black text-emerald-600"><LockKeyhole size={14} /> Anónimo</p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {CORPORATE_CAPABILITIES.map(({ icon: Icon, title, copy }) => (
          <article key={title} className="aurora-glass-card group p-4">
            <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/15 to-cyan-500/15 text-violet-600 transition group-hover:scale-105">
              <Icon size={18} />
            </div>
            <h2 className="text-[13px] font-extrabold text-slate-950 dark:text-white">{title}</h2>
            <p className="mt-1 text-[11px] leading-5 text-muted">{copy}</p>
          </article>
        ))}
      </section>

      <section className="space-y-4">
        <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-violet-600">Instrumentos disponibles</p>
            <h2 className="mt-1 text-xl font-black tracking-tight text-dark">Elige la evaluación adecuada</h2>
            <p className="mt-1 text-xs text-muted">Ambas versiones incluyen el recorrido completo de Aurora y un informe gratuito por RUC.</p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-[10px] font-bold text-emerald-700">
            <Check size={13} /> CENSOPAS configurado y listo
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {CATALOG_INSTRUMENTS.map((inst) => {
            const Icon = inst.icon;
            return (
              <article key={inst.id} className="aurora-instrument-card relative overflow-hidden rounded-[24px] border border-white/70 bg-white/80 p-5 shadow-[0_18px_45px_rgba(29,25,70,0.08)] backdrop-blur-xl sm:p-6">
                <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${inst.accent}`} />
                <div className="flex items-start justify-between gap-4">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-950 text-white shadow-lg">
                    <Icon size={20} />
                  </div>
                  <div className="flex flex-wrap justify-end gap-2">
                    {inst.recommended ? <span className="rounded-full bg-violet-600 px-2.5 py-1 text-[9px] font-black uppercase tracking-wider text-white">Más completa</span> : null}
                    <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[9px] font-bold text-slate-600">{inst.badge}</span>
                  </div>
                </div>
                <h3 className="mt-5 text-lg font-black tracking-tight text-dark">{inst.title}</h3>
                <p className="mt-2 min-h-[44px] text-[12px] leading-5 text-muted">{inst.description}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {inst.highlights.map((item) => (
                    <span key={item} className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-2.5 py-1.5 text-[10px] font-semibold text-slate-600">
                      <Check size={11} className="text-emerald-500" /> {item}
                    </span>
                  ))}
                </div>
                <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4">
                  <span className="text-[10px] font-bold text-muted">{inst.items} preguntas · {inst.duration}</span>
                  <button type="button" onClick={() => setSelectedInstrument(inst)} className="aurora-card-action">
                    Comenzar <ArrowRight size={14} />
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="rounded-[24px] border border-slate-200/80 bg-slate-950 p-5 text-white shadow-2xl sm:p-6">
        <div className="grid gap-5 lg:grid-cols-[.8fr_1.2fr] lg:items-center">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-cyan-300">Arquitectura expandible</p>
            <h2 className="mt-2 text-xl font-black">Aurora crecerá con tu operación.</h2>
            <p className="mt-2 max-w-lg text-xs leading-5 text-slate-400">Los siguientes instrumentos se integrarán de forma modular, conservando el mismo expediente, comparabilidad y gobierno de datos.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {ROADMAP_INSTRUMENTS.map(({ id, title, badge, description, icon: Icon }) => (
              <article key={id} className="rounded-2xl border border-white/10 bg-white/[0.06] p-4">
                <div className="flex items-center justify-between gap-3">
                  <Icon size={18} className="text-cyan-300" />
                  <span className="rounded-full border border-white/10 bg-white/[0.06] px-2 py-1 text-[8px] font-bold uppercase tracking-wider text-slate-300">{badge}</span>
                </div>
                <h3 className="mt-3 text-sm font-bold">{title}</h3>
                <p className="mt-1 text-[10px] leading-4 text-slate-400">{description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {selectedInstrument ? (
        <InstrumentConfirmModal
          instrument={selectedInstrument}
          isOpen={Boolean(selectedInstrument)}
          onClose={() => setSelectedInstrument(null)}
        />
      ) : null}
    </div>
  );
}
