import { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { AlertTriangle, Download, FileText, RefreshCw, ShieldCheck, Upload, Image as ImageIcon, Trash2, CheckCircle2 } from 'lucide-react';

import { useActiveProject } from '../../../hooks/useActiveProject.js';
import { getProject } from '../../../api/projects.js';
import { getStudy, listStudies } from '../../../api/studies.js';
import { fetchProtectedBlob, downloadProtectedFile } from '../../../api/protectedFiles.js';
import { getCensopasReadiness } from '../../../api/instruments.js';
import {
  createReportPreview,
  getReportDownloadUrl,
  getReportPreviewPdfUrl,
} from '../../../api/reports.js';

import { PageHeader } from '../../../components/layout/PageHeader.jsx';
import { Card } from '../../../components/ui/Card.jsx';
import { Button } from '../../../components/ui/Button.jsx';
import { LoadingState } from '../../../components/ui/LoadingState.jsx';
import { EmptyState } from '../../../components/ui/EmptyState.jsx';
import { ProjectMissingState } from '../../../components/colmena/ProjectMissingState.jsx';
import StudySelector from '../../../components/colmena/StudySelector.jsx';
import CensopasReadinessPanel from '../../../components/colmena/instruments/CensopasReadinessPanel.jsx';

const SECTIONS = [
  { key: 'portada', label: 'Portada' },
  { key: 'resumen_ejecutivo', label: 'Resumen ejecutivo' },
  { key: 'ficha_tecnica', label: 'Ficha técnica' },
  { key: 'calidad_datos', label: 'Calidad de datos (participación)' },
  { key: 'resultados_globales', label: 'Resultados globales' },
  { key: 'dimensiones', label: 'Dimensiones' },
  { key: 'subdimensiones', label: 'Subdimensiones' },
  { key: 'unidades_seguras', label: 'Unidades seguras' },
  { key: 'variables_descriptivas', label: 'Variables descriptivas' },
  { key: 'hallazgos_premium', label: 'Hallazgos premium' },
  { key: 'plan_accion', label: 'Plan de acción' },
  { key: 'anexos', label: 'Anexos' },
  { key: 'firmas', label: 'Firmas' },
];

export default function ProjectReportsPage({ overrideProjectId }) {
  const params = useParams();
  const projectId = overrideProjectId || params.projectId;
  useActiveProject(projectId);

  const [studyId, setStudyId] = useState(null);
  const [sections, setSections] = useState(SECTIONS.map((s) => s.key));
  const [reportMode, setReportMode] = useState('PROVISIONAL');
  const [outputFormat, setOutputFormat] = useState('PDF');
  const [previewState, setPreviewState] = useState('IDLE');
  const [preview, setPreview] = useState(null);
  const [previewBlobUrl, setPreviewBlobUrl] = useState(null);
  const [downloadError, setDownloadError] = useState(null);
  const [generatedConfig, setGeneratedConfig] = useState(null);

  // Logo state
  const fileInputRef = useRef(null);
  const [companyLogo, setCompanyLogo] = useState(() => {
    return localStorage.getItem(`company_logo_${projectId}`) || null;
  });

  const { data: project, isLoading: isLoadingProject } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });

  const { data: studiesData } = useQuery({
    queryKey: ['studies', projectId],
    queryFn: () => listStudies(projectId, { page: 1, pageSize: 50 }),
    enabled: Boolean(projectId),
  });

  const studies = studiesData?.items || [];

  // Auto-select first study if not selected
  useEffect(() => {
    if (!studyId && studies.length > 0) {
      setStudyId(studies[0].id);
    }
  }, [studies, studyId]);

  const { data: study } = useQuery({
    queryKey: ['study', studyId],
    queryFn: () => getStudy(studyId),
    enabled: Boolean(studyId),
  });

  const { data: readiness, isFetching: isLoadingReadiness } = useQuery({
    queryKey: ['censopas-readiness', study?.instrument_version_id],
    queryFn: () => getCensopasReadiness(study.instrument_version_id),
    enabled: Boolean(study?.instrument_version_id),
  });

  const currentConfig = { studyId, sections: [...sections].sort(), reportMode, outputFormat };

  const previewMutation = useMutation({
    mutationFn: () =>
      createReportPreview(studyId, {
        report_mode: reportMode,
        output_format: outputFormat,
        sections,
      }),
    onMutate: () => setPreviewState('GENERATING'),
    onSuccess: (data) => {
      setPreview(data);
      setGeneratedConfig(currentConfig);
      setPreviewState('READY');
    },
    onError: () => setPreviewState('ERROR'),
  });

  useEffect(() => {
    let cancelled = false;
    let objectUrl = null;
    if (preview?.preview_id) {
      fetchProtectedBlob(getReportPreviewPdfUrl(preview.preview_id))
        .then((blob) => {
          if (cancelled) return;
          objectUrl = URL.createObjectURL(blob);
          setPreviewBlobUrl(objectUrl);
        })
        .catch(() => { if (!cancelled) setPreviewBlobUrl(null); });
    }
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      setPreviewBlobUrl(null);
    };
  }, [preview?.preview_id]);

  // Auto generate preview when studyId is first set
  const autoGeneratedRef = useRef(false);
  useEffect(() => {
    if (studyId && !autoGeneratedRef.current && previewState === 'IDLE') {
      autoGeneratedRef.current = true;
      previewMutation.mutate();
    }
  }, [studyId]);

  useEffect(() => {
    if (previewState === 'READY' && generatedConfig && JSON.stringify(generatedConfig) !== JSON.stringify(currentConfig)) {
      setPreviewState('STALE');
    }
  }, [studyId, sections, reportMode, outputFormat]);

  const handleLogoUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      alert('El archivo no debe superar los 5MB.');
      return;
    }
    const reader = new FileReader();
    reader.onload = (event) => {
      const base64 = event.target?.result;
      if (typeof base64 === 'string') {
        setCompanyLogo(base64);
        localStorage.setItem(`company_logo_${projectId}`, base64);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleRemoveLogo = () => {
    setCompanyLogo(null);
    localStorage.removeItem(`company_logo_${projectId}`);
  };

  const toggleSection = (key) => {
    setSections((prev) => (prev.includes(key) ? prev.filter((s) => s !== key) : [...prev, key]));
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
    <div className="colmena-page space-y-6">
      <PageHeader
        eyebrow="Reportes de evaluación — AURORA PRO"
        title={project.name}
        description="Genera e imprime el Informe de Evaluación de Riesgos Psicosociales con membrete y logo institucional."
      />

      <div className="grid gap-6 md:grid-cols-[380px_1fr]">
        <div className="space-y-4">
          {/* Logo Upload Card */}
          <Card className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="colmena-label flex items-center gap-1.5">
                <ImageIcon size={14} className="text-amber" />
                Logo Institucional de la Empresa
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
              accept="image/png, image/jpeg, image/svg+xml"
              onChange={handleLogoUpload}
              className="hidden"
            />

            {companyLogo ? (
              <div className="flex items-center justify-between p-3 rounded-xl border border-border bg-surfaceSoft">
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
                className="w-full flex flex-col items-center justify-center p-4 border-2 border-dashed border-border hover:border-amber rounded-xl bg-surfaceSoft/50 hover:bg-surfaceSoft transition text-center space-y-1.5"
              >
                <Upload size={20} className="text-amber" />
                <span className="text-xs font-semibold text-dark">Subir Logo de la Empresa</span>
                <span className="text-[10px] text-muted">PNG, JPG o SVG (Máx. 5MB)</span>
              </button>
            )}
          </Card>

          {/* Report Config Card */}
          <Card className="flex flex-col gap-5 p-4">
            <div className="flex flex-col gap-3">
              <p className="colmena-label">Estudio de Evaluación</p>
              <StudySelector
                projectId={projectId}
                studyId={studyId}
                onStudyChange={(value) => {
                  setStudyId(value);
                  resetPreview();
                }}
              />
              {studyId ? <CensopasReadinessPanel readiness={readiness} isLoading={isLoadingReadiness} /> : null}
            </div>

            <div>
              <p className="colmena-label mb-2">Secciones a incluir en el informe</p>
              <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto pr-1">
                {SECTIONS.map((section) => (
                  <button
                    key={section.key}
                    type="button"
                    onClick={() => toggleSection(section.key)}
                    className={`text-xs px-2.5 py-1 rounded-lg font-medium transition ${
                      sections.includes(section.key)
                        ? 'bg-amber text-dark font-semibold'
                        : 'bg-surfaceSoft border border-border text-muted hover:text-dark'
                    }`}
                  >
                    {section.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="colmena-label mb-2">Validez Metodológica</p>
              <div className="grid gap-2 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setReportMode('PROVISIONAL')}
                  className={'rounded-xl border p-3 text-left transition ' + (reportMode === 'PROVISIONAL' ? 'border-amber bg-amber/5 ring-1 ring-amber/30' : 'border-border bg-surface')}
                >
                  <FileText size={16} className="mb-1.5 text-amber" />
                  <span className="block text-xs font-semibold text-dark">Informe Preliminar</span>
                </button>
                <button
                  type="button"
                  disabled={!readiness?.ready_for_official_reporting}
                  onClick={() => setReportMode('OFFICIAL')}
                  className={'rounded-xl border p-3 text-left transition ' + (reportMode === 'OFFICIAL' ? 'border-turquoise bg-turquoise/5 ring-1 ring-turquoise/30' : 'border-border bg-surface') + ' disabled:cursor-not-allowed disabled:opacity-50'}
                >
                  <ShieldCheck size={16} className="mb-1.5 text-turquoise" />
                  <span className="block text-xs font-semibold text-dark">Informe con equivalencia metodológica verificada</span>
                </button>
              </div>
            </div>

            <div>
              <label className="colmena-label mb-2 block" htmlFor="report-output-format">Formato de Salida</label>
              <select
                id="report-output-format"
                className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-xs font-medium text-dark focus:border-amber outline-none"
                value={outputFormat}
                onChange={(event) => setOutputFormat(event.target.value)}
              >
                <option value="PDF">Documento PDF (.pdf)</option>
                <option value="DOCX">Microsoft Word (.docx)</option>
              </select>
            </div>

            <Button
              variant="primary"
              size="md"
              onClick={() => previewMutation.mutate()}
              disabled={!studyId || previewState === 'GENERATING'}
              loading={previewState === 'GENERATING'}
              className="w-full flex items-center justify-center gap-2 font-bold"
            >
              <RefreshCw size={16} />
              Generar vista previa
            </Button>
          </Card>
        </div>

        {/* Report Preview Panel */}
        <Card className="flex min-h-[600px] flex-col gap-3 p-5">
          {previewState === 'IDLE' ? (
            <EmptyState
              title="Generación de Reporte de Riesgos Psicosociales"
              description="Selecciona el estudio y presiona «Generar Informe PDF Oficial» para procesar la carátula institucional, tablas de semaforización y plan de acción."
            />
          ) : null}
          {previewState === 'GENERATING' ? <LoadingState label="Procesando datos y renderizando informe PDF oficial..." /> : null}
          {previewState === 'ERROR' ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
              <AlertTriangle size={28} className="text-danger" />
              <p className="text-sm font-medium text-danger">Error al generar la vista previa del informe.</p>
              <Button variant="secondary" size="sm" onClick={() => previewMutation.mutate()}>
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
              <div className="flex items-center justify-between text-xs text-muted">
                <span>Páginas renderizadas: {preview.pages || '—'}</span>
                {companyLogo ? (
                  <span className="text-emerald-600 font-semibold flex items-center gap-1">
                    <CheckCircle2 size={12} /> Incluye membrete y logo de empresa
                  </span>
                ) : null}
              </div>
              <iframe
                title="Vista previa del reporte PDF"
                src={previewBlobUrl || 'about:blank'}
                className="min-h-[580px] flex-1 rounded-xl border border-border shadow-inner"
              />
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
                  const isPdf = outputFormat === 'PDF';
                  const url = isPdf ? getReportPreviewPdfUrl(preview.preview_id) : getReportDownloadUrl(preview.preview_id);
                  await downloadProtectedFile(url, `aurora-reporte-${preview.preview_id}.${isPdf ? 'pdf' : 'docx'}`);
                } catch (error) {
                  setDownloadError(error.message);
                }
              }}
              className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber hover:bg-amber-600 text-dark font-bold text-xs transition ${
                canExport ? '' : 'pointer-events-none opacity-50'
              }`}
            >
              <Download size={16} />
              Descargar {outputFormat === 'PDF' ? 'PDF' : 'Word editable'}
            </button>
            {downloadError ? <p role="alert" className="text-xs text-danger">{downloadError}</p>}
          </div>
        </Card>
      </div>
    </div>
  );
}
