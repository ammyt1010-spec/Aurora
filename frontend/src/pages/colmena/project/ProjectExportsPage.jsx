import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, FileDown, ShieldCheck } from 'lucide-react';

import { useActiveProject } from '../../../hooks/useActiveProject.js';
import { getProject } from '../../../api/projects.js';
import { createExport, getExportDownloadUrl, listExports } from '../../../api/exports.js';
import { downloadProtectedFile } from '../../../api/protectedFiles.js';

import { PageHeader } from '../../../components/layout/PageHeader.jsx';
import { Card } from '../../../components/ui/Card.jsx';
import { Button } from '../../../components/ui/Button.jsx';
import { EmptyState } from '../../../components/ui/EmptyState.jsx';
import { LoadingState } from '../../../components/ui/LoadingState.jsx';
import { ProjectMissingState } from '../../../components/colmena/ProjectMissingState.jsx';
import StudySelector from '../../../components/colmena/StudySelector.jsx';
import { displayLabel } from '../../../utils/labels.js';

const AVAILABLE_EXPORT_TYPES = ['CSV', 'XLSX', 'JSON'];
const PENDING_EXPORT_TYPES = [
  { type: 'SPSS', label: 'SPSS' },
  { type: 'POWERBI', label: 'Power BI' },
  { type: 'PARQUET', label: 'Parquet' },
];
const SHAPES = [
  { value: 'WIDE', label: 'Ancho (una fila por respondiente)' },
  { value: 'LONG', label: 'Largo (una fila por respuesta)' },
];

export default function ProjectExportsPage() {
  const { projectId } = useParams();
  const [studyId, setStudyId] = useState(null);
  const [shape, setShape] = useState('WIDE');
  const [downloadError, setDownloadError] = useState(null);
  const queryClient = useQueryClient();
  useActiveProject(projectId);

  const { data: project, isLoading: isLoadingProject } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });

  const { data: exports = [], isLoading: isLoadingExports } = useQuery({
    queryKey: ['exports', studyId],
    queryFn: () => listExports(studyId),
    enabled: Boolean(studyId),
    refetchInterval: (query) => (query.state.data?.some((e) => e.status === 'PENDING') ? 2000 : false),
  });

  const exportMutation = useMutation({
    mutationFn: (exportType) => createExport(studyId, { export_type: exportType, dataset_shape: shape }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['exports', studyId] }),
  });

  if (isLoadingProject) return <LoadingState label="Cargando..." />;
  if (!project) return <ProjectMissingState />;

  return (
    <div className="colmena-page">
      <PageHeader
        eyebrow="Exportaciones"
        title={project.name}
        description="Descarga el dataset del estudio en CSV, XLSX o JSON. Cada exportación queda registrada con fecha, forma y filtros para trazabilidad."
      />

      <Card>
        <StudySelector projectId={projectId} studyId={studyId} onStudyChange={setStudyId} />
      </Card>

      {!studyId ? (
        <Card>
          <EmptyState title="Elige una aplicación o estudio." description="Las exportaciones se generan por cada aplicación del instrumento." />
        </Card>
      ) : (
        <>
          <Card padding="compact">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 rounded-xl bg-turquoiseSoft p-2 text-turquoiseDark">
                  <ShieldCheck size={17} />
                </div>
                <div>
                  <p className="text-sm font-semibold text-dark">Dataset anonimizado</p>
                  <p className="mt-1 text-xs text-muted">No incluye identidad ni sesiones incompletas. Elige la forma y el formato.</p>
                </div>
              </div>
              <label className="flex flex-col gap-1.5">
                <span className="colmena-label">Forma del dataset</span>
                <select className="colmena-input h-9 px-3 text-xs" value={shape} onChange={(event) => setShape(event.target.value)}>
                  {SHAPES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {AVAILABLE_EXPORT_TYPES.map((type) => (
                <Button
                  key={type}
                  loading={exportMutation.isPending && exportMutation.variables === type}
                  onClick={() => exportMutation.mutate(type)}
                  size="sm"
                  type="button"
                  variant="secondary"
                >
                  <FileDown size={14} /> Exportar {type}
                </Button>
              ))}
              {PENDING_EXPORT_TYPES.map(({ type, label }) => (
                <span
                  key={type}
                  title="Formato definido en el backend, pendiente de implementación"
                  className="inline-flex h-8 shrink-0 cursor-not-allowed items-center gap-1.5 rounded-lg border border-dashed border-border px-3 text-xs font-semibold text-muted opacity-70"
                >
                  <FileDown size={14} /> {label} · pronto
                </span>
              ))}
            </div>
            {exportMutation.isError ? <p className="mt-2 text-xs font-medium text-danger">{exportMutation.error?.message}</p> : null}
          </Card>

          <Card padded={false}>
            <div className="border-b border-border px-4 py-3">
              <p className="text-sm font-semibold text-dark">Historial de exportaciones</p>
            </div>
            {downloadError ? <p role="alert" className="p-4 text-xs text-danger">{downloadError}</p> : null}
            {isLoadingExports ? (
              <div className="p-4">
                <LoadingState label="Cargando exportaciones..." />
              </div>
            ) : exports.length === 0 ? (
              <div className="p-4">
                <EmptyState title="Todavía no hay exportaciones" description="Genera la primera con los botones de arriba." />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-surfaceSoft text-xs uppercase text-muted">
                    <tr>
                      <th className="px-4 py-3">Tipo</th>
                      <th className="px-4 py-3">Forma</th>
                      <th className="px-4 py-3">Estado</th>
                      <th className="px-4 py-3">Filas</th>
                      <th className="px-4 py-3">Fecha</th>
                      <th className="px-4 py-3">Descarga</th>
                    </tr>
                  </thead>
                  <tbody>
                    {exports.map((exp) => (
                      <tr key={exp.id} className="border-t border-border">
                        <td className="px-4 py-3 font-semibold text-dark">{exp.export_type}</td>
                        <td className="px-4 py-3">{displayLabel(exp.dataset_shape)}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`colmena-badge ${
                              exp.status === 'COMPLETED'
                                ? 'bg-turquoise/10 text-turquoise'
                                : exp.status === 'FAILED'
                                  ? 'bg-danger/10 text-danger'
                                  : 'bg-amber/10 text-yellowDark'
                            }`}
                          >
                            {displayLabel(exp.status)}
                          </span>
                        </td>
                        <td className="px-4 py-3">{exp.row_count ?? '—'}</td>
                        <td className="px-4 py-3 text-xs text-muted">
                          {new Date(exp.created_at).toLocaleString('es-PE')}
                        </td>
                        <td className="px-4 py-3">
                          {exp.status === 'COMPLETED' ? (
                            <button
                              type="button"
                              onClick={async () => {
                                try {
                                  setDownloadError(null);
                                  await downloadProtectedFile(getExportDownloadUrl(exp.id), `aurora-export-${exp.id}.${exp.export_type.toLowerCase()}`);
                                } catch (error) {
                                  setDownloadError(error.message);
                                }
                              }}
                              className="colmena-badge inline-flex items-center gap-1 bg-amber/10 text-yellowDark hover:bg-amber/20"
                            >
                              <Download size={12} /> Descargar
                            </button>
                          ) : exp.status === 'FAILED' ? (
                            <span className="text-xs text-danger" title={exp.error_message || ''}>
                              Error
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
