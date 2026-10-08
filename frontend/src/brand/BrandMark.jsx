import { cn } from '../utils/cn.js';

export function BrandMark({ className }) {
  return (
    <svg
      aria-label="Aurora Pro"
      className={cn('shrink-0', className)}
      viewBox="0 0 100 100"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id="aurora-shield-grad1" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#818cf8" />
          <stop offset="50%" stopColor="#4f46e5" />
          <stop offset="100%" stopColor="#06b6d4" />
        </linearGradient>
        <linearGradient id="aurora-shield-grad2" x1="100%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#6366f1" />
          <stop offset="100%" stopColor="#2dd4bf" />
        </linearGradient>
        <filter id="aurora-shield-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>
      
      <polygon
        points="50,5 90,25 90,75 50,95 10,75 10,25"
        fill="url(#aurora-shield-grad1)"
        rx="8"
        filter="url(#aurora-shield-glow)"
      />
      
      <polygon points="50,14 82,30 82,70 50,86 18,70 18,30" fill="#1e1b4b" />
      
      <path
        d="M 30,65 C 40,45 60,75 70,35 C 70,55 55,75 30,65 Z"
        fill="url(#aurora-shield-grad2)"
        opacity="0.95"
      />
      <circle cx="50" cy="50" r="8" fill="#a4b8fc" />
    </svg>
  );
}
