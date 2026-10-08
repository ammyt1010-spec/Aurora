import { useId, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ArrowRight, Check, Eye, EyeOff, FolderKanban, GraduationCap, Lock, Plus, Search, SlidersHorizontal, Users } from 'lucide-react';

import { getCensopasCatalog } from '../../../api/censopas.js';
import { createProject } from '../../../api/projects.js';
import { createCollaboratorCode, joinOrganization, listOrganizations } from '../../../api/organizations.js';
import { cn } from '../../../utils/cn.js';
import { Button } from '../../ui/Button.jsx';
import FormField from '../../ui/FormField.jsx';
import { Modal } from '../../ui/Modal.jsx';

const PROJECT_TYPES = [
  { value: 'CENSO', label: 'CENSOPAS-COPSOQ', description: 'Evaluación psicosocial oficial en versiones Corta (42) y Media (112).', icon: Users },
  { value: 'RESEARCH', label: 'Salud Ocupacional', description: 'Diagnóstico de salud ocupacional, carga física y ergonomía.', icon: Search },
  { value: 'CUSTOM', label: 'Clima & Seguridad', description: 'Clima de seguridad y gestión de prevención minera e industrial.', icon: SlidersHorizontal },
];

const FALLBACK_INSTRUMENTS = [
  { code: 'CENSOPAS_SHORT', name: 'CENSOPAS Corta', questions: 42, psychosocial_questions: 31, dimensions: 6, subdimensions: 0, recommended_population: '<25' },
  { code: 'CENSOPAS_MEDIUM', name: 'CENSOPAS Media', questions: 112, psychosocial_questions: 69, dimensions: 6, subdimensions: 20, recommended_population: '>=25' },
];
const FALLBACK_PLANS = [
  { code: 'STANDARD', name: 'Estándar', description: 'Resultado CENSOPAS y análisis descriptivo.', level: 1, tools: [] },
  { code: 'ADVANCED', name: 'Avanzado', description: 'Inferencia, comparaciones y confiabilidad.', level: 2, tools: [] },
  { code: 'PREMIUM', name: 'Premium', description: 'Analítica multivariada y gestión estratégica.', level: 3, tools: [] },
];

const schema = z.object({
  name: z.string().trim().min(1, 'Ingresa un nombre').max(255),
  projectType: z.enum(['ACADEMIC', 'CENSO', 'RESEARCH', 'CUSTOM']),
  description: z.string().trim().max(1000).optional(),
});
const STEPS = ['Organización', 'Instrumento', 'Analítica', 'Estudio'];

