import { useId } from 'react';
import { cn } from '../utils/cn.js';

/** AURORA Professional: ondas boreales, un isotipo coherente con el manual v1.0. */
export function BrandMark({ className, decorative = false }) {
  const uid = useId().replace(/:/g, '');
  const g1 = 'aurora-wave-1-' + uid;
  const g2 = 'aurora-wave-2-' + uid;
  const g3 = 'aurora-wave-3-' + uid;
  return (
    <svg
      role={decorative ? 'presentation' : 'img'}
      aria-hidden={decorative ? true : undefined}
      aria-label={decorative ? undefined : 'AURORA Professional, ondas de luz boreal'}
      className={cn('shrink-0', className)}
      viewBox="0 0 200 150"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id={g1} x1="0%" y1="35%" x2="100%" y2="80%">
          <stop offset="0%" stopColor="#00D4D8" />
          <stop offset="48%" stopColor="#19B9F0" />
          <stop offset="100%" stopColor="#6366F1" />
        </linearGradient>
        <linearGradient id={g2} x1="0%" y1="50%" x2="100%" y2="70%">
          <stop offset="0%" stopColor="#14DAD3" />
          <stop offset="58%" stopColor="#257DEA" />
          <stop offset="100%" stopColor="#7566FC" />
        </linearGradient>
        <linearGradient id={g3} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#05D1D9" />
          <stop offset="65%" stopColor="#2477E5" />
          <stop offset="100%" stopColor="#5156E7" />
        </linearGradient>
      </defs>
      <path d="M15 88C44 22 111 10 180 73C139 46 78 39 36 91C91 49 127 54 160 80C111 65 79 67 55 94" fill={'url(#' + g1 + ')'} />
      <path d="M37 103C70 52 120 58 159 95C122 76 88 79 65 106Z" fill={'url(#' + g2 + ')'} opacity="0.97" />
      <path d="M64 117C92 80 124 88 153 112C123 101 98 101 85 121Z" fill={'url(#' + g3 + ')'} opacity="0.96" />
    </svg>
  );
}
