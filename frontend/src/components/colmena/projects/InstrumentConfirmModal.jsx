import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Copy,
  ExternalLink,
  QrCode,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react';

import { apiRequest } from '../../../api/client.js';
import { Modal } from '../../ui/Modal.jsx';
import { Button } from '../../ui/Button.jsx';
import FormField from '../../ui/FormField.jsx';

export default function InstrumentConfirmModal({ instrument, isOpen, onClose, onCreated }) {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [copied, setCopied] = useState(false);
  const [result, setResult] = useState(null);

  const [formData, setFormData] = useState({
    company_name: '',
    company_ruc: '',
    company_sector: 'MINING',
    study_name: instrument ? `Evaluación ${instrument.title} 2026` : 'Evaluación 2026',
    instrument_version: instrument?.version || 'MEDIUM',
    population_invited: 50,
  });

  const [errorMsg, setErrorMsg] = useState(null);

  const quickEvalMutation = useMutation({
    mutationFn: (payload) => apiRequest('/quick-eval', { method: 'POST', body: payload }),
    onSuccess: (data) => {
      setResult(data);
      setStep(2);
      if (onCreated) onCreated(data);
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

  const handleGoToTelemetry = () => {
    if (result?.project_id) {
      navigate(`/colmena/project/${result.project_id}/telemetry`);
      if (onClose) onClose();
    }
  };

  if (!isOpen || !instrument) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`⚡ Confirmar Instrumento — ${instrument.title}`}>
      {step === 1 ? (
        <form onSubmit={handleSubmit} className="space-y-3.5 text-xs">
          <div className="rounded-xl bg-amber-500/10 border border-amber-500/20 p-3 text-dark space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-amber text-xs flex items-center gap-1.5">
                <ShieldCheck size={14} /> {instrument.badge || 'Oficial SUNAFIL'}
              </span>
              <span className="text-[10px] font-semibold text-muted bg-surface px-2 py-0.5 rounded-full border border-border">
                {instrument.items} ítems · ~{instrument.duration}
              </span>
            </div>
            <p className="text-[11px] text-muted leading-relaxed">{instrument.description}</p>
          </div>

          {errorMsg ? (
            <div className="rounded-lg bg-red-500/10 border border-red-500/30 p-2.5 text-xs text-red-600">
              {errorMsg}
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
              {quickEvalMutation.isPending ? 'Procesando...' : '⚡ Confirmar y Generar Enlace / QR'}
            </Button>
          </div>
        </form>
      ) : (
        <div className="space-y-4 py-1 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600">
            <CheckCircle2 size={28} />
          </div>

          <div>
            <h3 className="text-base font-bold text-dark">¡Instrumento Configurado!</h3>
            <p className="text-xs text-muted mt-0.5">
              Empresa: <strong className="text-dark">{formData.company_name}</strong> · Enlace público listo para ser compartido.
            </p>
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
              <a
                href={`https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=${encodeURIComponent(surveyUrl)}`}
                target="_blank"
                download="qr_encuesta.png"
                rel="noreferrer"
                className="px-3 py-1.5 rounded-lg border border-border bg-surface hover:bg-surfaceSoft text-dark text-xs font-semibold transition"
              >
                Descargar QR
              </a>
            </div>
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
            <Button onClick={handleGoToTelemetry} size="sm" className="flex items-center justify-center gap-1.5 font-bold">
              Ir a Telemetría en Vivo
              <ArrowRight size={14} />
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