export default function ProjectCreateModal({ ownerUserId, onClose, onCreated }) {
  const formId = useId();
  const queryClient = useQueryClient();
  const { register, handleSubmit, setValue, watch, formState: { errors } } = useForm({
    resolver: zodResolver(schema), defaultValues: { name: '', projectType: 'CENSO', description: '' },
  });
  const selectedType = watch('projectType');
  const isCenso = selectedType === 'CENSO';
  const [step, setStep] = useState(1);
  const [instrumentKind, setInstrumentKind] = useState('SHORT');
  const [analyticsPlan, setAnalyticsPlan] = useState('STANDARD');
  const [organizationId, setOrganizationId] = useState(null);
  const [newOrganization, setNewOrganization] = useState(null);
  const [organizationForm, setOrganizationForm] = useState({ name: '', legal_name: '', tax_id: '', organization_type: '' });
  const [joinCode, setJoinCode] = useState('');
  const [organizationError, setOrganizationError] = useState(null);
  const [generatedCode, setGeneratedCode] = useState(null);
  const [studyContext, setStudyContext] = useState({});
  const { data: memberships = [] } = useQuery({ queryKey: ['organizations'], queryFn: listOrganizations, enabled: isCenso });
  const { data: catalog } = useQuery({ queryKey: ['censopas-catalog'], queryFn: getCensopasCatalog, enabled: isCenso, staleTime: 300000 });
  const instruments = catalog?.instrument_versions?.length ? catalog.instrument_versions : FALLBACK_INSTRUMENTS;
  const plans = catalog?.analytics_plans?.length ? catalog.analytics_plans : FALLBACK_PLANS;

  const joinMutation = useMutation({
    mutationFn: () => joinOrganization(joinCode.trim()),
    onSuccess: (result) => {
      setOrganizationId(result.organization.id); setNewOrganization(null); setJoinCode(''); setOrganizationError(null);
      queryClient.invalidateQueries({ queryKey: ['organizations'] });
    },
    onError: (error) => setOrganizationError(error.message || 'El código no es válido.'),
  });
  const codeMutation = useMutation({
    mutationFn: () => createCollaboratorCode(organizationId, 'Código de colaboración'),
    onSuccess: (result) => setGeneratedCode(result.code),
    onError: (error) => setOrganizationError(error.message || 'No se pudo generar el código.'),
  });
  const mutation = useMutation({
    mutationFn: (values) => {
      if (isCenso && !organizationId && !newOrganization) throw new Error('Selecciona una organización o registra una empresa nueva.');
      return createProject({
        ownerUserId, ...values, organizationId: isCenso ? organizationId : undefined,
        newOrganization: isCenso && newOrganization ? organizationForm : undefined,
        censopasStudy: isCenso ? {
          instrument_version: instrumentKind, analytics_plan: analyticsPlan,
          workplace_name: studyContext.workplace_name || null,
          population_invited: studyContext.population_invited ? Number(studyContext.population_invited) : null,
          period_start: studyContext.period_start || null, period_end: studyContext.period_end || null,
          settings: studyContext,
        } : undefined,
      });
    },
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] }); queryClient.invalidateQueries({ queryKey: ['organizations'] });
      onCreated ? onCreated(project) : onClose();
    },
  });

  const changeType = (value) => { setValue('projectType', value, { shouldValidate: true }); setStep(1); };
  const next = async () => {
    if (step === 1 && isCenso && !organizationId && !newOrganization) { setOrganizationError('Selecciona una organización o registra una empresa nueva.'); return; }
    setStep((current) => Math.min(current + 1, isCenso ? 4 : 1));
  };
  const back = () => setStep((current) => Math.max(current - 1, 1));
  const selectExisting = (id) => { setOrganizationId(Number(id)); setNewOrganization(null); setOrganizationError(null); };

  return <Modal title="Crear proyecto" subtitle={isCenso ? `Paso ${step} de ${STEPS.length}: ${STEPS[step - 1]}` : 'Elige el contexto y Colmena preparará la estructura metodológica inicial.'} icon={FolderKanban} onClose={onClose} size={isCenso && step === 3 ? 'xl' : 'lg'} preventClose={mutation.isPending} footer={<>
    <Button type="button" variant="secondary" size="lg" onClick={onClose}>Cancelar</Button>
    {isCenso && step > 1 ? <Button type="button" variant="secondary" size="lg" onClick={back}><ArrowLeft size={16} />Anterior</Button> : null}
    {isCenso && step < 4 ? <Button type="button" size="lg" onClick={next}>Siguiente<ArrowRight size={16} /></Button> : <Button type="submit" form={formId} size="lg" loading={mutation.isPending}><Plus size={16} />{isCenso ? 'Crear evaluación' : 'Crear proyecto'}</Button>}
  </>}>
    <form id={formId} className="space-y-5" onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate>
      {(!isCenso || step === 1) && <fieldset><legend className="colmena-label mb-2">Tipo de proyecto</legend><input type="hidden" {...register('projectType')} /><div className="grid gap-2 sm:grid-cols-2">{PROJECT_TYPES.map((type) => { const Icon = type.icon; const selected = selectedType === type.value; return <button key={type.value} type="button" aria-pressed={selected} onClick={() => changeType(type.value)} className={cn('flex items-start gap-3 rounded-xl border p-3 text-left', selected ? 'border-amber bg-amber/10' : 'border-border bg-white')}><Icon size={18} className="mt-1 shrink-0 text-amber" /><span><span className="block text-sm font-semibold text-dark">{type.label}</span><span className="block text-xs text-muted">{type.description}</span></span></button>; })}</div></fieldset>}
      {isCenso && step === 1 && <OrganizationStep memberships={memberships} organizationId={organizationId} newOrganization={newOrganization} onSelect={selectExisting} onNew={() => { setNewOrganization({}); setOrganizationId(null); setGeneratedCode(null); setOrganizationError(null); }} organizationForm={organizationForm} setOrganizationForm={setOrganizationForm} joinCode={joinCode} setJoinCode={setJoinCode} joinMutation={joinMutation} codeMutation={codeMutation} generatedCode={generatedCode} error={organizationError} />}
      {isCenso && step === 2 && <InstrumentStep instruments={instruments} selected={instrumentKind} onSelect={setInstrumentKind} />}
      {isCenso && step === 3 && <PlanStep plans={plans} selected={analyticsPlan} onSelect={setAnalyticsPlan} />}
      {isCenso && step === 4 && <StudyStep register={register} errors={errors} context={studyContext} setContext={setStudyContext} />}
      {!isCenso && <><FormField label="Nombre del proyecto" placeholder="Ej. Evaluación de clima y riesgos 2026" error={errors.name?.message} autoFocus {...register('name')} /><FormField label="Descripción (opcional)" error={errors.description?.message} {...register('description')} /></>}
      {mutation.isError ? <p role="alert" className="rounded-xl bg-red-50 px-3 py-2.5 text-sm text-danger">{mutation.error?.message || 'No se pudo crear el proyecto.'}</p> : null}
    </form>
  </Modal>;
}

