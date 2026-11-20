import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { QRCodeSVG } from 'qrcode.react';
import { CheckCircle2, Copy, ExternalLink } from 'lucide-react';

import { apiRequest } from '../../../api/client.js';
import { Modal } from '../../ui/Modal.jsx';
import { Button } from '../../ui/Button.jsx';
import { setActiveProjectId } from '../../../utils/activeProject.js';
import { setActiveStudyId } from '../../../utils/activeStudy.js';
import { getPaymentInstructions, getEvaluationAccess } from '../../../api/billing.js';
import { publicUrl } from '../../../utils/publicUrl.js';

const PRICE_METHODS = { SHORT: 'CENSOPAS_CORTA', MEDIUM: 'CENSOPAS_MEDIA' };

function priceFor(tariffs, versionKind, workers) {
  return tariffs.find((tariff) => tariff.active && tariff.method_code === PRICE_METHODS[versionKind]
    && tariff.min_workers <= workers && (tariff.max_workers == null || workers <= tariff.max_workers));
}

export default function InstrumentCartModal({ instruments, isOpen, onClose, trialRemaining, tariffs = [], companyProfile = null }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [copiedUrl, setCopiedUrl] = useState('');
  const [accessOverrides, setAccessOverrides] = useState({});
  const [checkingStudyId, setCheckingStudyId] = useState(null);
  const [activationError, setActivationError] = useState('');
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
        try {
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
        } catch (error) {
          created.push({ instrument, error: error.message || 'No se pudo crear esta evaluación.' });
        }
      }
      return created;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['telemetry-module-projects'] });
      queryClient.invalidateQueries({ queryKey: ['reports-module-projects'] });
      queryClient.invalidateQueries({ queryKey: ['aurora-trial-status'] });
    },
  });
  const { data: paymentInstructions } = useQuery({
    queryKey: ['aurora-payment-instructions'],
    queryFn: getPaymentInstructions,
    enabled: isOpen && Boolean(createEvaluations.data?.some(({ evaluation }) => evaluation?.payment_required)),
    retry: false,
  });

  useEffect(() => {
    if (companyProfile && isOpen && !createEvaluations.data) {
      setForm((current) => ({ ...current,
        company_name: companyProfile.legal_name || companyProfile.name || current.company_name,
        company_ruc: companyProfile.tax_id || current.company_ruc,
        population_invited: companyProfile.declared_workers || current.population_invited,
      }));
    }
  }, [companyProfile, isOpen, createEvaluations.data]);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const handleClose = () => {
    createEvaluations.reset();
    setCopiedUrl('');
    setAccessOverrides({});
    setActivationError('');
    onClose?.();
  };

  const openTracking = (evaluation) => {
    setActiveProjectId(evaluation.project_id);
    setActiveStudyId(evaluation.project_id, evaluation.study_id);
    handleClose();
    navigate('/colmena/telemetry');
  };

  const checkActivation = async (studyId) => {
    setCheckingStudyId(studyId);
    setActivationError('');
    try {
      const access = await getEvaluationAccess(studyId);
      setAccessOverrides((current) => ({ ...current, [studyId]: access }));
    } catch (error) {
      setActivationError(error.message || 'No se pudo consultar el pago.');
    } finally {
      setCheckingStudyId(null);
    }
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
          <p className="rounded-lg bg-[#EDF9FB] px-3 py-2 text-xs font-semibold text-[#075A70]">
            {trialRemaining == null ? 'La disponibilidad gratuita se verificará al registrar la evaluación.' :
              `${trialRemaining} de 4 evaluaciones gratuitas restantes en esta cuenta. Cada una incluye un informe completo.`}
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="colmena-label block">Razón social
              <input className="colmena-input mt-1 block w-full" name="company_name" required value={form.company_name} onChange={handleChange} />
            </label>
            <label className="colmena-label block">RUC
              <input className="colmena-input mt-1 block w-full" name="company_ruc" required inputMode="numeric" pattern="[0-9]{11}" maxLength={11} readOnly={Boolean(companyProfile)} value={form.company_ruc} onChange={handleChange} />
            </label>
            <label className="colmena-label block">Sector
              <select className="colmena-input mt-1 block w-full" name="company_sector" value={form.company_sector} onChange={handleChange}>
                <option value="SERVICES">Servicios y comercio</option>
                <option value="MINING">Minería e hidrocarburos</option>
                <option value="INDUSTRIAL">Industria y manufactura</option>
                <option value="CONSTRUCTION">Construcción y energía</option>
                <option value="HEALTH">Salud</option>
              </select>
            </label>
            <label className="colmena-label block">Cantidad de trabajadores
              <input className="colmena-input mt-1 block w-full" name="population_invited" type="number" min="1" max="10000000" required value={form.population_invited} onChange={handleChange} />
            </label>
          </div>
          <div className="rounded-xl border border-border bg-surfaceSoft p-3">
            <strong className="text-xs text-dark">Instrumentos seleccionados</strong>
            <ul className="mt-1.5 space-y-1 text-xs text-muted">
              {selected.map((instrument, index) => {
                const tariff = priceFor(tariffs, instrument.version_kind, Number(form.population_invited));
                const isPaid = trialRemaining != null && index >= trialRemaining;
                return <li key={instrument.instrument_version_id}>• {instrument.title} · {isPaid
                  ? tariff?.pricing_mode === 'FIXED' ? `S/ ${Number(tariff.price).toFixed(2)}` : 'Cotizar'
                  : 'uso gratuito'}</li>;
              })}
            </ul>
            <p className="mt-1.5 text-[11px] text-muted">Los precios posteriores al cuarto uso incluyen el descuento web del 20 % y dependen de la cantidad de trabajadores declarada.</p>
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
            <strong>{createEvaluations.data.every(({ evaluation }) => evaluation?.survey_url) ? 'Enlaces listos para compartir' : 'Estado de tus evaluaciones'}</strong>
          </div>
          <p className="text-xs text-muted">Los enlaces gratuitos están listos. Las evaluaciones adicionales se habilitan tras verificar el pago.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {createEvaluations.data.map(({ instrument, evaluation, error }) => {
              if (error) return <article key={instrument.instrument_version_id} className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700"><strong>{instrument.title}</strong><p className="mt-1">{error}</p></article>;
              const access = accessOverrides[evaluation.study_id];
              const surveyPath = access?.survey_url || evaluation.survey_url;
              const url = surveyPath ? publicUrl(surveyPath) : null;
              const quotedAmount = access?.amount ?? evaluation.amount;
              return (
                <article key={evaluation.study_id} className="rounded-xl border border-border bg-white p-3">
                  <strong className="block text-xs text-dark">{instrument.title}</strong>
                  {url ? <>
                    <div className="mx-auto my-3 w-fit rounded-lg border border-border bg-white p-2"><QRCodeSVG value={url} size={126} marginSize={1} /></div>
                    <a className="block break-all text-[11px] text-blue-700 underline" href={url} target="_blank" rel="noreferrer">{url}</a>
                    <div className="mt-2 flex gap-3">
                      <button type="button" className="inline-flex items-center gap-1 text-xs font-bold text-[#285994]" onClick={async () => {
                        await navigator.clipboard.writeText(url);
                        setCopiedUrl(url);
                      }}><Copy size={12}/>{copiedUrl === url ? 'Copiado' : 'Copiar'}</button>
                      <a className="inline-flex items-center gap-1 text-xs font-bold text-[#285994]" href={url} target="_blank" rel="noreferrer"><ExternalLink size={12}/>Abrir</a>
                    </div>
                    <button type="button" onClick={() => openTracking(evaluation)} className="mt-3 w-full rounded-lg bg-[#0A1F44] px-3 py-2 text-xs font-bold text-white">Ver respuestas →</button>
                  </> : <div className="mt-3 space-y-2 rounded-lg bg-[#FFF8E9] p-3 text-xs text-[#674914]">
                    <p className="font-bold">Pendiente de pago · orden #{evaluation.order_id}</p>
                    <p>{quotedAmount == null ? 'Cotización pendiente: no transfieras hasta recibir el importe.' : `Importe: S/ ${Number(quotedAmount).toFixed(2)}`}</p>
                    {paymentInstructions && <>
                      <p>Banco: {paymentInstructions.bank_name}</p><p>Titular: {paymentInstructions.account_holder}</p>
                      <p>Cuenta: {paymentInstructions.account_number}</p><p>CCI: {paymentInstructions.cci}</p>
                      <p className={paymentInstructions.provisional || quotedAmount == null ? 'font-bold text-red-700' : 'font-semibold'}>{quotedAmount == null ? 'Espera a que AURORA confirme el importe antes de cualquier transferencia. ' : ''}{paymentInstructions.notice}</p>
                    </>}
                    <button type="button" onClick={() => checkActivation(evaluation.study_id)} disabled={checkingStudyId === evaluation.study_id}
                      className="rounded-lg border border-[#D9B96B] bg-white px-3 py-1.5 font-bold disabled:opacity-60">{checkingStudyId === evaluation.study_id ? 'Consultando…' : 'Comprobar activación'}</button>
                    {access?.order_status && <p>Estado de la orden: {access.order_status}</p>}
                  </div>}
                </article>
              );
            })}
          </div>
          {activationError && <p role="alert" className="text-xs text-red-700">{activationError}</p>}
          <div className="flex justify-end"><Button size="sm" onClick={handleClose}>Cerrar</Button></div>
        </div>
      )}
    </Modal>
  );
}
