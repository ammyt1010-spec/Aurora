import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { CheckCircle2, Copy, ExternalLink, Sparkles, Users, Building2, FileText, ArrowRight } from 'lucide-react';

import { apiRequest } from '../../../api/client.js';
import { Modal } from '../../ui/Modal.jsx';
import { Button } from '../../ui/Button.jsx';
import FormField from '../../ui/FormField.jsx';

export default function QuickEvalModal({ isOpen = true, onClose, onCreated }) {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [copied, setCopied] = useState(false);
  const [result, setResult] = useState(null);

  const [formData, setFormData] = useState({
    company_name: '',
    company_ruc: '',
    company_sector: 'MINING',
    study_name: 'Evaluación Psicosocial 2026',
    instrument_version: 'MEDIUM',
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
      setErrorMsg(err?.message || 'Error al generar la evaluación rápida.');
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
      setErrorMsg('El nombre de la empresa es obligatorio.');
      return;
    }
    if (!formData.company_ruc.trim()) {
      setErrorMsg('El RUC / ID Tributario es obligatorio.');
      return;
    }
    quickEvalMutation.mutate({
      ...formData,
      population_invited: Number(formData.population_invited) || 1,
    });
  };

  const fullSurveyUrl = result ? `${window.location.origin}/encuesta/${result.public_id}` : '';

  const handleCopyLink = () => {
    if (!fullSurveyUrl) return;
    navigator.clipboard.writeText(fullSurveyUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleGoToDashboard = () => {
    if (result?.project_id) {
      navigate(`/colmena/project/${result.project_id}`);
      if (onClose) onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="⚡ Nueva Evaluación Rápida — AURORA PRO">
      {step === 1 ? (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="rounded-xl bg-amber-500/10 border border-amber-500/20 p-3 text-xs text-amber-800 dark:text-amber-300">
            <p className="font-semibold flex items-center gap-1.5">
              <Sparkles size={14} /> Emisión Instantánea
            </p>
            <p className="mt-0.5 opacity-90">
              Crea la empresa, carga el instrumento CENSOPAS y genera el enlace público en un solo clic.
            </p>
          </div>

          {errorMsg ? (
            <div className="rounded-lg bg-red-500/10 border border-red-500/30 p-2.5 text-xs text-red-600 dark:text-red-400">
              {errorMsg}
            </div>
          ) : null}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FormField label="Razón Social / Empresa *" id="company_name">
              <input
                id="company_name"
                name="company_name"
                type="text"
                placeholder="ej. Compañía Minera Aurora S.A.C."
                value={formData.company_name}
                onChange={handleChange}
                className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-dark placeholder:text-muted focus:border-amber focus:ring-1 focus:ring-amber outline-none transition"
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
                className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-dark placeholder:text-muted focus:border-amber focus:ring-1 focus:ring-amber outline-none transition"
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
                className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-dark focus:border-amber focus:ring-1 focus:ring-amber outline-none transition"
              >
                <option value="MINING">Minería e Hidrocarburos</option>
                <option value="INDUSTRIAL">Industria y Manufactura</option>
                <option value="CONSTRUCTION">Construcción y Energía</option>
                <option value="HEALTH">Salud y Servicios Médicos</option>
                <option value="SERVICES">Servicios y Comercio</option>
                <option value="OTHER">Otro Sector</option>
              </select>
            </FormField>

            <FormField label="Nombre del Estudio *" id="study_name">
              <input
                id="study_name"
                name="study_name"
                type="text"
                value={formData.study_name}
                onChange={handleChange}
                className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-dark placeholder:text-muted focus:border-amber focus:ring-1 focus:ring-amber outline-none transition"
                required
              />
            </FormField>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-dark block">
              Instrumento Oficial CENSOPAS-COPSOQ *
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setFormData((p) => ({ ...p, instrument_version: 'SHORT' }))}
                className={`p-3 text-left rounded-xl border transition ${
                  formData.instrument_version === 'SHORT'
                    ? 'border-amber bg-amber-500/10 text-dark font-medium shadow-sm ring-1 ring-amber/30'
                    : 'border-border bg-surface hover:bg-surfaceSoft text-muted'
                }`}
              >
                <p className="text-sm font-bold text-dark flex items-center justify-between">
                  <span>Corte Corta</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber/20 text-amber font-semibold">42 ítems</span>
                </p>
                <p className="text-xs mt-1 leading-tight text-muted">
                  Recomendado para PYMEs y organizaciones con menos de 25 trabajadores.
                </p>
              </button>

              <button
                type="button"
                onClick={() => setFormData((p) => ({ ...p, instrument_version: 'MEDIUM' }))}
                className={`p-3 text-left rounded-xl border transition ${
                  formData.instrument_version === 'MEDIUM'
                    ? 'border-amber bg-amber-500/10 text-dark font-medium shadow-sm ring-1 ring-amber/30'
                    : 'border-border bg-surface hover:bg-surfaceSoft text-muted'
                }`}
              >
                <p className="text-sm font-bold text-dark flex items-center justify-between">
                  <span>Versión Media</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-turquoise/20 text-turquoise font-semibold">112 ítems</span>
                </p>
                <p className="text-xs mt-1 leading-tight text-muted">
                  Estándar minero e industrial. Evaluación exhaustiva por 20 subdimensiones.
                </p>
              </button>
            </div>
          </div>

          <FormField label="Población Invitada (Nro. de Trabajadores)" id="population_invited">
            <input
              id="population_invited"
              name="population_invited"
              type="number"
              min="1"
              max="10000"
              value={formData.population_invited}
              onChange={handleChange}
              className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-dark focus:border-amber focus:ring-1 focus:ring-amber outline-none transition"
            />
          </FormField>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" disabled={quickEvalMutation.isPending}>
              {quickEvalMutation.isPending ? 'Creando...' : '⚡ Generar Evaluación Ahora'}
            </Button>
          </div>
        </form>
      ) : (
        <div className="space-y-5 text-center py-2">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-500">
            <CheckCircle2 size={32} />
          </div>

          <div>
            <h3 className="text-lg font-bold text-dark">¡Evaluación Creada Exitosamente!</h3>
            <p className="text-xs text-muted mt-1">
              Se ha configurado la empresa <strong className="text-dark">{formData.company_name}</strong> y generado el enlace público oficial.
            </p>
          </div>

          <div className="rounded-xl border border-border bg-surfaceSoft p-3.5 text-left space-y-2">
            <label className="text-xs font-semibold text-muted uppercase tracking-wider block">
              Enlace Público para Trabajadores
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={fullSurveyUrl}
                className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-mono text-dark outline-none select-all"
              />
              <button
                type="button"
                onClick={handleCopyLink}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-amber hover:bg-amber-600 text-dark font-semibold text-xs transition"
              >
                <Copy size={13} />
                {copied ? '¡Copiado!' : 'Copiar'}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-2">
            <a
              href={fullSurveyUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-border bg-surface hover:bg-surfaceSoft text-dark text-xs font-semibold transition"
            >
              <ExternalLink size={14} />
              Probar Encuesta Demo
            </a>
            <Button onClick={handleGoToDashboard} className="flex items-center justify-center gap-2">
              Ir al Dashboard
              <ArrowRight size={14} />
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
