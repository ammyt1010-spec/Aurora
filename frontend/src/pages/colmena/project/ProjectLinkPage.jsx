import { useRef, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { useParams, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Copy,
  ExternalLink,
  QrCode,
  ShieldCheck,
  Users,
  Lock,
  RefreshCcw,
} from 'lucide-react';

import { useActiveProject } from '../../../hooks/useActiveProject.js';
import { apiRequest } from '../../../api/client.js';
import { getProject } from '../../../api/projects.js';
import { listStudies, getStudy, openStudy } from '../../../api/studies.js';
import {
  canDistributeSurvey,
  selectCampaign,
} from '../../../utils/campaignAccess.js';
import {
  createEvaluationBundle,
  listEvaluationBundles,
  revokeEvaluationBundle,
} from '../../../api/evaluationBundles.js';

import ProjectWorkspaceHeader from '../../../components/colmena/project/ProjectWorkspaceHeader.jsx';
import { Card } from '../../../components/ui/Card.jsx';
import { LoadingState } from '../../../components/ui/LoadingState.jsx';
import { ProjectMissingState } from '../../../components/colmena/ProjectMissingState.jsx';

export default function ProjectLinkPage() {
  const { projectId } = useParams();
  const queryClient = useQueryClient();
  const [copied, setCopied] = useState(false);
  const qrContainerRef = useRef(null);
  const [invitationCount, setInvitationCount] = useState(10);
  const [issuedTokens, setIssuedTokens] = useState([]);
  const [searchParams] = useSearchParams();
  const [selectedStudyId, setSelectedStudyId] = useState(
    () => searchParams.get('studyId') || '',
  );
  const [revocationReason, setRevocationReason] = useState('');
  const [bundleSelection, setBundleSelection] = useState([]);
  const [bundleLabel, setBundleLabel] = useState(
    'Batería de evaluación empresarial',
  );
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

  const listedStudies = studiesData?.items ?? [];
  const requestedStudy = useQuery({
    queryKey: ['link-selected-study', projectId, selectedStudyId],
    queryFn: () => getStudy(selectedStudyId),
    enabled:
      Boolean(selectedStudyId) &&
      !listedStudies.some((study) => String(study.id) === selectedStudyId),
    retry: false,
  });
  const studies =
    requestedStudy.data &&
    String(requestedStudy.data.project_id) === String(projectId) &&
    !listedStudies.some((study) => study.id === requestedStudy.data.id)
      ? [requestedStudy.data, ...listedStudies]
      : listedStudies;
  // A deep link must never silently fall back to a different campaign.
  const activeStudy = selectedStudyId
    ? studies.find((study) => String(study.id) === selectedStudyId)
    : selectCampaign(studies, '');
  const publishCampaign = useMutation({
    mutationFn: () => openStudy(activeStudy.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studies', projectId] });
      queryClient.invalidateQueries({
        queryKey: ['link-selected-study', projectId, selectedStudyId],
      });
      queryClient.invalidateQueries({
        queryKey: ['aurora-battery-studies', String(projectId)],
      });
    },
  });
  const canDistribute = canDistributeSurvey(activeStudy);
  const publicId = activeStudy?.public_id;
  const surveyUrl =
    canDistribute && publicId
      ? `${window.location.origin}/encuesta/${publicId}`
      : null;

  const { data: bundles = [], isError: bundleListError } = useQuery({
    queryKey: ['evaluation-bundles', projectId],
    queryFn: () => listEvaluationBundles(projectId),
    enabled: Boolean(projectId),
    retry: false,
  });
  const eligibleForBundle = studies.filter(
    (study) =>
      study.status === 'OPEN' &&
      !study.requires_invitation &&
      canDistributeSurvey(study),
  );
  const createBundle = useMutation({
    mutationFn: () =>
      createEvaluationBundle(projectId, {
        label: bundleLabel.trim(),
        study_ids: bundleSelection,
      }),
    onSuccess: () => {
      setBundleSelection([]);
      queryClient.invalidateQueries({
        queryKey: ['evaluation-bundles', projectId],
      });
    },
  });
  const revokeBundle = useMutation({
    mutationFn: (id) => revokeEvaluationBundle(projectId, id),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ['evaluation-bundles', projectId],
      }),
  });

  const {
    data: invitations = [],
    isLoading: loadingInvitations,
    isError: failedInvitations,
  } = useQuery({
    queryKey: ['study-invitations', activeStudy?.id],
    queryFn: () => apiRequest(`/studies/${activeStudy.id}/invitations/list`),
    enabled: Boolean(activeStudy?.id && activeStudy?.requires_invitation),
  });
  const pendingInvitations = invitations.filter((item) =>
    ['PENDING', 'SENT'].includes(item.status),
  );
  const consumedCount = invitations.filter(
    (item) => item.status === 'CONSUMED',
  ).length;

  const downloadSurveyQr = () => {
    const svg = qrContainerRef.current?.querySelector('svg');
    if (!svg) return;
    const serialized = new XMLSerializer().serializeToString(svg);
    const blob = new Blob([serialized], {
      type: 'image/svg+xml;charset=utf-8',
    });
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
    mutationFn: async () =>
      apiRequest(`/studies/${activeStudy.id}/invitations`, {
        method: 'POST',
        body: { count: Number(invitationCount) },
      }),
    onSuccess: (data) => {
      setIssuedTokens(data.tokens || []);
      queryClient.invalidateQueries({
        queryKey: ['study-invitations', activeStudy.id],
      });
    },
  });

  const revokeInvitation = useMutation({
    mutationFn: (invitationId) =>
      apiRequest(
        `/studies/${activeStudy.id}/invitations/${invitationId}/revoke?reason=${encodeURIComponent(revocationReason.trim() || 'Revocada por el administrador')}`,
        { method: 'POST' },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['study-invitations', activeStudy.id],
      });
    },
  });

  if (isLoadingProject || isLoadingStudies)
    return <LoadingState label="Cargando enlace de evaluación..." />;
  if (!project) return <ProjectMissingState />;

  return (
    <div className="colmena-page space-y-6">
      <ProjectWorkspaceHeader activeTab="link" />

      <Card className="p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-dark">
              Campaña de evaluación
            </h2>
            <p className="text-xs text-muted">
              Selecciona la campaña antes de compartir accesos. Las campañas
              cerradas no admiten nuevas respuestas.
            </p>
          </div>
          <span
            className={`rounded-full px-3 py-1 text-xs font-bold ${canDistribute ? 'bg-emerald-500/10 text-emerald-600' : 'bg-surfaceSoft text-muted'}`}
          >
            {activeStudy?.status || 'SIN CAMPAÑAS'}
            {activeStudy?.status === 'OPEN' && !canDistribute
              ? ' · VENCIDA'
              : ''}
          </span>
        </div>
        {selectedStudyId && !activeStudy && (
          <p role="alert">
            La campaña seleccionada no está disponible en esta empresa.
            Selecciona otra campaña autorizada.
          </p>
        )}
        <label
          htmlFor="campaign-select"
          className="block text-xs font-semibold text-muted"
        >
          Estudio
        </label>
        <select
          id="campaign-select"
          className="colmena-input w-full"
          value={activeStudy?.id || ''}
          onChange={(event) => {
            setSelectedStudyId(event.target.value);
            setIssuedTokens([]);
            setRevocationReason('');
          }}
          disabled={!studies.length || publishCampaign.isPending}
        >
          {!studies.length && <option value="">No existen campañas</option>}
          {studies.map((study) => (
            <option key={study.id} value={study.id}>
              {study.name} · {study.status}
            </option>
          ))}
        </select>
        {activeStudy?.status === 'DRAFT' && (
          <div className="space-y-2">
            <p className="text-xs text-muted">
              Revisa el instrumento y su configuración antes de abrir. Al abrir
              se congela el cuestionario y se habilita la recepción de
              respuestas.
            </p>
            <button
              type="button"
              className="survey-btn survey-btn-primary"
              disabled={publishCampaign.isPending}
              onClick={() => publishCampaign.mutate()}
            >
              {publishCampaign.isPending
                ? 'Abriendo…'
                : 'Abrir campaña seleccionada'}
            </button>
          </div>
        )}
        {publishCampaign.isError && (
          <p role="alert" className="text-red-700">
            {publishCampaign.error.message}
          </p>
        )}
      </Card>

      <Card className="rounded-2xl border border-[#dce5f4] bg-gradient-to-br from-white to-[#f5f8ff] p-4 shadow-lg">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-extrabold text-[#1c3359]">
              Batería de instrumentos
            </h2>
            <p className="mt-1 text-xs text-muted">
              Crea un solo enlace para orientar a los participantes hacia varios
              estudios publicados. Cada cuestionario y resultado conserva su
              propia metodología.
            </p>
          </div>
          <span className="shrink-0 rounded-lg bg-[#e5edff] px-2.5 py-1.5 text-xs font-bold text-[#2b4d8d]">
            {bundleSelection.length} seleccionados
          </span>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto] md:items-end">
          <label className="flex flex-col gap-1 text-xs font-semibold text-dark">
            Nombre del paquete
            <input
              aria-label="Nombre del paquete"
              className="colmena-input w-full"
              maxLength={180}
              value={bundleLabel}
              onChange={(e) => setBundleLabel(e.target.value)}
            />
          </label>
          <fieldset className="min-w-0">
            <legend className="mb-1 text-xs font-semibold text-dark">
              Estudios disponibles
            </legend>
            <div className="flex max-h-28 flex-wrap gap-2 overflow-auto rounded-xl border border-border bg-white p-2">
              {eligibleForBundle.length ? (
                eligibleForBundle.map((study) => (
                  <label
                    key={study.id}
                    className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-[#f0f4fa] px-2.5 py-2 text-xs font-semibold text-dark"
                  >
                    <input
                      type="checkbox"
                      checked={bundleSelection.includes(study.id)}
                      onChange={(event) =>
                        setBundleSelection((prev) =>
                          event.target.checked
                            ? [...prev, study.id]
                            : prev.filter((id) => id !== study.id),
                        )
                      }
                    />
                    {study.name}
                  </label>
                ))
              ) : (
                <span className="text-xs text-muted">
                  Se requieren al menos dos estudios abiertos sin invitación
                  individual.
                </span>
              )}
            </div>
          </fieldset>
          <button
            type="button"
            disabled={
              bundleSelection.length < 2 ||
              bundleLabel.trim().length < 3 ||
              createBundle.isPending
            }
            onClick={() => createBundle.mutate()}
            className="rounded-xl bg-[#234677] px-4 py-3 text-xs font-bold text-white shadow-md hover:bg-[#315f9e] disabled:opacity-40"
          >
            {createBundle.isPending ? 'Generando…' : 'Generar enlace unificado'}
          </button>
        </div>
        {createBundle.isError && (
          <p role="alert" className="mt-3 text-xs font-semibold text-danger">
            {createBundle.error?.message || 'No fue posible crear la batería.'}
          </p>
        )}
        {bundleListError && (
          <p role="alert" className="mt-3 text-xs text-danger">
            No fue posible recuperar el historial de baterías.
          </p>
        )}
        {bundles.filter((bundle) => bundle.status === 'PUBLISHED').length >
          0 && (
          <div className="mt-4 grid gap-2 lg:grid-cols-2">
            {bundles
              .filter((bundle) => bundle.status === 'PUBLISHED')
              .map((bundle) => {
                const url = `${window.location.origin}/bateria/${bundle.public_id}`;
                return (
                  <div
                    key={bundle.id}
                    className="flex min-w-0 items-center gap-3 rounded-xl border border-[#e1e8f4] bg-white p-3"
                  >
                    <QRCodeSVG
                      value={url}
                      size={61}
                      aria-label={'QR de ' + bundle.label}
                    />
                    <div className="min-w-0 flex-1">
                      <strong className="block truncate text-xs text-dark">
                        {bundle.label}
                      </strong>
                      <span className="block text-[11px] text-muted">
                        {bundle.study_ids.length} estudios
                      </span>
                      <div className="mt-1 flex flex-wrap gap-3 text-[11px] font-semibold text-[#375a9c]">
                        <button
                          type="button"
                          onClick={() => navigator.clipboard.writeText(url)}
                        >
                          Copiar enlace
                        </button>
                        <a href={url} target="_blank" rel="noreferrer">
                          Abrir
                        </a>
                        <button
                          type="button"
                          disabled={revokeBundle.isPending}
                          className="text-red-600"
                          onClick={() => {
                            if (
                              window.confirm('¿Revocar este enlace de batería?')
                            )
                              revokeBundle.mutate(bundle.id);
                          }}
                        >
                          Revocar
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
        )}
        <p className="mt-3 text-[11px] text-muted">
          La batería es una entrada conjunta a cuestionarios independientes. No
          crea una sesión única entre instrumentos ni modifica las reglas de
          invitación. Las cotizaciones e informes definitivos siguen asociados a
          cada estudio.
        </p>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Survey Link Box */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="p-6 space-y-5 border-amber/30 bg-surface shadow-sm">
            <div className="flex items-center justify-between border-b border-border/80 pb-4">
              <div>
                <span
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${canDistribute ? 'bg-emerald-500/10 text-emerald-600' : 'bg-surfaceSoft text-muted'}`}
                >
                  <ShieldCheck size={14} />{' '}
                  {canDistribute
                    ? 'Encuesta habilitada'
                    : 'Encuesta no disponible'}
                </span>
                <h2 className="text-xl font-bold text-dark mt-2">
                  Enlace Oficial de Respuesta
                </h2>
                <p className="text-xs text-muted mt-0.5">
                  Comparte este enlace con los trabajadores de la empresa para
                  la recolección confidencial de respuestas.
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
                    Respuestas confidenciales según política del estudio
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted">
                {activeStudy
                  ? 'Esta campaña no está abierta o su plazo ha vencido. No difundas el enlace hasta habilitar una campaña vigente.'
                  : 'Crea primero una campaña de evaluación.'}
              </p>
            )}
          </Card>

          {/* Real, server-validated invitation codes (no localStorage security theater). */}
          <Card className="p-6 space-y-4">
            <div className="flex items-start gap-3">
              <Lock size={20} className="text-amber" />
              <div>
                <h3 className="text-base font-bold text-dark">
                  Acceso de trabajadores
                </h3>
                <p className="text-xs text-muted mt-1">
                  {activeStudy?.requires_invitation
                    ? 'Este estudio exige códigos personales de un solo uso, validados en el servidor.'
                    : 'El estudio acepta respuestas con su enlace público. Para restringirlo, activa «Requiere invitación» antes de abrir el estudio.'}
                </p>
              </div>
            </div>
            {activeStudy?.requires_invitation ? (
              <>
                <label
                  className="text-xs font-semibold"
                  htmlFor="invitation-count"
                >
                  Cantidad de códigos
                </label>
                <input
                  id="invitation-count"
                  type="number"
                  min="1"
                  max="1000"
                  value={invitationCount}
                  onChange={(event) => setInvitationCount(event.target.value)}
                  className="colmena-input w-36"
                />
                <button
                  type="button"
                  onClick={() => issueInvitations.mutate()}
                  disabled={
                    !canDistribute ||
                    issueInvitations.isPending ||
                    Number(invitationCount) < 1 ||
                    Number(invitationCount) > 1000
                  }
                  className="px-4 py-2 rounded-lg bg-amber text-dark font-bold text-xs"
                >
                  {issueInvitations.isPending
                    ? 'Generando…'
                    : 'Emitir invitaciones'}
                </button>
                {issueInvitations.isError && (
                  <p role="alert" className="text-xs text-danger">
                    {issueInvitations.error?.message}
                  </p>
                )}
                {!canDistribute && (
                  <p className="text-xs text-muted">
                    La emisión de invitaciones sólo está disponible para
                    campañas abiertas y vigentes.
                  </p>
                )}
                {issuedTokens.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs text-muted">
                      Copia los códigos ahora: por seguridad no podrán
                      recuperarse de la API después.
                    </p>
                    <textarea
                      readOnly
                      className="colmena-input w-full font-mono text-xs"
                      rows="5"
                      value={issuedTokens.join('\n')}
                    />
                    <button
                      type="button"
                      className="text-xs font-semibold underline"
                      onClick={() =>
                        navigator.clipboard.writeText(issuedTokens.join('\n'))
                      }
                    >
                      Copiar todos los códigos
                    </button>
                  </div>
                )}
              </>
            ) : null}
          </Card>

          {activeStudy?.requires_invitation && (
            <Card className="p-6 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-base font-bold text-dark">
                    Control de invitaciones
                  </h3>
                  <p className="text-xs text-muted">
                    {pendingInvitations.length} disponibles · {consumedCount}{' '}
                    utilizadas · {invitations.length} registradas
                  </p>
                </div>
                <button
                  type="button"
                  className="inline-flex items-center gap-2 text-xs font-semibold text-muted hover:text-dark"
                  onClick={() =>
                    queryClient.invalidateQueries({
                      queryKey: ['study-invitations', activeStudy.id],
                    })
                  }
                >
                  <RefreshCcw size={14} /> Actualizar
                </button>
              </div>
              <label
                className="block text-xs font-semibold text-muted"
                htmlFor="revoke-reason"
              >
                Motivo de revocación (opcional)
              </label>
              <input
                id="revoke-reason"
                className="colmena-input w-full"
                maxLength={300}
                placeholder="Ej. Invitación enviada por error"
                value={revocationReason}
                onChange={(event) => setRevocationReason(event.target.value)}
              />
              {loadingInvitations && (
                <p className="text-xs text-muted">Consultando invitaciones…</p>
              )}
              {failedInvitations && (
                <p role="alert" className="text-xs text-danger">
                  No fue posible consultar las invitaciones. Reintenta la
                  operación.
                </p>
              )}
              {revokeInvitation.isError && (
                <p role="alert" className="text-xs text-danger">
                  {revokeInvitation.error?.message ||
                    'No se pudo revocar la invitación.'}
                </p>
              )}
              {!loadingInvitations &&
                !failedInvitations &&
                invitations.length === 0 && (
                  <p className="text-xs text-muted">
                    No se han emitido invitaciones para esta campaña.
                  </p>
                )}
              <div className="max-h-80 space-y-2 overflow-y-auto">
                {invitations.map((invitation) => {
                  const canRevoke = ['PENDING', 'SENT'].includes(
                    invitation.status,
                  );
                  return (
                    <div
                      key={invitation.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border px-3 py-2"
                    >
                      <div>
                        <p className="font-mono text-xs text-dark">
                          Invitación #{invitation.id}
                        </p>
                        <p className="text-[11px] text-muted">
                          {invitation.status === 'CONSUMED'
                            ? 'Utilizada'
                            : invitation.status === 'REVOKED'
                              ? 'Revocada'
                              : invitation.status === 'EXPIRED'
                                ? 'Caducada'
                                : 'Pendiente'}
                        </p>
                      </div>
                      {canRevoke && (
                        <button
                          type="button"
                          className="rounded-lg border border-danger/40 px-3 py-1.5 text-xs font-semibold text-danger hover:bg-danger/10 disabled:opacity-50"
                          disabled={revokeInvitation.isPending}
                          onClick={() => revokeInvitation.mutate(invitation.id)}
                        >
                          Revocar acceso
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
              <p className="text-[11px] text-muted">
                Los códigos secretos no se recuperan del servidor después de
                emitirlos. La revocación impide su canje futuro.
              </p>
            </Card>
          )}
        </div>

        {/* QR Code & Information Sidebar */}
        <div className="space-y-6">
          <Card className="p-6 text-center space-y-4">
            <div className="inline-flex items-center gap-1.5 text-xs font-bold text-dark">
              <QrCode size={16} className="text-amber" /> Código QR de
              Aplicación
            </div>

            {surveyUrl ? (
              <div
                ref={qrContainerRef}
                className="mx-auto flex h-48 w-48 items-center justify-center rounded-2xl border-2 border-border bg-white p-3 shadow-inner"
              >
                <QRCodeSVG
                  value={surveyUrl}
                  size={168}
                  level="M"
                  marginSize={1}
                  title="Código QR de la encuesta"
                />
              </div>
            ) : null}

            <p className="text-[11px] text-muted leading-tight">
              Imprime este código QR para colocarlo en afiches, áreas comunes o
              enviar por WhatsApp corporativo.
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
