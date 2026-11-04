import { cn } from '../../utils/cn.js';

/**
 * Botón con las 3 líneas de colores de la "E" de COLMENA.
 * Se usa como control para contraer/expandir el sidebar.
 */
export function ColmenaMenuButton({ onClick, title = 'Menú', className, ariaExpanded }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      aria-expanded={ariaExpanded}
      aria-controls="aurora-sidebar"
      className={cn(
        'group inline-flex items-center justify-center transition-transform hover:scale-105 active:scale-95',
        className,
      )}
    >
      <span className="flex flex-col gap-[3px]">
        <span className="block h-[3px] w-[18px] rounded-full bg-[#F5B21A]" />
        <span className="block h-[3px] w-[18px] rounded-full bg-[#FF6A2A]" />
        <span className="block h-[3px] w-[18px] rounded-full bg-[#11B7B2]" />
      </span>
    </button>
  );
}

export default ColmenaMenuButton;
