import React from 'react';

type DefectVariant = 'longitudinal' | 'transverse' | 'alligator' | 'pothole' | 'unknown';

function classifyDefect(className: string): DefectVariant {
  const lower = className.toLowerCase();
  if (/longitudinal|diagonal|linear|crack/.test(lower)) return 'longitudinal';
  if (/transverse|horizontal|cross/.test(lower)) return 'transverse';
  if (/alligator|mesh|fatigue|map|block/.test(lower)) return 'alligator';
  if (/pothole|hole|depression|pit/.test(lower)) return 'pothole';
  return 'unknown';
}

interface DefectIconProps {
  className: string;
  /** Icon size in px. Default: 20. */
  size?: number;
  /** Stroke/fill color class or CSS value. Default: currentColor. */
  color?: string;
  /** Optional extra className for the wrapper span. */
  wrapClass?: string;
}

export default function DefectIcon({
  className,
  size = 20,
  wrapClass = '',
}: DefectIconProps) {
  const variant = classifyDefect(className);
  const s = size;
  const mid = s / 2;
  const stroke = 'currentColor';

  const icons: Record<DefectVariant, React.ReactNode> = {
    /** Longitudinal / diagonal crack — a single diagonal line */
    longitudinal: (
      <svg width={s} height={s} viewBox={`0 0 ${s} ${s}`} fill="none" aria-label="Longitudinal crack">
        <line x1={s * 0.15} y1={s * 0.15} x2={s * 0.85} y2={s * 0.85}
              stroke={stroke} strokeWidth={1.8} strokeLinecap="round" />
      </svg>
    ),

    /** Transverse crack — horizontal line */
    transverse: (
      <svg width={s} height={s} viewBox={`0 0 ${s} ${s}`} fill="none" aria-label="Transverse crack">
        <line x1={s * 0.1} y1={mid} x2={s * 0.9} y2={mid}
              stroke={stroke} strokeWidth={1.8} strokeLinecap="round" />
      </svg>
    ),

    /** Alligator / mesh cracking — crosshatch pattern */
    alligator: (
      <svg width={s} height={s} viewBox={`0 0 ${s} ${s}`} fill="none" aria-label="Alligator cracking">
        {[0.25, 0.5, 0.75].map((t) => (
          <React.Fragment key={`h${t}`}>
            <line x1={s * 0.1} y1={s * t} x2={s * 0.9} y2={s * t}
                  stroke={stroke} strokeWidth={1.2} strokeLinecap="round" />
            <line x1={s * t} y1={s * 0.1} x2={s * t} y2={s * 0.9}
                  stroke={stroke} strokeWidth={1.2} strokeLinecap="round" />
          </React.Fragment>
        ))}
      </svg>
    ),

    /** Pothole — solid circle */
    pothole: (
      <svg width={s} height={s} viewBox={`0 0 ${s} ${s}`} fill="none" aria-label="Pothole">
        <circle cx={mid} cy={mid} r={s * 0.32} fill={stroke} />
      </svg>
    ),

    /** Unknown / unrecognised class — dashed bounding-box + question mark */
    unknown: (
      <svg width={s} height={s} viewBox={`0 0 ${s} ${s}`} fill="none" aria-label="Unknown defect">
        <rect x={s * 0.12} y={s * 0.12} width={s * 0.76} height={s * 0.76}
              stroke={stroke} strokeWidth={1.4} strokeDasharray="3 2" rx={1} />
        <text x={mid} y={mid + s * 0.15}
              textAnchor="middle"
              fontSize={s * 0.42}
              fontFamily="var(--font-mono)"
              fill={stroke}>?</text>
      </svg>
    ),
  };

  return (
    <span
      className={`inline-flex items-center justify-center shrink-0 ${wrapClass}`}
      title={className}
    >
      {icons[variant]}
    </span>
  );
}
