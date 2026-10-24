import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { QRCodeSVG } from 'qrcode.react';
import { Check, Copy, Layers3, QrCode } from 'lucide-react';
import { listStudies } from '../../../api/studies.js';
import { createEvaluationBundle } from '../../../api/evaluationBundles.js';

/** Inicio: batería formada exclusivamente por estudios realmente habilitados. */
export default function BundleSelectionPanel({ projects }) {
  const [projectId, setProjectId] = useState('');
  const [selected, setSelected] = useState([]);
  const [generated, setGenerated] = useState(null);
  const [copyStatus, setCopyStatus] = useState('');

  useEffect(() => {
    if (!projects.length) { setProjectId(''); return; }
    if (!projects.some(item => String(item.id) === projectId)) {
      setProjectId(String(projects[0].id));
    }
  }, [projects, projectId]);
  useEffect(() => {
    setSelected([]);
    setGenerated(null);
    setCopyStatus('');
  }, [projectId]);

  const studiesQuery = useQuery({
    queryKey: ['aurora-battery-studies', projectId],
    queryFn: () => listStudies(projectId, {page:1,pageSize:100}),
    enabled: Boolean(projectId),
    retry: false,
  });
  const now = Date.now();
  const eligible = (studiesQuery.data?.items || []).filter(study => {
    if (study.status !== 'OPEN' || study.requires_invitation || !study.public_id ||
        !study.instrument_version_id) return false;
    if (study.start_at && new Date(study.start_at).getTime() > now) return false;
    if (study.end_at && new Date(study.end_at).getTime() < now) return false;
    return true;
  });
  const create = useMutation({
    mutationFn: () => createEvaluationBundle(projectId, {
      label: ('Batería empresarial · ' + (projects.find(p=>String(p.id)===projectId)?.name || 'AURORA')).slice(0,180),
      study_ids:selected,
    }),
    onSuccess: (result) => {setGenerated(result);setCopyStatus('');},
  });
  const url = generated?.public_id
    ? window.location.origin + '/bateria/' + generated.public_id : '';

  if (!projects.length) {
    return (
      <section className="rounded-xl border border-[#DDE7F1] bg-white p-4">
        <h2 className="text-sm font-bold text-[#0A1F44]">Selecciona tus instrumentos</h2>
        <p className="mt-1 text-xs text-[#64748B]">Primero registra una evaluación empresarial. Los instrumentos autorizados estarán disponibles para generar su enlace conjunto.</p>
      </section>
    );
  }
  return (
    <section aria-label="Seleccionar instrumentos de batería" className="rounded-xl border border-[#D9E6F1] bg-white p-3.5 shadow-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-1.5 text-xs font-extrabold text-[#0A1F44]">
          <Layers3 size={15} className="text-[#2B69A5]"/> Instrumentos de la batería
        </h2>
        <label className="flex min-w-0 items-center gap-1.5 text-[11px] font-semibold text-[#426282]">
          Empresa
          <select value={projectId} onChange={e=>setProjectId(e.target.value)}
            aria-label="Empresa para la batería"
            className="min-w-0 max-w-[280px] rounded-lg border border-[#D8E3EF] bg-white px-2.5 py-1 text-xs">
            {projects.map(project=><option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
        </label>
      </div>
      <p className="mt-0.5 text-[10px] text-[#64748B]">Marca las evaluaciones abiertas para generar un solo enlace y código QR.</p>
      {studiesQuery.isLoading && <p role="status" className="mt-2 text-xs">Buscando instrumentos habilitados…</p>}
      {studiesQuery.isError && <p role="alert" className="mt-2 text-xs text-red-700">No se pudieron consultar las evaluaciones habilitadas. Comprueba los permisos.</p>}
      {!studiesQuery.isLoading && !studiesQuery.isError && !eligible.length && (
        <p className="mt-2 text-xs text-[#64748B]">No hay instrumentos abiertos y habilitados en esta empresa. Deben configurarse antes de generar la batería.</p>
      )}
      <fieldset className="mt-2 grid max-h-[140px] grid-cols-1 gap-2 overflow-y-auto sm:grid-cols-2 xl:grid-cols-3">
        <legend className="sr-only">Instrumentos disponibles para la batería</legend>
        {eligible.map(study=>{
          const checked = selected.includes(study.id);
          return (
            <label key={study.id} className={'flex cursor-pointer items-center gap-2.5 rounded-lg border px-2.5 py-2 text-xs ' +
              (checked ? 'border-[#59BFD3] bg-[#EDF9FB]' : 'border-[#E0E8F1] bg-[#FAFCFF]')}>
              <input type="checkbox" className="shrink-0" checked={checked}
                onChange={e=>setSelected(prev=>e.target.checked ?
                  (prev.length < 12 ? [...prev,study.id] : prev) :
                  prev.filter(x=>x!==study.id))}/>
              <span className="min-w-0 flex-1">
                <strong className="block truncate text-[11px] text-[#193D67]">{study.instrument_name || study.name}</strong>
                <small className="block truncate text-[10px] text-[#6B7C91]">{study.name}</small>
              </span>
              {checked && <Check size={14} className="text-[#108B91]"/>}
            </label>
          );
        })}
      </fieldset>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-[#E8EFF5] pt-2">
        <span className="text-xs font-bold text-[#426282]">{selected.length} seleccionados</span>
        <button type="button" disabled={selected.length < 2 || selected.length > 12 || create.isPending}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[#0A1F44] px-3.5 py-1.5 text-xs font-bold text-white disabled:opacity-40"
          onClick={()=>create.mutate()}>
          <QrCode size={14}/>{create.isPending ? 'Creando…' : 'Generar enlace y QR'}
        </button>
      </div>
      {create.isError && <p role="alert" className="mt-1.5 text-xs text-red-700">{create.error?.message || 'No se pudo emitir la batería.'}</p>}
      {url && <div className="mt-2 flex flex-wrap items-center gap-3 rounded-lg border border-[#CFE7F1] bg-[#F3FBFF] p-2.5">
        <QRCodeSVG value={url} size={68} aria-label="Código QR de batería empresarial"/>
        <div className="min-w-0 flex-1">
          <strong className="block text-xs text-[#224A74]">Enlace de batería generado</strong>
          <a href={url} target="_blank" rel="noreferrer" className="mt-0.5 block break-all text-xs text-[#256CAA] underline">{url}</a>
          <button type="button" className="mt-1.5 inline-flex items-center gap-1 text-xs font-bold text-[#285994]"
            onClick={async()=>{
              try{await navigator.clipboard.writeText(url);setCopyStatus('Copiado');}
              catch{setCopyStatus('No se pudo copiar el enlace');}
            }}><Copy size={12}/> Copiar enlace</button>
          {copyStatus && <span role="status" className="ml-2 text-xs">{copyStatus}</span>}
        </div>
      </div>}
    </section>
  );
}