function OrganizationStep({ memberships, organizationId, newOrganization, onSelect, onNew, organizationForm, setOrganizationForm, joinCode, setJoinCode, joinMutation, codeMutation, generatedCode, error }) {
  const update = (key, value) => setOrganizationForm((current) => ({ ...current, [key]: value }));
  return <fieldset className="space-y-4"><div><legend className="colmena-label mb-2">Organización</legend><p className="text-xs text-muted">El RUC identifica una empresa única. Si ya existe, necesitarás un código de colaborador.</p></div>{memberships.length ? <select className="colmena-input h-10 w-full px-3 text-sm" value={organizationId || ''} onChange={(event) => onSelect(event.target.value)}><option value="">Selecciona una organización</option>{memberships.map((item) => <option key={item.organization.id} value={item.organization.id}>{item.organization.name} · {item.role_code}</option>)}</select> : null}<Button type="button" variant="secondary" onClick={onNew}><Plus size={16} />Registrar nueva empresa</Button>{organizationId && !newOrganization ? <div className="rounded-xl border border-border bg-amber/5 p-4"><p className="text-sm font-semibold text-dark">Invitar colaboradores</p><p className="mt-1 text-xs text-muted">Genera un código permanente para que se incorporen como colaboradores de solo lectura.</p><Button type="button" className="mt-3" variant="secondary" loading={codeMutation.isPending} onClick={() => codeMutation.mutate()}>Generar código</Button>{generatedCode ? <p className="mt-3 rounded-lg bg-white px-3 py-2 font-mono text-sm font-semibold tracking-wide text-dark" role="status">{generatedCode}</p> : null}</div> : null}{newOrganization ? <div className="grid gap-3 rounded-xl border border-border p-4 sm:grid-cols-2"><FormField label="Razón social" value={organizationForm.name} onChange={(event) => update('name', event.target.value)} /><FormField label="RUC" value={organizationForm.tax_id} onChange={(event) => update('tax_id', event.target.value)} /><FormField label="Nombre legal" value={organizationForm.legal_name} onChange={(event) => update('legal_name', event.target.value)} /><FormField label="Sector / tipo" value={organizationForm.organization_type} onChange={(event) => update('organization_type', event.target.value)} /></div> : null}<div className="rounded-xl border border-border bg-surfaceSoft/50 p-4"><p className="text-sm font-semibold text-dark">¿Eres colaborador?</p><p className="mt-1 text-xs text-muted">Ingresa el código permanente que te entregó el administrador.</p><div className="mt-3 flex gap-2"><input className="colmena-input h-10 min-w-0 flex-1 px-3 text-sm" value={joinCode} onChange={(event) => setJoinCode(event.target.value)} placeholder="COL-..." /><Button type="button" variant="secondary" loading={joinMutation.isPending} onClick={() => joinMutation.mutate()}>Unirme</Button></div></div>{error ? <p role="alert" className="text-sm font-medium text-danger">{error}</p> : null}</fieldset>;
}

