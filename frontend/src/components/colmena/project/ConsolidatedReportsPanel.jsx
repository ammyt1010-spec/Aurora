import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, FileCheck2, Layers3, ShieldCheck } from 'lucide-react';

import {
  listEvaluationBundles, listConsolidatedBundleReports,
  createConsolidatedBundleReport, consolidatedPdfUrl,
} from '../../../api/evaluationBundles.js';
import { downloadProtectedFile } from '../../../api/protectedFiles.js';

/** Emisión documental: cada fuente debe estar pagada y preservar su hash. */
export default function ConsolidatedReportsPanel({ projectId }) {
  const queryClient = useQueryClient();
  const [bundleId, setBundleId] = useState('');
  const [downloadError, setDownloadError] = useState('');
  const bundlesQuery = useQuery({
    queryKey: ['evaluation-bundles', projectId],
    queryFn: () => listEvaluationBundles(projectId),
    enabled: Boolean(projectId),
    retry: false,
  });
  const bundles = bundlesQuery.data || [];

  useEffect(() => {
    if (!bundles.length) { setBundleId(''); return; }
    if (!bundles.some((row) => String(row.id) === String(bundleId))) {
      setBundleId(String(bundles[0].id));
    }
  }, [bundles, bundleId]);

  const selected = bundles.find((row) => String(row.id) === String(bundleId));
  const history = useQuery({
    queryKey: ['consolidated-bundle-reports', projectId, bundleId],
    queryFn: () => listConsolidatedBundleReports(projectId, bundleId),
    enabled: Boolean(projectId && bundleId),
    retry: false,
  });
  const create = useMutation({
    mutationFn: () => createConsolidatedBundleReport(projectId, bundleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['consolidated-bundle-reports', projectId, bundleId] });
    },
  });

  if (!bundlesQuery.isLoading && !bundles.length && !bundlesQuery.isError) return null;

  return (
    <section aria-label="Consolidación multiinstrumento" className="rounded-2xl border border-[#dbe5f4] bg-gradient-to-br from-white to-[#f7f9ff] p-4 shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-[#243e72]">
          <Layers3 size={20}/><h2 className="text-sm font-extrabold">Informe consolidado multiinstrumento</h2>
        </div>
        <span className="rounded-lg border border-[#d9e2f2] bg-white px-2.5 py-1 text-[11px] font-bold text-[#57708f]">
          Originales autorizados
        </span>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted">
        Combina informes PDF individuales previamente emitidos y pagados, con secciones independientes por metodología,
        marcadores de navegación y comprobación de integridad. No permite consolidar muestras gratuitas.
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="flex min-w-[220px] flex-1 flex-col gap-1 text-xs font-semibold text-dark">
          Batería empresarial
          <select className="colmena-input" value={bundleId}
            onChange={(e) => setBundleId(e.target.value)}>
            <option value="">Selecciona una batería</option>
            {bundles.map((bundle) => <option key={bundle.id} value={bundle.id}>
              {bundle.label} · {bundle.study_ids.length} instrumentos
            </option>)}
          </select>
        </label>
        <button type="button" disabled={!selected || selected.status !== 'PUBLISHED' || create.isPending}
          onClick={() => create.mutate()}
          className="inline-flex min-h-[40px] items-center gap-2 rounded-xl bg-[#234677] px-4 py-2.5 text-xs font-bold text-white shadow-md hover:bg-[#315f9e] disabled:opacity-40">
          <FileCheck2 size={15}/>{create.isPending ? 'Consolidando…' : 'Generar PDF consolidado'}
        </button>
      </div>
      {bundlesQuery.isError && <p role="alert" className="mt-2 text-xs text-danger">No se pudieron consultar las baterías de la empresa.</p>}
      {create.isError && <p role="alert" className="mt-2 text-xs text-danger">
        {create.error?.message || 'Los informes de todos los instrumentos deben estar emitidos y pagados.'}
      </p>}
      {history.isError && <p role="alert" className="mt-2 text-xs text-danger">No se pudo consultar el historial de consolidados.</p>}
      {(history.data || []).length > 0 && (
        <div className="mt-3 grid gap-2">
          {history.data.map((report) => (
            <div key={report.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-[#e0e8f5] bg-white px-3 py-2.5 shadow-sm">
              <ShieldCheck size={17} className="text-[#20a98c]"/>
              <div className="min-w-0 flex-1">
                <strong className="block text-xs text-dark">Consolidado #{report.id}</strong>
                <span className="text-[11px] text-muted">
                  {report.manifest?.reports?.length || 0} informes · {new Date(report.created_at).toLocaleDateString('es-PE')}
                </span>
              </div>
              <button type="button" className="inline-flex items-center gap-1.5 rounded-lg border border-[#c7d7ef] px-3 py-2 text-xs font-bold text-[#254680] hover:bg-[#edf2ff]"
                onClick={async () => {
                  setDownloadError('');
                  try {
                    await downloadProtectedFile(consolidatedPdfUrl(report.id), `aurora-consolidado-${report.id}.pdf`);
                  } catch (error) { setDownloadError(error.message || 'No fue posible descargar el archivo.'); }
                }}>
                <Download size={14}/> Descargar
              </button>
            </div>
          ))}
        </div>
      )}
      {downloadError && <p role="alert" className="mt-2 text-xs text-danger">{downloadError}</p>}
      <p className="mt-3 text-[11px] text-muted">
        Esta compilación documental no sustituye los archivos originales ni constituye una firma o certificación oficial adicional.
      </p>
    </section>
  );
}
