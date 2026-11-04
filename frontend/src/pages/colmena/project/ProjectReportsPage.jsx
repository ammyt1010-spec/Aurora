import { useEffect, useMemo, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { AlertTriangle, Download, ExternalLink, FileText, Upload, Image as ImageIcon, Trash2, CheckCircle2 } from 'lucide-react';

import { useActiveProject } from '../../../hooks/useActiveProject.js';
import { getActiveStudyId, setActiveStudyId } from '../../../utils/activeStudy.js';
import { getProject } from '../../../api/projects.js';
import { listOrganizations } from '../../../api/organizations.js';
import { getStudy, listStudies } from '../../../api/studies.js';
import { fetchProtectedBlob, downloadProtectedFile } from '../../../api/protectedFiles.js';
import {
  createReportPreview,
  getReportPreviewPdfUrl,
} from '../../../api/reports.js';

import '../../../design/PremiumSurfaces.css';
import { Card } from '../../../components/ui/Card.jsx';
import { Button } from '../../../components/ui/Button.jsx';
import { LoadingState } from '../../../components/ui/LoadingState.jsx';
import { EmptyState } from '../../../components/ui/EmptyState.jsx';
import { ProjectMissingState } from '../../../components/colmena/ProjectMissingState.jsx';
import StudySelector, { reportInstrumentLabel } from '../../../components/colmena/StudySelector.jsx';
import PdfCanvasViewer from '../../../components/colmena/PdfCanvasViewer.jsx';

const SIGNATORY_ROLES = [
  { role: 'PROFESSIONAL', label: 'Profesional responsable', short: 'Profesional', detail: 'Psicología o salud ocupacional' },
  { role: 'COMPANY', label: 'Representante de la empresa', short: 'Empresa', detail: 'Conformidad de la organización' },
  { role: 'SST', label: 'Responsable SST', short: 'SST', detail: 'Seguridad y salud en el trabajo' },
  { role: 'PSYCHOLOGY', label: 'Psicología ocupacional', short: 'Psicología', detail: 'Revisión especializada' },
];

export default function ProjectReportsPage({ overrideProjectId }) {
  const params = useParams();
  const projectId = overrideProjectId || params.projectId;
  useActiveProject(projectId);

  const [studyId, setStudyId] = useState(() => getActiveStudyId(projectId));
  const [previewState, setPreviewState] = useState('IDLE');
  const [preview, setPreview] = useState(null);
  const [previewBlobUrl, setPreviewBlobUrl] = useState(null);
  const [previewBlob, setPreviewBlob] = useState(null);
  const [viewerError, setViewerError] = useState(null);
  const [downloadError, setDownloadError] = useState(null);
  const [generatedConfig, setGeneratedConfig] = useState(null);
  const [signatories, setSignatories] = useState(() => Object.fromEntries(SIGNATORY_ROLES.map(({ role }) => [role, { name: '', registry: '', signature_png: null }])));
  const [signaturesAuthorized, setSignaturesAuthorized] = useState(false);
  const [assetError, setAssetError] = useState(null);

  // Logo state
  const fileInputRef = useRef(null);
  const [companyLogo, setCompanyLogo] = useState(() => {
    const savedLogo = localStorage.getItem(`company_logo_${projectId}`);
    return savedLogo?.startsWith('data:image/png;base64,') ? savedLogo : null;
  });

  const { data: project, isLoading: isLoadingProject } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });
  const { data: memberships = [] } = useQuery({ queryKey: ['organizations'], queryFn: listOrganizations });
  const companyMembership = memberships.find((item) => item.organization.id === project?.organization_id);
  const company = companyMembership?.organization;

  const { data: studiesData } = useQuery({
    queryKey: ['studies', projectId],
    queryFn: () => listStudies(projectId, { page: 1, pageSize: 50 }),
    enabled: Boolean(projectId),
  });

  const studies = studiesData?.items || [];

  // Mantiene el mismo instrumento al pasar de Telemetría a Informe.
  useEffect(() => {
    if (!studies.length) return;
    const preferred = studies.find((item) => item.id === studyId)
      || studies.find((item) => item.id === Number(project?.metadata?.censopas_study_id))
      || studies.find((item) => item.name && item.name.toLowerCase().includes('minero'))
      || studies[0];
    if (preferred.id !== studyId) setStudyId(preferred.id);
    setActiveStudyId(projectId, preferred.id);
  }, [studies, studyId, projectId, project?.metadata?.censopas_study_id]);

  const { data: study } = useQuery({
    queryKey: ['study', studyId],
    queryFn: () => getStudy(studyId),
    enabled: Boolean(studyId),
  });
  const selectedInstrument = study ? reportInstrumentLabel(study) : null;

  const currentConfig = useMemo(() => JSON.stringify({
    studyId, companyLogo, signatories, signaturesAuthorized,
  }), [studyId, companyLogo, signatories, signaturesAuthorized]);
  const reportSignatories = SIGNATORY_ROLES.flatMap(({ role }) => {
    const item = signatories[role];
    return item.name.trim() ? [{ role, name: item.name.trim(), registry: item.registry.trim() || null, signature_png: item.signature_png }] : [];
  });
  const missingSignerName = SIGNATORY_ROLES.some(({ role }) => signatories[role].signature_png && !signatories[role].name.trim());
  const hasSignatureImage = SIGNATORY_ROLES.some(({ role }) => Boolean(signatories[role].signature_png));

  const previewMutation = useMutation({
    mutationFn: () =>
      createReportPreview(studyId, {
        report_mode: 'SAMPLE',
        is_sample_preview: true,
        company_logo_png: companyLogo?.startsWith('data:image/png;base64,') ? companyLogo : null,
        signatories: reportSignatories,
        signatures_authorized: signaturesAuthorized,
        output_format: 'PDF',
        sections: [],
      }),
    onMutate: () => setPreviewState('GENERATING'),
    onSuccess: (data, requestConfig) => {
      setPreview(data);
      setGeneratedConfig(requestConfig.config);
      setPreviewState('READY');
    },
    onError: () => setPreviewState('ERROR'),
  });

  useEffect(() => {
    let cancelled = false;
    let objectUrl = null;
    let retryTimer = null;
    if (preview?.preview_id) {
      setPreviewBlob(null);
      setViewerError(null);
      const loadPdf = (attempt) => {
        fetchProtectedBlob(getReportPreviewPdfUrl(preview.preview_id))
          .then((blob) => {
            if (cancelled) return;
            objectUrl = URL.createObjectURL(blob);
            setPreviewBlobUrl(objectUrl);
            setPreviewBlob(blob);
          })
          .catch(() => {
            if (cancelled) return;
            if (attempt < 2) {
              retryTimer = window.setTimeout(() => loadPdf(attempt + 1), 450 * (attempt + 1));
            } else {
              setPreviewBlobUrl(null);
              setViewerError('No se pudo cargar la vista previa. Intenta descargar el PDF o generar el informe de nuevo.');
            }
          });
      };
      loadPdf(0);
    }
    return () => {
      cancelled = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      setPreviewBlobUrl(null);
      setPreviewBlob(null);
    };
  }, [preview?.preview_id]);

  useEffect(() => {
    if ((previewState === 'READY' || previewState === 'STALE') && generatedConfig && generatedConfig !== currentConfig) {
      setPreviewState('STALE');
    }
  }, [currentConfig, generatedConfig, previewState]);

  const handleLogoUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.type !== 'image/png' || file.size > 600 * 1024) {
      setAssetError('Selecciona un logotipo PNG de hasta 600 KB.');
      return;
    }
    setAssetError(null);
    const reader = new FileReader();
    reader.onload = (event) => {
      const base64 = event.target?.result;
      if (typeof base64 === 'string') {
        setCompanyLogo(base64);
        if (previewState === 'READY') setPreviewState('STALE');
        localStorage.setItem(`company_logo_${projectId}`, base64);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleRemoveLogo = () => {
    setCompanyLogo(null);
    if (previewState === 'READY') setPreviewState('STALE');
    localStorage.removeItem(`company_logo_${projectId}`);
  };

  const updateSignatory = (role, update) => {
    setSignatories((previous) => ({ ...previous, [role]: { ...previous[role], ...update } }));
  };

  const handleSignatureUpload = (role, file) => {
    if (!file) return;
    if (file.type !== 'image/png' || file.size > 300 * 1024) {
      setAssetError('La firma debe ser PNG y no superar 300 KB.');
      return;
    }
    setAssetError(null);
    const reader = new FileReader();
    reader.onload = (event) => {
      if (typeof event.target?.result === 'string') updateSignatory(role, { signature_png: event.target.result });
    };
    reader.readAsDataURL(file);
  };

  const resetPreview = () => {
    setPreview(null);
    setGeneratedConfig(null);
    setPreviewState('IDLE');
  };

  if (isLoadingProject) return <LoadingState label="Cargando..." />;
  if (!project) return <ProjectMissingState />;

  const canExport = previewState === 'READY' && preview;


  return (
    <div className="colmena-page aurora-premium-page space-y-4">
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3 xl:grid-cols-[minmax(330px,390px)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-3">
          <Card className="aurora-report-builder min-w-0 space-y-3 p-4">
            <div>
              <h1 className="text-base font-extrabold text-dark">Informe técnico</h1>
              <p className="text-[11px] text-muted">Paso 3 de 3 · Elige la aplicación, añade responsables y revisa el PDF.</p>
            </div>
            <div>
              <label className="colmena-label mb-1 block">1. Estudio</label>
              <StudySelector projectId={projectId} studyId={studyId} showInstrument onStudyChange={(value) => {
                setStudyId(value);
                setActiveStudyId(projectId, value);
                resetPreview();
              }} />
              <p className="mt-1 text-[10px] leading-4 text-muted">Se crea un informe independiente por instrumento, usando solo las respuestas de esta aplicación.</p>
              {company && <div className="mt-1 flex flex-wrap items-center gap-x-2 text-[10px] text-muted">
                <span className="max-w-[235px] truncate" title={company.legal_name || company.name}>{company.legal_name || company.name}</span>
                <span className="font-semibold text-[#315788]">RUC {company.tax_id || 'no registrado'}</span>
              </div>}
            </div>
            <div className="flex items-center justify-between">
              <p className="colmena-label flex items-center gap-1.5">
                <ImageIcon size={14} className="text-amber" />
                2. Logo de la empresa
              </p>
              {companyLogo ? (
                <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-600 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                  <CheckCircle2 size={11} /> Vinculado
                </span>
              ) : null}
            </div>

            <input
              type="file"
              ref={fileInputRef}
              accept="image/png"
              onChange={handleLogoUpload}
              className="hidden"
            />

            {companyLogo ? (
              <div className="flex items-center justify-between p-2 rounded-xl border border-border bg-surfaceSoft">
                <img src={companyLogo} alt="Logo empresa" className="max-h-12 max-w-[160px] object-contain" />
                <button
                  type="button"
                  onClick={handleRemoveLogo}
                  className="p-1.5 rounded-lg text-muted hover:text-red-500 hover:bg-red-500/10 transition"
                  title="Eliminar logo"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-surfaceSoft/50 px-3 py-2 text-center transition hover:border-amber hover:bg-surfaceSoft"
              >
                <Upload size={15} className="text-amber" />
                <span className="text-xs font-semibold text-dark">Añadir logo PNG</span>
                <span className="text-[10px] text-muted">máx. 600 KB</span>
              </button>
            )}
            <div className="border-t border-border/70 pt-2">
              <p className="colmena-label">3. Responsables y firmas</p>
              <p className="mb-1 text-[10px] text-muted">Nombre, registro y firma PNG opcional.</p>
              <div className="space-y-1">
                {SIGNATORY_ROLES.map(({ role, label, short, detail }) => {
                  const person = signatories[role];
                  return <div key={role} className="grid grid-cols-[78px_minmax(0,1fr)_66px_30px_18px] items-center gap-1 rounded-lg border border-border/80 bg-white/80 px-1.5 py-1">
                    <span title={`${label} · ${detail}`} className="truncate text-[10px] font-bold text-dark">{short}</span>
                    <input aria-label={`Nombre de ${label}`} placeholder="Nombre completo" maxLength={120} value={person.name}
                      onChange={(event) => updateSignatory(role, { name: event.target.value })} className="aurora-report-field" />
                    <input aria-label={`Registro de ${label}`} placeholder="Registro" maxLength={80} value={person.registry}
                      onChange={(event) => updateSignatory(role, { registry: event.target.value })} className="aurora-report-field" />
                    <label title={`Añadir firma PNG de ${label}`} className="flex h-7 cursor-pointer items-center justify-center rounded-md border border-border text-[#315788] hover:bg-[#EDF5FC]">
                        <input type="file" accept="image/png" className="sr-only" aria-label={`Firma PNG de ${label}`}
                          onChange={(event) => { handleSignatureUpload(role, event.target.files?.[0]); event.target.value = ''; }} />
                        {person.signature_png ? <CheckCircle2 size={14} aria-hidden="true" /> : <Upload size={14} aria-hidden="true" />}
                    </label>
                    {person.signature_png ? <button type="button" aria-label={`Quitar firma de ${label}`} onClick={() => updateSignatory(role, { signature_png: null })}
                      className="text-muted hover:text-red-600"><Trash2 size={13} /></button> : <span />}
                  </div>;
                })}
              </div>
            </div>
            {hasSignatureImage && <div className="flex flex-wrap gap-1.5" aria-label="Firmas cargadas">
              {SIGNATORY_ROLES.filter(({ role }) => signatories[role].signature_png).map(({ role, short }) => (
                <div key={role} className="flex items-center gap-1 rounded-lg border border-border bg-white px-1.5 py-1">
                  <img src={signatories[role].signature_png} alt={`Vista previa de firma de ${short}`} className="h-6 max-w-14 object-contain" />
                  <span className="text-[9px] text-muted">{short}</span>
                </div>
              ))}
            </div>}
            {assetError && <p role="alert" className="text-xs text-danger">{assetError}</p>}
            {missingSignerName && <p role="alert" className="text-xs text-danger">Cada firma requiere el nombre de su responsable.</p>}
            {hasSignatureImage && <label className="flex items-start gap-2 rounded-lg bg-[#F3F8FC] p-2 text-[11px] leading-4 text-[#315788]">
              <input type="checkbox" checked={signaturesAuthorized} onChange={(event) => setSignaturesAuthorized(event.target.checked)} className="mt-0.5 shrink-0" />
              Confirmo que cuento con autorización para incorporar estas imágenes de firma al informe.
            </label>}
            <div className="border-t border-border/70 pt-2">
              <Button variant="primary" size="md" onClick={() => previewMutation.mutate({ config: currentConfig })}
                disabled={!studyId || missingSignerName || (hasSignatureImage && !signaturesAuthorized) || previewState === 'GENERATING'}
                loading={previewState === 'GENERATING'} className="flex w-full items-center justify-center gap-2 font-bold">
                <FileText size={16} /> Generar informe PDF
              </Button>
              <p className="mt-2 text-[10px] leading-4 text-muted">El demo genera un PDF completo con datos sintéticos y marca de agua.</p>
              <p className="mt-2 text-[10px] leading-4 text-muted">La imagen de una firma es una reproducción aportada por la empresa; no equivale a una firma digital certificada.</p>
            </div>
          </Card>
        </div>

        {/* Report Preview Panel */}
        <Card className="aurora-report-viewer flex min-h-[680px] min-w-0 flex-col gap-3 p-4 sm:p-5">
          {previewState === 'IDLE' ? (
            <EmptyState
              title="Previsualización del informe por instrumento"
              description="Elige la aplicación, añade logo y responsables si deseas, y genera su PDF independiente para revisarlo aquí."
            />
          ) : null}
          {previewState === 'GENERATING' ? <LoadingState label="Procesando datos y renderizando el informe PDF..." /> : null}
          {previewState === 'ERROR' ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
              <AlertTriangle size={28} className="text-danger" />
              <p className="text-sm font-medium text-danger">{previewMutation.error?.message || 'Error al generar la vista previa del informe.'}</p>
              <Button variant="secondary" size="sm" onClick={() => previewMutation.mutate({ config: currentConfig })}>
                Reintentar
              </Button>
            </div>
          ) : null}
          {(previewState === 'READY' || previewState === 'STALE' || previewState === 'EXPORTING') && preview ? (
            <>
              {previewState === 'STALE' ? (
                <p className="rounded-xl border border-amber/30 bg-amber/10 px-3 py-2 text-xs font-medium text-yellowDark">
                  Se modificaron parámetros. Haz clic en actualizar para regenerar la vista previa.
                </p>
              ) : null}
              {preview.is_sample && (
                <p className="rounded-lg border border-amber/30 bg-amber/10 p-2 text-xs font-bold text-yellowDark">
                  INFORME DE PRUEBA · DATOS SINTÉTICOS · MARCA DE AGUA
                </p>
              )}
              <div className="flex items-center justify-between text-xs text-muted">
                <span>Páginas renderizadas: {preview.pages || '—'}</span>
                {companyLogo ? (
                  <span className="text-emerald-600 font-semibold flex items-center gap-1">
                    <CheckCircle2 size={12} /> Logo incorporado al informe generado
                  </span>
                ) : null}
              </div>
              {selectedInstrument && <p className="text-xs font-semibold text-[#315788]">Informe individual · {selectedInstrument}</p>}
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-surfaceSoft px-3 py-2">
                <span className="text-xs font-semibold text-dark">Informe completo · página por página</span>
                <div className="flex flex-wrap gap-2">
                  <button type="button" disabled={!previewBlobUrl}
                    onClick={() => { if (previewBlobUrl) window.open(previewBlobUrl, '_blank', 'noopener,noreferrer'); }}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-dark hover:bg-white disabled:opacity-40">
                    <ExternalLink size={13} /> Abrir en otra pestaña
                  </button>
                </div>
              </div>
              {viewerError && <p role="alert" className="text-xs text-danger">{viewerError}</p>}
              {previewBlob ? <PdfCanvasViewer blob={previewBlob} /> : !viewerError ? <LoadingState label="Abriendo las páginas del PDF..." /> : null}
            </>
          ) : null}

          <div className="flex justify-end gap-3 border-t border-border pt-4">
            <button
              type="button"
              disabled={!canExport}
              onClick={async () => {
                if (!preview) return;
                setDownloadError(null);
                try {
                  await downloadProtectedFile(getReportPreviewPdfUrl(preview.preview_id), `aurora-informe-demo-${preview.preview_id}.pdf`);
                } catch (error) {
                  setDownloadError(error.message);
                }
              }}
              className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber hover:bg-amber-600 text-dark font-bold text-xs transition ${
                canExport ? '' : 'pointer-events-none opacity-50'
              }`}
            >
              <Download size={16} />
              Descargar PDF de prueba
            </button>
            {downloadError ? <p role="alert" className="text-xs text-danger">{downloadError}</p> : null}
          </div>
        </Card>
      </div>
    </div>
  );
}
