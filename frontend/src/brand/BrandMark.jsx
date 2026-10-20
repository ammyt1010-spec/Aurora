import { useId } from 'react';

import { cn } from '../utils/cn.js';

export function BrandMark({ className, title = 'Aurora' }) {
  const rawId = useId();
  const id = rawId.replace(/:/g, '');

  return (
    <svg
      aria-label={title}
      className={cn('shrink-0 overflow-visible', className)}
      viewBox="0 0 72 82"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
    >
      <defs>
        <linearGradient id={`${id}-flame`} x1="12" y1="70" x2="60" y2="10" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#12B8B0" />
          <stop offset="0.32" stopColor="#5B7CFA" />
          <stop offset="0.63" stopColor="#A855F7" />
          <stop offset="0.82" stopColor="#FF5F6D" />
          <stop offset="1" stopColor="#FFB423" />
        </linearGradient>
        <linearGradient id={`${id}-core`} x1="28" y1="66" x2="45" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="#F8FAFC" />
          <stop offset="0.5" stopColor="#DFFBFF" />
          <stop offset="1" stopColor="#FFF4D6" />
        </linearGradient>
        <filter id={`${id}-glow`} x="-45%" y="-35%" width="190%" height="190%">
          <feGaussianBlur stdDeviation="4.5" result="blur" />
          <feColorMatrix
            in="blur"
            type="matrix"
            values="1 0 0 0 0.28  0 1 0 0 0.25  0 0 1 0 0.95  0 0 0 .32 0"
          />
        </filter>
      </defs>

      <path
        d="M37 5C39 18 31 22 26 30c-3 5-4 10-2 15-7-4-9-11-7-20C7 34 3 45 6 57c4 15 16 22 30 22 17 0 29-11 30-27 1-13-6-26-19-35 1 9-3 15-8 18 2-10 1-20-2-30Z"
        fill={`url(#${id}-flame)`}
        filter={`url(#${id}-glow)`}
        opacity="0.5"
      />
      <path
        d="M37 5C39 18 31 22 26 30c-3 5-4 10-2 15-7-4-9-11-7-20C7 34 3 45 6 57c4 15 16 22 30 22 17 0 29-11 30-27 1-13-6-26-19-35 1 9-3 15-8 18 2-10 1-20-2-30Z"
        fill={`url(#${id}-flame)`}
      />
      <path
        d="M38 34c1 8-6 12-8 19-2 8 2 15 9 18 9-2 14-9 13-17-1-7-6-13-11-17 0 5-2 8-5 10 1-5 1-9 2-13Z"
        fill={`url(#${id}-core)`}
        opacity="0.94"
      />
      <circle cx="19" cy="57" r="2.4" fill="#72F1E8" opacity="0.9" />
      <circle cx="54" cy="48" r="2" fill="#FFD36A" opacity="0.9" />
    </svg>
  );
}
