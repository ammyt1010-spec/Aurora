import { useState } from 'react';
import { Upload, Sparkles, CheckCircle2, AlertCircle, X } from 'lucide-react';
import { Button } from '../../ui/Button.jsx';

const PREBUILT_TEMPLATES = [
  {
    code: 'MBI_BURNOUT',
    name: 'Inventario de Burnout de Maslach (MBI)',
    description: 'Mide Agotamiento Emocional, Despersonalización y Realización Personal en el trabajo.',
    questions: 22,
    dimensions: 3,
    population: 'Todo tipo de personal',
  },
  {
    code: 'ERGO_CLIMATE',
    name: 'Cuestionario de Clima y Riesgo Ergonómico',
    description: 'Mide carga física, posturas forzadas y fatiga osteomuscular percibida por puesto.',
    questions: 18,
    dimensions: 4,
    population: 'Personal operativo y de planta',
  },
  {
    code: 'WORK_SATISFACTION',
    name: 'Escala de Satisfacción Laboral y Clima Empresarial',
    description: 'Mide ambiente laboral, liderazgo, reconocimiento y equidad organizacional.',
    questions: 25,
    dimensions: 5,
    population: 'Toda la empresa',
  },
];

export default function CustomInstrumentModal({ isOpen, onClose, onImportSuccess }) {
  const [activeTab, setActiveTab] = useState('templates');
  const [jsonContent, setJsonContent] = useState('');
  const [statusMessage, setStatusMessage] = useState(null);

  if (!isOpen) return null;

  const handleImportJson = () => {
    try {
      if (!jsonContent.trim()) {
        setStatusMessage({ type: 'error', text: 'Ingresa o carga un JSON de manifiesto válido.' });
        return;
      }
      const parsed = JSON.parse(jsonContent);
      if (!parsed.instrument || !parsed.questions) {
        setStatusMessage({
          type: 'error',
          text: 'El JSON debe contener las claves "instrument" y "questions".',
        });
        return;
      }
      setStatusMessage({
        type: 'success',
        text: `Instrumento "${parsed.instrument.name || 'Personalizado'}" validado e importado correctamente.`,
      });
      setTimeout(() => {
        if (onImportSuccess) onImportSuccess(parsed);
        onClose();
      }, 1200);
    } catch (err) {
      setStatusMessage({ type: 'error', text: 'JSON inválido: ' + err.message });
    }
  };

  const handleSelectTemplate = (tmpl) => {
    setStatusMessage({
      type: 'success',
      text: `Plantilla "${tmpl.name}" vinculada correctamente al proyecto.`,
    });
    setTimeout(() => {
      if (onImportSuccess) onImportSuccess(tmpl);
      onClose();
    }, 1200);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-2xl rounded-2xl border border-white/10 bg-slate-900 p-6 text-white shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white transition-colors"
        >
          <X size={20} />
        </button>

        <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/20 text-amber-400">
            <Sparkles size={20} />
          </div>
          <div>
            <h3 className="text-lg font-bold">Motor Extensible de Instrumentos</h3>
            <p className="text-xs text-slate-400">
              Adapta o integra nuevos cuestionarios de riesgos, burnout o factores ergonómicos.
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="mt-4 flex gap-2 border-b border-slate-800 pb-2">
          <button
            onClick={() => setActiveTab('templates')}
            className={`px-4 py-2 text-xs font-semibold rounded-lg transition-colors ${
              activeTab === 'templates'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                : 'text-slate-400 hover:bg-slate-800'
            }`}
          >
            Plantillas Prediseñadas
          </button>
          <button
            onClick={() => setActiveTab('json')}
            className={`px-4 py-2 text-xs font-semibold rounded-lg transition-colors ${
              activeTab === 'json'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                : 'text-slate-400 hover:bg-slate-800'
            }`}
          >
            Importar Manifiesto JSON
          </button>
        </div>

        {/* Tab Content */}
        <div className="mt-4">
          {activeTab === 'templates' ? (
            <div className="space-y-3">
              <p className="text-xs text-slate-400">
                Selecciona una plantilla adicional para medir otros factores relevantes según el puesto:
              </p>
              <div className="grid gap-3 sm:grid-cols-1">
                {PREBUILT_TEMPLATES.map((tmpl) => (
                  <div
                    key={tmpl.code}
                    onClick={() => handleSelectTemplate(tmpl)}
                    className="group cursor-pointer rounded-xl border border-slate-800 bg-slate-800/50 p-4 transition-all hover:border-amber-500/50 hover:bg-slate-800"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <span className="text-xs font-bold text-amber-400">{tmpl.code}</span>
                        <h4 className="font-semibold text-white group-hover:text-amber-300">
                          {tmpl.name}
                        </h4>
                        <p className="mt-1 text-xs text-slate-300">{tmpl.description}</p>
                      </div>
                      <span className="rounded-md bg-slate-700 px-2 py-1 text-[10px] text-slate-300">
                        {tmpl.population}
                      </span>
                    </div>
                    <div className="mt-3 flex items-center gap-4 text-[11px] text-slate-400">
                      <span>{tmpl.questions} Preguntas</span>
                      <span>•</span>
                      <span>{tmpl.dimensions} Dimensiones</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-xs text-slate-400">
                Pega la estructura JSON del nuevo instrumento con sus preguntas, opciones y baremos:
              </p>
              <textarea
                value={jsonContent}
                onChange={(e) => setJsonContent(e.target.value)}
                placeholder='{\n  "instrument": { "code": "MI_FACTOR", "name": "Factor Específico" },\n  "questions": [...]\n}'
                className="w-full h-44 rounded-xl border border-slate-700 bg-slate-950 p-3 font-mono text-xs text-emerald-400 placeholder-slate-600 focus:border-amber-500 focus:outline-none"
              />
              <div className="flex justify-end gap-2">
                <Button variant="secondary" size="sm" onClick={onClose}>
                  Cancelar
                </Button>
                <Button size="sm" onClick={handleImportJson}>
                  <Upload size={14} className="mr-1.5" /> Importar Manifiesto
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Status Feedback */}
        {statusMessage ? (
          <div
            className={`mt-4 flex items-center gap-2 rounded-xl p-3 text-xs ${
              statusMessage.type === 'success'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
            }`}
          >
            {statusMessage.type === 'success' ? (
              <CheckCircle2 size={16} />
            ) : (
              <AlertCircle size={16} />
            )}
            <span>{statusMessage.text}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
