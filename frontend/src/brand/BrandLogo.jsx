import { BrandMark } from './BrandMark.jsx';
import { cn } from '../utils/cn.js';

export function BrandLogo({ className, compact = false }) {
  if (compact) {
    return <BrandMark className={cn('h-8 w-8', className)} />;
  }

  return (
    <div className={cn('flex h-[36px] items-center gap-2.5 overflow-visible', className)}>
      <BrandMark className="h-[34px] w-[34px] shrink-0" />
      <div className="flex flex-col justify-center">
        <div className="flex items-center gap-1.5 leading-none">
          <span className="text-[17px] font-black tracking-[0.12em] text-slate-900 dark:text-white">
            AURORA
          </span>
          <span className="rounded-md bg-gradient-to-r from-aurora-500 to-cyan-500 px-1.5 py-0.5 text-[9px] font-black tracking-widest text-white uppercase shadow-sm">
            PRO
          </span>
        </div>
        <span className="mt-0.5 text-[9px] font-semibold tracking-wider text-slate-500 dark:text-slate-400 uppercase">
          RIESGOS PSICOSOCIALES
        </span>
      </div>
    </div>
  );
}
