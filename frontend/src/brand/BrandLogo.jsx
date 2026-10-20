import { BrandMark } from './BrandMark.jsx';
import { cn } from '../utils/cn.js';

export function BrandLogo({ className, compact = false, inverted = false }) {
  if (compact) {
    return <BrandMark className={cn('h-9 w-8', className)} />;
  }

  return (
    <div className={cn('flex items-center gap-2.5 overflow-visible', className)}>
      <BrandMark className="h-10 w-9 shrink-0" />
      <div className="flex min-w-0 flex-col justify-center">
        <div className="flex items-center gap-2 leading-none">
          <span className={cn('text-[18px] font-black tracking-[0.16em]', inverted ? 'text-white' : 'text-slate-950 dark:text-white')}>
            AURORA
          </span>
          <span className="rounded-full border border-violet-300/40 bg-violet-500/10 px-2 py-1 text-[8px] font-black tracking-[0.16em] text-violet-600 uppercase dark:text-violet-300">
            Intelligence
          </span>
        </div>
        <span className={cn('mt-1 text-[8px] font-bold tracking-[0.18em] uppercase', inverted ? 'text-white/55' : 'text-slate-500 dark:text-slate-400')}>
          Riesgos psicosociales
        </span>
      </div>
    </div>
  );
}
