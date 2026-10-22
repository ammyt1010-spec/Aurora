import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { ClipboardCheck, ExternalLink, ShieldCheck, Layers3 } from 'lucide-react';
import { getPublicEvaluationBundle } from '../api/evaluationBundles.js';

export default function PublicBundlePage() {
  const { publicId } = useParams();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['public-evaluation-bundle', publicId],
    queryFn: () => getPublicEvaluationBundle(publicId),
    retry: false,
  });

  return (
    <main className="min-h-screen bg-[#f4f7fd] px-4 py-10 text-[#182b48]">
      <div className="mx-auto max-w-3xl space-y-6">
        <header className="overflow-hidden rounded-2xl bg-gradient-to-br from-[#14284b] to-[#25447c] px-6 py-7 text-white shadow-xl">
          <div className="mb-3 flex items-center gap-2 text-xs font-bold tracking-widest text-[#a9f4e6]">
            <Layers3 size={16} /> AURORA PROFESSIONAL
          </div>
          <h1 className="text-2xl font-extrabold">Batería de evaluaciones</h1>
          <p className="mt-2 text-sm text-[#d2e0f4]">Completa los instrumentos disponibles de forma individual y confidencial.</p>
        </header>
        {isLoading && <p role="status" className="rounded-xl bg-white p-5 text-sm">Verificando disponibilidad de instrumentos…</p>}
        {isError && <div role="alert" className="rounded-xl border border-red-200 bg-white p-5 text-sm">
          Este enlace no está disponible o alguno de sus estudios ya no admite respuestas.
        </div>}
        {data && (
          <>
            <div className="rounded-xl border border-[#dce4f2] bg-white p-4 shadow-sm">
              <h2 className="font-bold">{data.title}</h2>
              <p className="mt-1 text-xs text-[#66758c]">
                Cada encuesta se completa por separado. AURORA no une identidades de trabajadores entre instrumentos,
                ni revela resultados individuales a la empresa.
              </p>
            </div>
            <ol className="grid gap-3">
              {data.evaluations.map((item, index) => (
                <li key={item.id} className="flex flex-wrap items-center gap-4 rounded-xl border border-[#dce4f2] bg-white p-4 shadow-md">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#edf2ff] text-sm font-extrabold text-[#3654a9]">
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <h3 className="font-semibold">{item.name}</h3>
                    <p className="text-xs text-[#66758c]">{item.instrument_name}</p>
                  </div>
                  <a className="inline-flex items-center gap-2 rounded-lg bg-[#233f75] px-4 py-2.5 text-xs font-bold text-white hover:bg-[#315ba5]"
                    href={`/encuesta/${item.survey_public_id}`} target="_blank" rel="noreferrer">
                    <ClipboardCheck size={15} /> Responder <ExternalLink size={13}/>
                  </a>
                </li>
              ))}
            </ol>
            <p className="flex items-start gap-2 px-2 text-xs leading-6 text-[#66758c]">
              <ShieldCheck className="mt-1 shrink-0" size={15}/>
              Los enlaces de los instrumentos siguen sus propios permisos, fechas y reglas de aplicación.
              Si ya completaste una evaluación, no la respondas nuevamente.
            </p>
          </>
        )}
      </div>
    </main>
  );
}
