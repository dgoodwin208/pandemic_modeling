import React from 'react';

// APR Logo based on brand guidelines
// Map grid with epidemic curve overlay
export default function APRLogo({ size = 'default', showText = true, className = '' }) {
  const sizes = {
    small: { icon: 32, text: 'text-lg' },
    default: { icon: 48, text: 'text-xl' },
    large: { icon: 64, text: 'text-2xl' },
  };

  const { icon, text } = sizes[size] || sizes.default;

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {/* Icon */}
      <svg
        width={icon}
        height={icon}
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="flex-shrink-0"
      >
        {/* Grid background - upper section (lighter) */}
        <rect x="4" y="4" width="56" height="24" fill="none" stroke="#1e3a5f" strokeWidth="1" opacity="0.3" />

        {/* Grid lines - upper */}
        <line x1="4" y1="12" x2="60" y2="12" stroke="#1e3a5f" strokeWidth="0.5" opacity="0.3" />
        <line x1="4" y1="20" x2="60" y2="20" stroke="#1e3a5f" strokeWidth="0.5" opacity="0.3" />
        <line x1="18" y1="4" x2="18" y2="28" stroke="#1e3a5f" strokeWidth="0.5" opacity="0.3" />
        <line x1="32" y1="4" x2="32" y2="28" stroke="#1e3a5f" strokeWidth="0.5" opacity="0.3" />
        <line x1="46" y1="4" x2="46" y2="28" stroke="#1e3a5f" strokeWidth="0.5" opacity="0.3" />

        {/* Map shapes - stylized blocks representing regions */}
        <rect x="4" y="28" width="14" height="12" fill="#1e3a5f" />
        <rect x="4" y="40" width="8" height="8" fill="#1e3a5f" />
        <rect x="12" y="44" width="10" height="16" fill="#1e3a5f" />
        <rect x="22" y="36" width="12" height="24" fill="#1e3a5f" />
        <rect x="34" y="40" width="10" height="20" fill="#1e3a5f" />
        <rect x="44" y="44" width="8" height="12" fill="#1e3a5f" />
        <rect x="52" y="48" width="8" height="8" fill="#1e3a5f" />
        <rect x="44" y="32" width="16" height="12" fill="#1e3a5f" />

        {/* Health facility markers */}
        <rect x="8" y="32" width="4" height="4" fill="#10b981" rx="0.5" />
        <rect x="26" y="42" width="4" height="4" fill="#ffffff" stroke="#10b981" strokeWidth="1" rx="0.5" />

        {/* Epidemic curve - the signature element */}
        <path
          d="M4 24 Q16 26, 24 20 Q32 14, 44 18 Q52 20, 60 12"
          stroke="#10b981"
          strokeWidth="3"
          fill="none"
          strokeLinecap="round"
        />

        {/* Data point at end of curve */}
        <circle cx="60" cy="12" r="4" fill="#1e3a5f" />
        <circle cx="60" cy="12" r="2.5" fill="#10b981" />
      </svg>

      {/* Text */}
      {showText && (
        <div className="flex flex-col">
          <span className={`font-medium text-slate-800 ${text} leading-tight`}>
            AI-Augmented
          </span>
          <span className={`font-medium text-slate-800 ${text} leading-tight`}>
            Pandemic Response
          </span>
        </div>
      )}
    </div>
  );
}

// Compact version with just "APR" text
export function APRLogoCompact({ size = 32, className = '' }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="flex-shrink-0"
      >
        {/* Simplified icon for compact use */}
        <rect x="4" y="28" width="14" height="12" fill="#1e3a5f" />
        <rect x="4" y="40" width="8" height="8" fill="#1e3a5f" />
        <rect x="12" y="44" width="10" height="16" fill="#1e3a5f" />
        <rect x="22" y="36" width="12" height="24" fill="#1e3a5f" />
        <rect x="34" y="40" width="10" height="20" fill="#1e3a5f" />
        <rect x="44" y="44" width="8" height="12" fill="#1e3a5f" />
        <rect x="52" y="48" width="8" height="8" fill="#1e3a5f" />
        <rect x="44" y="32" width="16" height="12" fill="#1e3a5f" />

        <rect x="8" y="32" width="4" height="4" fill="#10b981" rx="0.5" />
        <rect x="26" y="42" width="4" height="4" fill="#ffffff" stroke="#10b981" strokeWidth="1" rx="0.5" />

        <path
          d="M4 24 Q16 26, 24 20 Q32 14, 44 18 Q52 20, 60 12"
          stroke="#10b981"
          strokeWidth="3"
          fill="none"
          strokeLinecap="round"
        />

        <circle cx="60" cy="12" r="4" fill="#1e3a5f" />
        <circle cx="60" cy="12" r="2.5" fill="#10b981" />
      </svg>
      <span className="font-medium text-slate-800 text-lg">APR</span>
    </div>
  );
}
