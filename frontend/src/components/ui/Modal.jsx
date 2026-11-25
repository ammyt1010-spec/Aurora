import { useEffect, useId } from 'react';
import { Hexagon, X } from 'lucide-react';

import { cn } from '../../utils/cn.js';

const SIZES = {
  md: 'max-w-[580px]',
  lg: 'max-w-[680px]',
  xl: 'max-w-4xl',
};

/**
 * Diálogo centrado (reemplaza los drawers laterales angostos que teníamos
 * antes) — fondo con blur, tarjeta amplia con header fijo, cuerpo scrollable
 * y footer de acciones pegado abajo, siguiendo el sistema de diseño nuevo
 * (colmena-card, tokens ámbar).
 */
export function Modal({
  title,
  subtitle,
  icon: Icon = Hexagon,
  onClose,
  size = 'lg',
  children,
  footer,
  preventClose = false,
  closeOnBackdrop = true,
}) {
  const titleId = useId();
  const subtitleId = useId();

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && !preventClose) onClose?.();
    };
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose, preventClose]);

  const handleBackdropClick = (event) => {
    if (event.target === event.currentTarget && closeOnBackdrop && !preventClose) onClose?.();
  };

  return (
    <div
      className="animate-colmena-overlay-in fixed inset-0 z-[60] flex items-center justify-center bg-[#1C1F24]/40 px-3 py-4 backdrop-blur-sm"
      onMouseDown={handleBackdropClick}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={subtitle ? subtitleId : undefined}
        className={cn(
          'colmena-card colmena-modal animate-colmena-modal-in flex max-h-[88vh] w-full flex-col overflow-hidden bg-white shadow-glass',
          SIZES[size],
        )}
      >
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="flex min-w-0 items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber/10 text-amber">
              <Icon size={20} strokeWidth={2} />
            </div>
            <div className="min-w-0 pt-0.5">
              <h2 id={titleId} className="text-[17px] font-bold leading-5 text-dark">{title}</h2>
              {subtitle ? <p id={subtitleId} className="mt-1 text-xs leading-4 text-muted">{subtitle}</p> : null}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={preventClose}
            aria-label="Cerrar modal"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-white text-muted transition hover:bg-[#f5f6f8] hover:text-dark"
          >
            <X size={15} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5 sm:px-6">{children}</div>

        {footer ? <div className="flex shrink-0 justify-end gap-3 border-t border-border bg-surfaceSoft px-5 py-4 sm:px-6">{footer}</div> : null}
      </div>
    </div>
  );
}

export default Modal;