function InstrumentStep({ instruments, selected, onSelect }) { return <fieldset><legend className="colmena-label mb-2">Instrumento CENSOPAS</legend><p className="mb-3 text-xs text-muted">Premium usa las mismas respuestas; sólo agrega capacidad analítica.</p><div className="grid gap-3 sm:grid-cols-2">{instruments.map((item) => { const kind = item.code.endsWith('MEDIUM') ? 'MEDIUM' : 'SHORT'; return <button key={item.code} type="button" aria-pressed={selected === kind} onClick={() => onSelect(kind)} className={cn('rounded-xl border p-4 text-left', selected === kind ? 'border-amber bg-amber/10' : 'border-border bg-white')}><span className="block text-sm font-semibold text-dark">{item.name}</span><span className="mt-1 block text-xs text-muted">{item.questions} preguntas · {item.psychosocial_questions} psicosociales</span><span className="mt-1 block text-xs text-muted">{item.dimensions} dimensiones · {item.subdimensions} subdimensiones</span><span className="mt-2 block text-xs font-semibold text-amber">Recomendado: población {item.recommended_population}</span></button>; })}</div></fieldset>; }
function PlanStep({ plans, selected, onSelect }) {
  const [detailsCode, setDetailsCode] = useState(null);
  const detailsPlan = plans.find((plan) => plan.code === detailsCode);
  const features = detailsPlan?.tools?.map((tool) => tool.name || tool.code) || [];

  return <fieldset><legend className="colmena-label mb-2">Plan analítico Colmena</legend><p className="mb-3 text-xs text-muted">Define las herramientas disponibles, no el cuestionario. Selecciona una tarjeta o abre el ojo para revisar sus capacidades.</p><div className="grid gap-3 sm:grid-cols-3">{plans.map((plan) => { const isSelected = selected === plan.code; const isOpen = detailsCode === plan.code; return <div key={plan.code} className={cn('rounded-xl border p-4 transition-all duration-200', isSelected ? 'border-amber bg-amber/10 shadow-sm' : 'border-border bg-white hover:border-amber/40')}><div className="flex items-start justify-between gap-3"><button type="button" aria-pressed={isSelected} onClick={() => onSelect(plan.code)} className="min-w-0 flex-1 text-left"><span className="block text-sm font-semibold text-dark">{plan.name}</span><span className="mt-1 block text-xs leading-4 text-muted">{plan.description}</span><span className="mt-3 block text-xs font-medium text-amber">{plan.tools?.length || 0} herramientas habilitadas</span></button><button type="button" aria-label={isOpen ? `Ocultar detalles de ${plan.name}` : `Ver detalles de ${plan.name}`} aria-expanded={isOpen} onClick={() => setDetailsCode(isOpen ? null : plan.code)} className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border transition-colors', isOpen ? 'border-amber bg-amber text-white' : 'border-border bg-white text-muted hover:border-amber hover:text-amber')}>{isOpen ? <EyeOff size={15} /> : <Eye size={15} />}</button></div></div>; })}</div><div aria-live="polite" className={cn('mx-auto overflow-hidden transition-all duration-300 ease-out', detailsPlan ? 'mt-4 max-h-[520px] translate-y-0 opacity-100' : 'max-h-0 -translate-y-2 opacity-0')}><div className="mx-auto max-w-3xl rounded-2xl border border-amber/30 bg-gradient-to-b from-amber/10 to-white p-5 shadow-sm"><div className="flex items-start justify-between gap-3"><div><p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber">Detalle del plan</p><h3 className="mt-1 text-base font-bold text-dark">{detailsPlan?.name}</h3><p className="mt-1 max-w-2xl text-xs leading-5 text-muted">{detailsPlan?.description}</p></div><span className="rounded-full bg-amber/15 px-2.5 py-1 text-xs font-semibold text-amber">Nivel {detailsPlan?.level}</span></div><div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{features.map((feature) => <div key={feature} className="flex items-center gap-2 rounded-lg border border-border/80 bg-white px-3 py-2 text-xs text-dark"><Check size={14} className="shrink-0 text-amber" />{feature}</div>)}{!features.length ? <p className="col-span-full text-xs text-muted">Las capacidades se cargarán desde el catálogo analítico.</p> : null}</div></div></div></fieldset>;
}
function StudyStep({ register, errors, context, setContext }) { const field = (key, label, type = 'text') => <label className="flex flex-col gap-1.5"><span className="text-xs font-medium text-muted">{label}</span><input type={type} className="colmena-input h-10 px-3 text-sm" value={context[key] || ''} onChange={(event) => setContext((current) => ({ ...current, [key]: event.target.value }))} /></label>; return <><FormField label="Nombre del proyecto / estudio" error={errors.name?.message} autoFocus {...register('name')} /><FormField label="Descripción (opcional)" error={errors.description?.message} {...register('description')} /><fieldset><legend className="colmena-label mb-2">Configuración del estudio</legend><div className="grid gap-3 sm:grid-cols-2">{field('workplace_name', 'Centro laboral')}{field('population_invited', 'Población invitada', 'number')}{field('period_start', 'Inicio del período', 'date')}{field('period_end', 'Fin del período', 'date')}</div></fieldset><div className="flex items-start gap-3 rounded-xl border border-border bg-white p-4"><Lock size={16} className="mt-1 text-amber" /><p className="text-xs text-muted">Las preguntas núcleo quedan protegidas y no editables.</p></div></>; }
