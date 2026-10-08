import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Check,
  Copy,
  ExternalLink,
  QrCode,
  Send,
  ShieldCheck,
  Users,
  Building2,
  Lock,
  Sparkles,
  RefreshCcw,
} from 'lucide-react';

import { useActiveProject } from '../../../hooks/useActiveProject.js';
import { getProject } from '../../../api/projects.js';
import { listStudies, openStudy, closeStudy } from '../../../api/studies.js';

import ProjectWorkspaceHeader from '../../../components/colmena/project/ProjectWorkspaceHeader.jsx';
import { Card } from '../../../components/ui/Card.jsx';
import { Button } from '../../../components/ui/Button.jsx';
import { LoadingState } from '../../../components/ui/LoadingState.jsx';
import { ProjectMissingState } from '../../../components/colmena/ProjectMissingState.jsx';

export default function ProjectLinkPage() {
  const { projectId } = useParams();
  const queryClient = useQueryClient();
  const [copied, setCopied] = useState(false);
  const [accessCode, setAccessCode] = useState(() => localStorage.getItem(`access_code_${projectId}`) || '');
  const [savedCodeMsg, setSavedCodeMsg] = useState(false);
  useActiveProject(projectId);

  const { data: project, isLoading: isLoadingProject } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });

  const { data: studiesData, isLoading: isLoadingStudies } = useQuery({
    queryKey: ['studies', projectId],
    queryFn: () => listStudies(projectId, { page: 1, pageSize: 20 }),
    enabled: Boolean(projectId),
  });

  const studies = studiesData?.items ?? [];
  const activeStudy = studies.find((s) => s.status === 'OPEN') || studies[0];
  const publicId = activeStudy?.public_id || project?.censopas_study?.public_id;
  const surveyUrl = publicId ? `${window.location.origin}/encuesta/${publicId}` : null;

  const handleCopyLink = () => {
    if (!surveyUrl) return;
    navigator.clipboard.writeText(surveyUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleSaveAccessCode = () => {
    localStorage.setItem(`access_code_${projectId}`, accessCode);
    setSavedCodeMsg(true);
    setTimeout(() => setSavedCodeMsg(false), 2500);
  };

  if (isLoadingProject || isLoadingStudies) return <LoadingState label="Cargando enlace de evaluación..." />;
  if (!project) return <ProjectMissingState />;

  return (
    <div className="colmena-page space-y-6">
      <ProjectWorkspaceHeader activeTab="link" />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Survey Link Box */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="p-6 space-y-5 border-amber/30 bg-surface shadow-sm">
            <div className="flex items-center justify-between border-b border-border/80 pb-4">
              <div>
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-600 text-xs font-bold uppercase tracking-wider">
                  <ShieldCheck size={14} /> Encuesta Pública Habilitada
                </span>
                <h2 className="text-xl font-bold text-dark mt-2">Enlace Oficial de Respuesta</h2>
                <p className="text-xs text-muted mt-0.5">
                  Comparte este enlace con los trabajadores de la empresa para la recolección confidencial de respuestas.
                </p>
              </div>
            </div>

            {surveyUrl ? (
              <div className="space-y-4">
                <div className="rounded-xl border border-border bg-surfaceSoft p-4 space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider text-muted block">
                    URL de Aplicación Directa
                  </label>
                  <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                    <input
                      type="text"
                      readOnly
                      value={surveyUrl}
                      className="flex-1 rounded-xl border border-border bg-surface px-4 py-2.5 text-xs font-mono text-dark select-all outline-none"
                    />
                    <button
                      type="button"
                      onClick={handleCopyLink}
                      className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-amber hover:bg-amber-600 text-dark font-bold text-xs shadow-sm transition"
                    >
                      <Copy size={14} />
                      {copied ? '¡Copiado!' : 'Copiar Enlace'}
                    </button>
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                  <a
                    href={surveyUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-border bg-surface hover:bg-surfaceSoft text-dark font-semibold text-xs transition"
                  >
                    <ExternalLink size={14} />
                    Abrir Formulario en Nueva Ventana
                  </a>

                  <span className="text-xs text-muted flex items-center gap-1">
                    <Users size={14} className="text-amber" />
                    Respuestas Anónimas Protegidas por CENSOPAS
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted">No se ha generado un enlace público aún.</p>
            )}
          </Card>

          {/* Worker Authentication / Company Access Code */}
          <Card className="p-6 space-y-4">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber/10 text-amber">
                <Lock size={20} />
              </div>
              <div>
                <h3 className="text-base font-bold text-dark">Validación de Trabajadores y Acceso Restringido</h3>
                <p className="text-xs text-muted mt-0.5">
                  Establece un código de verificación empresarial (opcional) para asegurar que solo personal autorizado conteste la encuesta.
                </p>
              </div>
            </div>

            <div className="pt-2 grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="sm:col-span-2">
                <input
                  type="text"
                  placeholder="ej. MINERA-AURORA-2026"
                  value={accessCode}
                  onChange={(e) => setAccessCode(e.target.value)}
                  className="w-full rounded-xl border border-border bg-surface px-4 py-2.5 text-xs text-dark placeholder:text-muted focus:border-amber outline-none transition"
                />
              </div>
              <button
                type="button"
                onClick={handleSaveAccessCode}
                className="px-4 py-2.5 rounded-xl border border-border bg-surfaceSoft hover:bg-surface text-dark font-bold text-xs transition"
              >
                {savedCodeMsg ? '¡Guardado!' : 'Guardar Código'}
              </button>
            </div>
          </Card>
        </div>

        {/* QR Code & Information Sidebar */}
        <div className="space-y-6">
          <Card className="p-6 text-center space-y-4">
            <div className="inline-flex items-center gap-1.5 text-xs font-bold text-dark">
              <QrCode size={16} className="text-amber" /> Código QR de Aplicación
            </div>

            {surveyUrl ? (
              <div className="mx-auto flex h-48 w-48 items-center justify-center rounded-2xl border-2 border-border bg-white p-3 shadow-inner">
                {/* Clean QR code rendering using Google Charts QR API */}
                <img
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(surveyUrl)}`}
                  alt="Código QR de la Encuesta"
                  className="h-full w-full object-contain"
                />
              </div>
            ) : null}

            <p className="text-[11px] text-muted leading-tight">
              Imprime este código QR para colocarlo en afiches, áreas comunes o enviar por WhatsApp corporativo.
            </p>

            {surveyUrl ? (
              <a
                href={`https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=${encodeURIComponent(surveyUrl)}`}
                target="_blank"
                download="qr_encuesta_aurora.png"
                rel="noreferrer"
                className="inline-block w-full py-2.5 rounded-xl border border-border bg-surfaceSoft hover:bg-surface text-dark text-xs font-bold transition"
              >
                Descargar QR Alta Resolución
              </a>
            ) : null}
          </Card>
        </div>
      </div>
    </div>
  );
}
