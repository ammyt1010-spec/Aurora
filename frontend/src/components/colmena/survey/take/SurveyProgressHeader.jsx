import { ListFilter, Square } from 'lucide-react';
import { BrandMark } from '../../../../brand/BrandMark.jsx';

export default function SurveyProgressHeader({ studyName, answered, total, viewMode, onToggleViewMode }) {
  const pct = total > 0 ? Math.round((answered / total) * 100) : 0;

  return (
    <div className="survey-header">
      <div className="survey-header-inner">
        <div className="survey-header-row">
          <div className="survey-header-brand">
            <BrandMark className="h-4 w-4" />
            <span>{studyName}</span>
          </div>
          <div className="flex items-center gap-3">
            {onToggleViewMode && (
              <button
                type="button"
                onClick={onToggleViewMode}
                className="hidden sm:inline-flex items-center gap-1.5 px-2 py-1 rounded-md border border-border text-[11px] font-medium text-muted hover:text-dark hover:bg-slate-100 transition"
                title="Cambiar modo de visualización"
              >
                {viewMode === 'all' ? (
                  <>
                    <Square size={12} />
                    <span>Ver 1 por 1</span>
                  </>
                ) : (
                  <>
                    <ListFilter size={12} />
                    <span>Ver lista completa</span>
                  </>
                )}
              </button>
            )}
            <span className="survey-label">
              {answered} / {total} respondidas
            </span>
          </div>
        </div>
        <div className="survey-progress-track">
          <div className="survey-progress-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  );
}
