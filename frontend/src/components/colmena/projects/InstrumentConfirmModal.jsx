import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import QRCode from 'qrcode';
import {
  ArrowRight,
  CheckCircle2,
  Copy,
  Crown,
  ExternalLink,
  Gift,
  LockKeyhole,
  QrCode,
  ShieldCheck,
} from 'lucide-react';

import { apiRequest } from '../../../api/client.js';
import { Modal } from '../../ui/Modal.jsx';
import { Button } from '../../ui/Button.jsx';
import FormField from '../../ui/FormField.jsx';

export default function InstrumentConfirmModal({ instrument, isOpen, onClose }) {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [copied, setCopied] = useState(false);
  const [result, setResult] = useState(null);

  const [formData, setFormData] = useState({
    company_name: '',
    company_ruc: '',
    company_sector: 'MINING',
    study_name: instrument ? `Evaluación ${instrument.title} · Aurora 2026` : 'Evaluación Aurora 2026',
    instrument_version: instrument?.version || 'MEDIUM',
    population_invited: instrument?.version === 'SHORT' ? 20 : 250,
  });

  useEffect(() => {
    if (!instrument) return;
    setFormData((prev) => ({
      ...prev,
      study_name: `Evaluación ${instrument.title} · Aurora 2026`,
      instrument_version: instrument.version,
      population_invited: instrument.version === 'SHORT' ? 20 : 250,
    }));
    setStep(1);
    setResult(null);
    setErrorMsg(null);
  }, [instrument]);

  const [errorMsg, setErrorMsg] = useState(null);

  const quickEvalMutation = useMutation({
    mutationFn: (payload) => apiRequest('/quick-eval', { method: 'POST', body: payload }),
    onSuccess: (data) => {
      setResult(data);
      setStep(2);
    },
    onError: (err) => {
      setErrorMsg(err?.message || 'Error al generar el instrumento.');
    },
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!formData.company_name.trim()) {
      setErrorMsg('Ingresa la Razón Social de la empresa.');
      return;
    }
    if (!formData.company_ruc.trim()) {
      setErrorMsg('Ingresa el RUC o ID Tributario.');
      return;
    }
    if (instrument?.version === 'SHORT' && Number(formData.population_invited) > 24) {
      setErrorMsg('Para 25 o más trabajadores selecciona CENSOPAS versión media.');
      return;
    }

    quickEvalMutation.mutate({
      ...formData,
      instrument_version: instrument?.version || 'MEDIUM',
      population_invited: Number(formData.population_invited) || 1,
    });
  };

  const surveyUrl = result ? `${window.location.origin}/encuesta/${result.public_id}` : '';

  const handleCopyLink = () => {
    if (!surveyUrl) return;
    navigator.clipboard.writeText(surveyUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadQr = async () => {
    if (!surveyUrl) return;
    const dataUrl = await QRCode.toDataURL(surveyUrl, {
      width: 720,
      margin: 3,
      color: { dark: '#17162D', light: '#FFFFFF' },
      errorCorrectionLevel: 'H',
    });
    const anchor = document.createElement('a');
    anchor.href = dataUrl;
    anchor.download = `aurora-encuesta-${formData.company_ruc || 'empresa'}.png`;
    anchor.click();
  };

  const handleGoToWorkspace = () => {
    if (result?.project_id) {
      navigate(`/colmena/project/${result.project_id}/link`);
      if (onClose) onClose();
    }
  };

  if (!isOpen || !instrument) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      icon={Gift}
      title="Crear informe gratuito"
      subtitle={`${instrument.title} · acceso completo de evaluación`}
    >
      {step === 1 ? (
        <form onSubmit={handleSubmit} className="space-y-3.5 text-xs">
          <div className="rounded-2xl border border-violet-200/70 bg-gradient-to-br from-violet-50 via-white to-cyan-50 p-4 text-dark shadow-sm">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-extrabold text-violet-700">
                <ShieldCheck size={14} /> {instrument.badge || 'Oficial SUNAFIL'}
              </span>
              <span className="rounded-full border border-white bg-white/80 px-2 py-1 text-[10px] font-bold text-muted shadow-sm">
                {instrument.items} ítems · ~{instrument.duration}
              </span>
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-muted">{instrument.description}</p>
            <div className="mt-3 grid gap-2 border-t border-violet-100 pt-3 sm:grid-cols-3">
              {[
                ['Informe', 'PDF / Word'],
                ['Analítica', 'Premium'],
                ['Costo inicial', 'S/ 0'],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl bg-white/70 px-3 py-2">
                  <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">{label}</p>
                  <p className="mt-0.5 text-[11px] font-extrabold text-slate-900">{value}</p>
                </div>
              ))}
            </div>
          </div>

          {errorMsg ? (
            <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700">
              <p className="font-bold">No pudimos crear esta evaluación</p>
              <p className="mt-1 leading-5">{errorMsg}</p>
              {quickEvalMutation.error?.errorCode === 'CONFLICT' ? (
                <p className="mt-2 rounded-lg bg-white/70 px-2.5 py-2 text-[10px] font-semibold text-slate-600">
                  El beneficio aplica una vez por RUC. El proyecto existente permanece disponible desde el panel.
                </p>
              ) : null}
            </div>
          ) : null}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FormField label="Razón Social / Empresa *" id="company_name">
              <input
                id="company_name"
                name="company_name"
                type="text"
                placeholder="ej. Compañía Minera Yauricocha S.A.C."
                value={formData.company_name}
                onChange={handleChange}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-dark placeholder:text-muted focus:border-amber outline-none"
                required
              />
            </FormField>

            <FormField label="RUC / ID Tributario *" id="company_ruc">
              <input
                id="company_ruc"
                name="company_ruc"
                type="text"
                placeholder="ej. 20123456789"
                value={formData.company_ruc}
                onChange={handleChange}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-dark placeholder:text-muted focus:border-amber outline-none"
                required
              />
            </FormField>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FormField label="Sector Económico" id="company_sector">
              <select
                id="company_sector"
                name="company_sector"
                value={formData.company_sector}
                onChange={handleChange}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-dark focus:border-amber outline-none"
              >
                <option value="MINING">Minería e Hidrocarburos</option>
                <option value="INDUSTRIAL">Industria y Manufactura</option>
                <option value="CONSTRUCTION">Construcción y Energía</option>
                <option value="HEALTH">Salud y Servicios Médicos</option>
                <option value="SERVICES">Servicios y Comercio</option>
              </select>
            </FormField>

            <FormField label="Población Trabajadores" id="population_invited">
              <input
                id="population_invited"
                name="population_invited"
                type="number"
                min="1"
                max="10000"
                value={formData.population_invited}
                onChange={handleChange}
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-dark focus:border-amber outline-none"
              />
            </FormField>
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-border">
            <Button type="button" variant="secondary" size="sm" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" size="sm" disabled={quickEvalMutation.isPending} className="font-bold">
              {quickEvalMutation.isPending ? 'Configurando Aurora...' : 'Crear evaluación gratuita'}
            </Button>
          </div>
        </form>
      ) : (
        <div className="space-y-4 py-1 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600">
            <CheckCircle2 size={28} />
          </div>

          <div>
            <h3 className="text-lg font-black tracking-tight text-dark">Aurora está lista para tu empresa</h3>
            <p className="text-xs text-muted mt-0.5">
              <strong className="text-dark">{formData.company_name}</strong> ya puede compartir el enlace anónimo con sus trabajadores.
            </p>
            <div className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-violet-200 bg-violet-50 px-3 py-1.5 text-[10px] font-extrabold text-violet-700">
              <Crown size={12} /> Informe gratuito · Analítica premium habilitada
            </div>
          </div>

          {/* Enlace & QR Selection Box */}
          <div className="rounded-xl border border-border bg-surfaceSoft p-4 text-left space-y-3">
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-muted block mb-1">
                1. Enlace Público Directo
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={surveyUrl}
                  className="flex-1 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-mono text-dark select-all outline-none"
                />
                <button
                  type="button"
                  onClick={handleCopyLink}
                  className="px-3 py-1.5 rounded-lg bg-amber hover:bg-amber-600 text-dark font-bold text-xs transition shrink-0"
                >
                  <Copy size={13} className="inline mr-1" />
                  {copied ? '¡Copiado!' : 'Copiar'}
                </button>
              </div>
            </div>

            <div className="pt-2 border-t border-border/80 flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-dark flex items-center gap-1">
                  <QrCode size={14} className="text-amber" /> 2. Código QR para Afiches
                </span>
                <span className="text-[11px] text-muted block">Escaneo directo desde celular</span>
              </div>
              <button
                type="button"
                onClick={handleDownloadQr}
                className="px-3 py-1.5 rounded-lg border border-border bg-surface hover:bg-surfaceSoft text-dark text-xs font-semibold transition"
              >
                Descargar QR
              </button>
            </div>
          </div>

          <div className="flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-left text-[10px] leading-4 text-emerald-800">
            <LockKeyhole size={14} className="mt-0.5 shrink-0" />
            <p><strong>Protección activa:</strong> Aurora procesa resultados agregados y evita exponer identidades individuales en la experiencia de empresa.</p>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-2">
            <a
              href={surveyUrl}
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl border border-border bg-surface hover:bg-surfaceSoft text-dark text-xs font-semibold transition"
            >
              <ExternalLink size={14} />
              Probar Demo
            </a>
            <Button onClick={handleGoToWorkspace} size="sm" className="flex items-center justify-center gap-1.5 font-bold">
              Ver enlace y QR
              <ArrowRight size={14} />
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
