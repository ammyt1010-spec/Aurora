import { BrandMark } from './BrandMark.jsx';
import { cn } from '../utils/cn.js';

/** Logotipo maestro: nombre y subtítulo nunca deben confundirse con un instrumento concreto. */
export function BrandLogo({ className, compact = false }) {
  if (compact) return <BrandMark className={cn('h-8 w-8', className)} />;
  return (
    <div className={cn('flex min-h-[42px] items-center gap-2.5', className)}
      aria-label="AURORA Professional">
      <BrandMark className="h-[43px] w-[48px] shrink-0" decorative />
      <div className="flex flex-col justify-center">
        <span className="text-[18px] font-extrabold leading-none tracking-[0.12em] text-[#0A1F44]">AURORA</span>
        <span className="mt-[4px] text-[10px] font-medium leading-none tracking-[0.18em] text-[#64748B]">Professional</span>
      </div>
    </div>
  );
}
