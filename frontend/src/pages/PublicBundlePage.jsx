import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { CheckCircle2, ShieldCheck, Layers3 } from 'lucide-react';
import { getPublicEvaluationBundle } from '../api/evaluationBundles.js';
import PublicSurveyPage from './PublicSurveyPage.jsx';
import { BrandLogo } from '../brand/BrandLogo.jsx';

/** Un enlace y una experiencia continua. Las sesiones de cada estudio siguen aisladas. */
export default function PublicBundlePage() {
  const { publicId } = useParams();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [flowError, setFlowError] = useState('');
  const query = useQuery({
    queryKey: ['public-evaluation-bundle', publicId],
    queryFn: () => getPublicEvaluationBundle(publicId),
    retry: false,
    refetchOnWindowFocus: false,
  });
  const evaluations = Array.isArray(query.data?.evaluations) ? query.data.evaluations : [];
  const current = evaluations[currentIndex];
  const finished = Boolean(evaluations.length && currentIndex >= evaluations.length);

  const advance = async () => {
    // Comprobar nuevamente que el enlace no fue revocado o cerrado mientras
    // el participante respondía. No guardar una identidad común entre estudios.
    const refreshed = await query.refetch();
    const refreshedItems = refreshed.data?.evaluations;
    if (refreshed.isError || !Array.isArray(refreshedItems) ||
      refreshedItems.length !== evaluations.length ||
      refreshedItems.some((row, i) => row.id !== evaluations[i].id)) {
      setFlowError('La batería ya no está disponible. Las respuestas enviadas permanecen registradas.');
      return;
    }
    setCurrentIndex((i) => i + 1);
  };

  return (
    <main className="min-h-screen bg-[#F8FAFC] text-[#0A1F44]">
      <div className="mx-auto max-w-5xl space-y-3 px-3 py-4 sm:px-5">
        <header className="rounded-xl border border-[#DBE8F0] bg-white px-4 py-3 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <BrandLogo />
            {evaluations.length > 0 && <span className="rounded-lg bg-[#EEF7FB] px-3 py-2 text-xs font-bold text-[#246293]">
              {finished ? 'Evaluación completada' : 'Instrumento ' + (currentIndex + 1) + ' de ' + evaluations.length}
            </span>}
          </div>
          <h1 className="mt-2 text-lg font-extrabold">{query.data?.title || 'Batería de evaluaciones'}</h1>
          {evaluations.length > 0 && <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#E3EBF5]"
            role="progressbar" aria-label="Progreso de instrumentos completados"
            aria-valuenow={Math.min(evaluations.length, currentIndex)} aria-valuemin={0} aria-valuemax={evaluations.length}>
            <div className="h-full rounded-full bg-gradient-to-r from-[#00B4CD] to-[#6366F1]"
              style={{width: (Math.min(evaluations.length,currentIndex) / evaluations.length * 100) + '%'}} />
          </div>}
        </header>
        {query.isLoading && <p role="status" className="rounded-xl bg-white p-6">Preparando los instrumentos autorizados…</p>}
        {query.isError && !flowError && <p role="alert" className="rounded-xl border border-red-200 bg-white p-6 text-red-700">
          La batería no está disponible. Confirma que el enlace sigue vigente.
        </p>}
        {flowError && <p role="alert" className="rounded-xl border border-red-200 bg-white p-5 text-red-700">{flowError}</p>}
        {finished && !flowError && <section className="rounded-xl border border-[#C8EEE1] bg-white p-8 text-center shadow-sm">
          <CheckCircle2 size={36} className="mx-auto text-[#10B981]"/>
          <h2 className="mt-3 text-xl font-extrabold">Has completado la batería</h2>
          <p className="mt-2 text-sm text-[#64748B]">Gracias. Cada cuestionario fue registrado bajo sus propias reglas de confidencialidad.</p>
        </section>}
        {current && !flowError && <section aria-label={'Cuestionario ' + (currentIndex + 1)}>
          <PublicSurveyPage key={current.survey_public_id} publicIdOverride={current.survey_public_id}
            batteryContext={(currentIndex + 1) + '/' + evaluations.length + ' · ' + current.instrument_name}
            onCompleted={advance}/>
        </section>}
        <footer className="flex items-center gap-2 px-2 pb-4 text-xs text-[#64748B]">
          <ShieldCheck size={15}/> Sesiones anónimas independientes. No se comparte un identificador de trabajador entre instrumentos.
          <Layers3 size={13} aria-hidden="true"/>
        </footer>
      </div>
    </main>
  );
}
