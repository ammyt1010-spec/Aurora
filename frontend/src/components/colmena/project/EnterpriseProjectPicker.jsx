import { Building2 } from 'lucide-react';

/** Contexto compartido de empresa/evaluación para Telemetría e Informe. */
export default function EnterpriseProjectPicker({ projects, selectedId, onChange }) {
  if (!projects.length) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#dfe7f3] bg-white/95 px-4 py-3 shadow-sm">
      <div className="flex items-center gap-2">
        <span className="rounded-lg bg-[#e8efff] p-2 text-[#3154a4]"><Building2 size={18}/></span>
        <div>
          <strong className="block text-xs text-[#1c3156]">Evaluación activa</strong>
          <span className="text-[11px] text-[#72819a]">Selecciona el expediente corporativo</span>
        </div>
      </div>
      <label className="min-w-[210px] flex-1 sm:max-w-sm">
        <span className="sr-only">Seleccionar evaluación empresarial</span>
        <select aria-label="Seleccionar evaluación empresarial"
          value={selectedId == null ? '' : String(selectedId)}
          onChange={(event) => onChange(event.target.value)}
          className="colmena-input w-full text-xs font-bold">
          {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>
      </label>
    </div>
  );
}
