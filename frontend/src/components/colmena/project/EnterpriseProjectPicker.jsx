import { Building2 } from 'lucide-react';

/** Contexto compartido de empresa/evaluación para Telemetría e Informe. */
export default function EnterpriseProjectPicker({ projects, selectedId, onChange }) {
  if (!projects.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-[#dfe7f3] bg-white/95 px-3 py-2 shadow-sm">
      <label htmlFor="aurora-project-switcher" className="flex items-center gap-1.5 text-xs font-bold text-[#294A7A]">
        <Building2 size={15}/> Empresa
      </label>
      <div className="min-w-[210px] flex-1">
        <select id="aurora-project-switcher" aria-label="Seleccionar evaluación empresarial"
          value={selectedId == null ? '' : String(selectedId)}
          onChange={(event) => onChange(event.target.value)}
          className="colmena-input w-full text-xs font-bold">
          {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>
      </div>
    </div>
  );
}
