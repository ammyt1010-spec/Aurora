import { useMemo, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { QRCodeSVG } from 'qrcode.react';
import { CheckCircle2, Copy, ExternalLink } from 'lucide-react';

import { apiRequest } from '../../../api/client.js';
import { Modal } from '../../ui/Modal.jsx';
import { Button } from '../../ui/Button.jsx';
import { setActiveProjectId } from '../../../utils/activeProject.js';
import { setActiveStudyId } from '../../../utils/activeStudy.js';

export default function InstrumentCartModal({ instruments, isOpen, onClose }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [copiedUrl, setCopiedUrl] = useState('');
  const [form, setForm] = useState({
    company_name: '',
    company_ruc: '',
    company_sector: 'SERVICES',
    population_invited: 25,
  });

  const selected = useMemo(() => instruments || [], [instruments]);
  const createEvaluations = useMutation({
    mutationFn: async (company) => {
      const created = [];
      for (const instrument of selected) {
        const evaluation = await apiRequest('/quick-eval', {
          method: 'POST',
          body: {
            ...company,
            population_invited: Number(company.population_invited) || 1,
            instrument_version: instrument.version_kind,
            study_name: `${company.company_name} · ${instrument.title}`.slice(0, 255),
          },
        });
        created.push({ instrument, evaluation });
      }
      return created;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['telemetry-module-projects'] });
      queryClient.invalidateQueries({ queryKey: ['reports-module-projects'] });
    },
  });

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const handleClose = () => {
    createEvaluations.reset();
    setCopiedUrl('');
    onClose?.();
  };

  const openTracking = (evaluation) => {
    setActiveProjectId(evaluation.project_id);
    setActiveStudyId(evaluation.project_id, evaluation.study_id);
    handleClose();
    navigate('/colmena/telemetry');
  };

  if (!isOpen || !selected.length) return null;

  return (
    <Modal onClose={handleClose} title={createEvaluations.data ? 'Paso 2 · Comparte los enlaces' : 'Datos de la empresa'}>
      {!createEvaluations.data ? (
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            createEvaluations.mutate(form);
          }}
        >
          <p className="text-xs text-muted">
            Completa estos datos una vez. Aurora generará {selected.length === 1 ? 'el enlace del instrumento' : 'un enlace independiente por instrumento'}.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="colmena-label">Razón social
              <input className="colmena-input mt-1" name="company_name" required value={form.company_name} onChange={handleChange} />
            </label>
            <label className="colmena-label">RUC
              <input className="colmena-input mt-1" name="company_ruc" required minLength={3} value={form.company_ruc} onChange={handleChange} />
            </label>
            <label className="colmena-label">Sector
              <select className="colmena-input mt-1" name="company_sector" value={form.company_sector} onChange={handleChange}>
                <option value="SERVICES">Servicios y comercio</option>
                <option value="MINING">Minería e hidrocarburos</option>
                <option value="INDUSTRIAL">Industria y manufactura</option>
                <option value="CONSTRUCTION">Construcción y energía</option>
                <option value="HEALTH">Salud</option>
              </select>
            </label>
            <label className="colmena-label">Cantidad de trabajadores
              <input className="colmena-input mt-1" name="population_invited" type="number" min="1" max="10000" required value={form.population_invited} onChange={handleChange} />
            </label>
          </div>
          <div className="rounded-xl border border-border bg-surfaceSoft p-3">
            <strong className="text-xs text-dark">Instrumentos seleccionados</strong>
            <ul className="mt-1.5 space-y-1 text-xs text-muted">
              {selected.map((instrument) => <li key={instrument.instrument_version_id}>• {instrument.title}</li>)}
            </ul>
          </div>
          {createEvaluations.isError ? <p role="alert" className="text-xs text-red-600">{createEvaluations.error?.message || 'No se pudieron generar los enlaces.'}</p> : null}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" size="sm" onClick={handleClose}>Cancelar</Button>
            <Button type="submit" size="sm" disabled={createEvaluations.isPending}>
              {createEvaluations.isPending ? 'Generando…' : 'Generar enlace y QR'}
            </Button>
          </div>
        </form>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-emerald-700">
            <CheckCircle2 size={20} />
            <strong>Enlaces listos para compartir</strong>
          </div>
          <p className="text-xs text-muted">Comparte cada enlace o QR con los trabajadores. Luego abre «Ver respuestas» para seguir esa evaluación.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {createEvaluations.data.map(({ instrument, evaluation }) => {
              const url = `${window.location.origin}${evaluation.survey_url}`;
              return (
                <article key={evaluation.study_id} className="rounded-xl border border-border bg-white p-3">
                  <strong className="block text-xs text-dark">{instrument.title}</strong>
                  <div className="mx-auto my-3 w-fit rounded-lg border border-border bg-white p-2">
                    <QRCodeSVG value={url} size={126} marginSize={1} />
                  </div>
                  <a className="block break-all text-[11px] text-blue-700 underline" href={url} target="_blank" rel="noreferrer">{url}</a>
                  <div className="mt-2 flex gap-3">
                    <button type="button" className="inline-flex items-center gap-1 text-xs font-bold text-[#285994]" onClick={async () => {
                      await navigator.clipboard.writeText(url);
                      setCopiedUrl(url);
                    }}><Copy size={12}/>{copiedUrl === url ? 'Copiado' : 'Copiar'}</button>
                    <a className="inline-flex items-center gap-1 text-xs font-bold text-[#285994]" href={url} target="_blank" rel="noreferrer"><ExternalLink size={12}/>Abrir</a>
                  </div>
                  <button type="button" onClick={() => openTracking(evaluation)}
                    className="mt-3 w-full rounded-lg bg-[#0A1F44] px-3 py-2 text-xs font-bold text-white transition hover:bg-[#163A63]">
                    Ver respuestas →
                  </button>
                </article>
              );
            })}
          </div>
          <div className="flex justify-end"><Button size="sm" onClick={handleClose}>Cerrar</Button></div>
        </div>
      )}
    </Modal>
  );
}
