import { useRef, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
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
import { apiRequest } from '../../../api/client.js';
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
  const qrContainerRef = useRef(null);
  const [invitationCount, setInvitationCount] = useState(10);
  const [issuedTokens, setIssuedTokens] = useState([]);
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

  const downloadSurveyQr = () => {
    const svg = qrContainerRef.current?.querySelector('svg');
    if (!svg) return;
    const serialized = new XMLSerializer().serializeToString(svg);
    const blob = new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' });
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = 'aurora-encuesta-qr.svg';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 5000);
  };

  const handleCopyLink = () => {
    if (!surveyUrl) return;
    navigator.clipboard.writeText(surveyUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const issueInvitations = useMutation({
    mutationFn: async () => apiRequest(`/studies/${activeStudy.id}/invitations`, {
      method: 'POST',
      body: { count: Number(invitationCount) },
    }),
    onSuccess: (data) => setIssuedTokens(data.tokens || []),
  });

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

          {/* Real, server-validated invitation codes (no localStorage security theater). */}
          <Card className="p-6 space-y-4">
            <div className="flex items-start gap-3">
              <Lock size={20} className="text-amber" />
              <div>
                <h3 className="text-base font-bold text-dark">Acceso de trabajadores</h3>
                <p className="text-xs text-muted mt-1">
                  {activeStudy?.requires_invitation
                    ? 'Este estudio exige códigos personales de un solo uso, validados en el servidor.'
                    : 'El estudio acepta respuestas con su enlace público. Para restringirlo, activa «Requiere invitación» antes de abrir el estudio.'}
                </p>
              </div>
            </div>
            {activeStudy?.requires_invitation ? (
              <>
                <label className="text-xs font-semibold" htmlFor="invitation-count">Cantidad de códigos</label>
                <input
                  id="invitation-count"
                  type="number" min="1" max="1000"
                  value={invitationCount}
                  onChange={(event) => setInvitationCount(event.target.value)}
                  className="colmena-input w-36"
                />
                <button type="button" onClick={() => issueInvitations.mutate()}
                  disabled={issueInvitations.isPending || Number(invitationCount) < 1 || Number(invitationCount) > 1000}
                  className="px-4 py-2 rounded-lg bg-amber text-dark font-bold text-xs">
                  {issueInvitations.isPending ? 'Generando…' : 'Emitir invitaciones'}
                </button>
                {issueInvitations.isError && (
                  <p role="alert" className="text-xs text-danger">{issueInvitations.error?.message}</p>
                )}
                {issuedTokens.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs text-muted">Copia los códigos ahora: por seguridad no podrán recuperarse de la API después.</p>
                    <textarea readOnly className="colmena-input w-full font-mono text-xs" rows="5" value={issuedTokens.join('\n')} />
                    <button type="button" className="text-xs font-semibold underline" onClick={() => navigator.clipboard.writeText(issuedTokens.join('\n'))}>
                      Copiar todos los códigos
                    </button>
                  </div>
                )}
              </>
            ) : null}
          </Card>
        </div>

        {/* QR Code & Information Sidebar */}
        <div className="space-y-6">
          <Card className="p-6 text-center space-y-4">
            <div className="inline-flex items-center gap-1.5 text-xs font-bold text-dark">
              <QrCode size={16} className="text-amber" /> Código QR de Aplicación
            </div>

            {surveyUrl ? (
              <div ref={qrContainerRef} className="mx-auto flex h-48 w-48 items-center justify-center rounded-2xl border-2 border-border bg-white p-3 shadow-inner">
                <QRCodeSVG value={surveyUrl} size={168} level="M" marginSize={1} title="Código QR de la encuesta" />
              </div>
            ) : null}

            <p className="text-[11px] text-muted leading-tight">
              Imprime este código QR para colocarlo en afiches, áreas comunes o enviar por WhatsApp corporativo.
            </p>

            {surveyUrl ? (
              <button
                type="button"
                onClick={downloadSurveyQr}
                className="inline-block w-full py-2.5 rounded-xl border border-border bg-surfaceSoft hover:bg-surface text-dark text-xs font-bold transition"
              >
                Descargar QR vectorial (SVG)
              </button>
            ) : null}
          </Card>
        </div>
      </div>
    </div>
  );
}
