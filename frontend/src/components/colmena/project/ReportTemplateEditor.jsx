import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileText, Plus, Save, ShieldCheck } from 'lucide-react';

import { createReportTemplate, listReportTemplates, updateReportTemplate } from '../../../api/reports.js';
import { Card } from '../../ui/Card.jsx';

const DISCIPLINES = [
  { value: 'PSICOSOCIAL', label: 'Riesgos psicosociales' },
  { value: 'ERGONOMIA', label: 'Ergonomía' },
  { value: 'CLIMA', label: 'Clima organizacional' },
];
const SECTIONS = [
  ['portada', 'Portada'],
  ['resumen_ejecutivo', 'Resumen ejecutivo'],
  ['ficha_tecnica', 'Ficha técnica'],
  ['calidad_datos', 'Calidad de datos'],
  ['resultados_globales', 'Resultados por constructo'],
  ['hallazgos_premium', 'Análisis complementario'],
  ['plan_accion', 'Plan de acción'],
  ['conclusiones', 'Conclusiones'],
  ['anexos', 'Anexos'],
  ['firmas', 'Firmas'],
];
const DEFAULT_SECTIONS = SECTIONS.map(([code]) => code);

export default function ReportTemplateEditor() {
  const qc = useQueryClient();
  const { data: templates = [], isLoading, isError } = useQuery({
    queryKey: ['enterprise-report-templates'],
    queryFn: () => listReportTemplates(),
  });
  const [selectedId, setSelectedId] = useState('');
  const [name, setName] = useState('');
  const [discipline, setDiscipline] = useState('PSICOSOCIAL');
  const [header, setHeader] = useState('');
  const [palette, setPalette] = useState('aurora-amber');
  const [sections, setSections] = useState(DEFAULT_SECTIONS);
  const [notice, setNotice] = useState('');

  const load = (template) => {
    const config = template?.template_config || {};
    setSelectedId(template ? String(template.id) : 'new');
    setName(template?.name || '');
    setDiscipline(config.discipline || template?.discipline || 'PSICOSOCIAL');
    setHeader(config.header_title || '');
    setPalette(config.palette || 'aurora-amber');
    setSections(Array.isArray(config.sections) ? [...config.sections] : DEFAULT_SECTIONS);
    setNotice('');
  };

  useEffect(() => {
    if (!selectedId && templates.length > 0) load(templates[0]);
  }, [templates, selectedId]);

  const save = useMutation({
    mutationFn: async () => {
      const cleanName = name.trim();
      const cleanHeader = header.trim();
      if (!cleanName || !cleanHeader || !sections.length) {
        throw new Error('Completa el nombre, el título de portada y al menos una sección.');
      }
      const config = {
        discipline,
        header_title: cleanHeader,
        palette,
        sections,
      };
      if (selectedId === 'new') {
        return createReportTemplate({
          name: cleanName,
          discipline,
          report_type: discipline,
          template_config: config,
        });
      }
      return updateReportTemplate(Number(selectedId), {
        name: cleanName,
        discipline,
        report_type: discipline,
        template_config: config,
      });
    },
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ['enterprise-report-templates'] });
      load(saved);
      setNotice('Plantilla guardada en AURORA. Se aplicará a los próximos informes.');
    },
    onError: (error) => setNotice(error.message || 'No fue posible guardar la plantilla.'),
  });

  const toggleSection = (code) => {
    setSections((current) => (
      current.includes(code) ? current.filter((value) => value !== code) : [...current, code]
    ));
  };

  return (
    <Card className="space-y-5 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <FileText size={20} className="text-amber" />
          <div>
            <h2 className="text-base font-bold text-dark">Editor de plantillas de informes</h2>
            <p className="text-xs text-muted">Administración central · Configuración aplicada a Word y PDF</p>
          </div>
        </div>
        <button type="button" onClick={() => load(null)}
          className="inline-flex items-center gap-2 rounded-xl border border-border px-3 py-2 text-xs font-bold text-dark hover:bg-surfaceSoft">
          <Plus size={14} /> Nueva plantilla
        </button>
      </div>
      {isLoading && <p className="text-xs text-muted">Cargando plantillas…</p>}
      {isError && <p role="alert" className="text-xs text-danger">No se pudo cargar el catálogo de plantillas.</p>}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
          <label className="block text-xs font-semibold text-muted" htmlFor="template-selector">Plantilla</label>
          <select id="template-selector" className="colmena-input w-full" value={selectedId}
            onChange={(event) => {
              const option = templates.find((item) => String(item.id) === event.target.value);
              load(option || null);
            }}>
            <option value="">Seleccionar una plantilla</option>
            <option value="new">Crear nueva</option>
            {templates.map((template) => (
              <option value={template.id} key={template.id}>{template.name}</option>
            ))}
          </select>
          <label className="block text-xs font-semibold text-muted" htmlFor="template-name">Nombre de la plantilla</label>
          <input id="template-name" className="colmena-input w-full" required maxLength={255}
            value={name} onChange={(event) => setName(event.target.value)} />
          <label className="block text-xs font-semibold text-muted" htmlFor="template-discipline">Disciplina</label>
          <select id="template-discipline" className="colmena-input w-full" value={discipline}
            onChange={(event) => setDiscipline(event.target.value)}>
            {DISCIPLINES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
          <label className="block text-xs font-semibold text-muted" htmlFor="template-header">Título de portada</label>
          <input id="template-header" className="colmena-input w-full" required maxLength={180}
            value={header} onChange={(event) => setHeader(event.target.value)} />
          <label className="block text-xs font-semibold text-muted" htmlFor="template-palette">Paleta</label>
          <select id="template-palette" className="colmena-input w-full" value={palette}
            onChange={(event) => setPalette(event.target.value)}>
            <option value="aurora-amber">Ámbar profesional</option>
            <option value="aurora-teal">Turquesa técnico</option>
            <option value="aurora-indigo">Índigo corporativo</option>
          </select>
          <fieldset className="space-y-2 rounded-xl border border-border p-3">
            <legend className="px-1 text-xs font-bold text-dark">Secciones del documento</legend>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {SECTIONS.map(([code, label]) => (
                <label key={code} className="flex items-center gap-2 text-xs text-dark">
                  <input type="checkbox" checked={sections.includes(code)}
                    onChange={() => toggleSection(code)} />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
          <button type="submit" disabled={save.isPending || !selectedId}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-amber px-4 py-3 text-xs font-bold text-dark transition hover:brightness-105 disabled:opacity-50">
            <Save size={15} /> {save.isPending ? 'Guardando…' : 'Guardar plantilla'}
          </button>
          {notice && <p role="status" className="text-xs text-muted">{notice}</p>}
        </form>
        <div className="rounded-2xl border border-border bg-surfaceSoft p-4">
          <p className="mb-3 text-xs font-bold uppercase tracking-widest text-muted">Vista previa de composición</p>
          <div className="mx-auto aspect-[210/297] w-full max-w-[360px] overflow-hidden rounded-lg border border-border bg-white shadow-xl">
            <div className={`h-3 w-full ${palette === 'aurora-teal' ? 'bg-teal-700' : palette === 'aurora-indigo' ? 'bg-indigo-700' : 'bg-amber'}`} />
            <div className="space-y-5 px-5 pt-12 text-center">
              <p className="text-[9px] font-bold tracking-[0.2em] text-muted">AURORA PROFESSIONAL</p>
              <p className="break-words text-lg font-extrabold leading-tight text-dark">
                {header || 'Título del informe profesional'}
              </p>
              <p className="text-xs font-semibold text-muted">
                {DISCIPLINES.find((item) => item.value === discipline)?.label || discipline}
              </p>
              <div className="h-px bg-border" />
              <p className="text-left text-[10px] font-semibold text-dark">Secciones seleccionadas</p>
              <div className="space-y-1 text-left">
                {SECTIONS.filter(([code]) => sections.includes(code)).slice(0, 7).map(([code, label]) => (
                  <div key={code} className="rounded border border-border/70 px-2 py-1 text-[9px] text-muted">{label}</div>
                ))}
              </div>
            </div>
          </div>
          <p className="mt-3 flex items-start gap-2 text-[11px] text-muted">
            <ShieldCheck size={14} className="shrink-0" />
            Composición orientativa. El visor PDF mostrará el renderizado final con datos válidos.
          </p>
        </div>
      </div>
    </Card>
  );
}
