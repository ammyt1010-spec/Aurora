import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import QRCode from 'qrcode';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Copy,
  ExternalLink,
  QrCode,
  ShieldCheck,
  Users,
  FlaskConical,
} from 'lucide-react';

import { useActiveProject } from '../../../hooks/useActiveProject.js';
import { getProject } from '../../../api/projects.js';
import { listStudies } from '../../../api/studies.js';
import { getDemoPopulationStatus, startDemoPopulation } from '../../../api/demoPopulation.js';

import ProjectWorkspaceHeader from '../../../components/colmena/project/ProjectWorkspaceHeader.jsx';
import { Card } from '../../../components/ui/Card.jsx';
import { Button } from '../../../components/ui/Button.jsx';
import { LoadingState } from '../../../components/ui/LoadingState.jsx';
import { ProjectMissingState } from '../../../components/colmena/ProjectMissingState.jsx';

export default function ProjectLinkPage() {
  const { projectId } = useParams();
  const [copied, setCopied] = useState(false);
  const [qrDataUrl, setQrDataUrl] = useState(null);
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
  useEffect(() => {
    let active = true;
    if (!surveyUrl) return undefined;
    QRCode.toDataURL(surveyUrl, { width: 720, margin: 3, errorCorrectionLevel: 'H' })
      .then((url) => { if (active) setQrDataUrl(url); })
      .catch(() => { if (active) setQrDataUrl(null); });
    return () => { active = false; };
  }, [surveyUrl]);
  const isFreeDemo = project?.metadata?.commercial_tier === 'FREE_REPORT';
  const demoQuery = useQuery({
    queryKey: ['demoPopulation', activeStudy?.id],
    queryFn: () => getDemoPopulationStatus(activeStudy.id),
    enabled: isFreeDemo && Boolean(activeStudy?.id),
    refetchInterval: (query) => query.state.data?.status === 'RUNNING' ? 3000 : false,
  });
  const demoMutation = useMutation({
    mutationFn: () => startDemoPopulation(activeStudy.id),
    onSuccess: () => demoQuery.refetch(),
  });

  const handleCopyLink = () => {
    if (!surveyUrl) return;
    navigator.clipboard.writeText(surveyUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
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

          {isFreeDemo && demoQuery.data?.status !== 'HAS_RESPONSES' ? (
            <Card className="space-y-3 border-violet-200 bg-gradient-to-br from-violet-50 to-cyan-50 p-5">
              <div className="flex items-start gap-3">
                <FlaskConical size={20} className="mt-0.5 shrink-0 text-violet-600" />
                <div>
                  <h3 className="text-sm font-bold text-dark">Probar todo Aurora con datos de ejemplo</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">
                    Genera hasta {demoStatus?.target || 250} respuestas anónimas sintéticas, calcula los niveles de riesgo y activa telemetría, dashboard e informe. Úsalo solo para esta prueba; una evaluación real debe iniciar con respuestas de trabajadores.
                  </p>
                </div>
              </div>
              {demoQuery.data?.status === 'AVAILABLE' || demoQuery.data?.status === 'FAILED' ? (
                <Button disabled={demoMutation.isPending} onClick={() => demoMutation.mutate()} size="sm">
                  {demoMutation.isPending ? 'Preparando muestra…' : `Cargar muestra sintética de ${demoStatus?.target || 250} trabajadores`}
                </Button>
              ) : null}
              {demoQuery.data?.status === 'RUNNING' ? (
                <p className="text-xs font-semibold text-violet-700">Generando respuestas y análisis. Esta sección se actualizará automáticamente.</p>
              ) : null}
              {demoQuery.data?.status === 'COMPLETED' ? (
                <div className="flex flex-wrap items-center gap-3 text-xs font-semibold text-emerald-700">
                  <span>{demoStatus?.target || 250} respuestas sintéticas listas</span>
                  <Link to={`/colmena/project/${projectId}/telemetry`} className="underline">Ver telemetría →</Link>
                  <Link to={`/colmena/project/${projectId}/premium`} className="underline">Ver dashboard →</Link>
                </div>
              ) : null}
              {demoQuery.data?.status === 'FAILED' || demoMutation.isError ? (
                <p className="text-xs text-red-700">{demoQuery.data?.error || demoMutation.error?.message || 'No se pudo preparar la muestra.'}</p>
              ) : null}
            </Card>
          ) : null}

          <Card className="p-5 text-xs leading-5 text-muted">
            El enlace permite responder sin cuenta ni nombre. Compártelo únicamente con la población convocada; Aurora presenta resultados agregados y protege los grupos pequeños.
          </Card>
        </div>

        {/* QR Code & Information Sidebar */}
        <div className="space-y-6">
          <Card className="p-6 text-center space-y-4">
            <div className="inline-flex items-center gap-1.5 text-xs font-bold text-dark">
              <QrCode size={16} className="text-amber" /> Código QR de Aplicación
            </div>

            {qrDataUrl ? (
              <div className="mx-auto flex h-48 w-48 items-center justify-center rounded-2xl border-2 border-border bg-white p-3 shadow-inner">
                <img
                  src={qrDataUrl}
                  alt="Código QR de la Encuesta"
                  className="h-full w-full object-contain"
                />
              </div>
            ) : null}

            <p className="text-[11px] text-muted leading-tight">
              Imprime este código QR para colocarlo en afiches, áreas comunes o enviar por WhatsApp corporativo.
            </p>

            {qrDataUrl ? (
              <a
                href={qrDataUrl}
                download="qr_encuesta_aurora.png"
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
