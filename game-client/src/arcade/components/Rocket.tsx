import { memo } from 'react';

interface Props { x: number; y: number; angle: number; flying: boolean; }

function RocketBase({ x, y, angle, flying }: Props) {
  return (
    <g transform={`translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${angle.toFixed(1)}) scale(2.1)`}>
      <g className={flying ? 'rocket__flame rocket__flame--on' : 'rocket__flame'}>
        <path d="M-40 0 Q-110 -22 -230 0 Q-110 22 -40 0Z" fill="url(#flameGrad)" opacity="0.75" />
        <path d="M-40 0 Q-90 -13 -160 0 Q-90 13 -40 0Z" fill="#ffb02e" />
        <path d="M-40 0 Q-70 -6 -105 0 Q-70 6 -40 0Z" fill="#fffbe0" />
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <circle key={i} className="spark" r={2 + (i % 3)} cx={-60} cy={(i - 2.5) * 4} fill="#ffd34a" style={{ animationDelay: `${i * 0.13}s` }} />
        ))}
      </g>
      <path d="M-28 -13 L-52 -40 L-4 -17Z" fill="url(#finGrad)" />
      <path d="M-28 13 L-52 40 L-4 17Z" fill="#a8231a" />
      <rect x="-46" y="-8" width="10" height="16" rx="3" fill="#5b6479" />
      <path d="M-40 -16 Q12 -26 56 0 Q12 26 -40 16Z" fill="url(#bodyGrad)" stroke="#aebbd6" strokeWidth="1" />
      <path d="M-34 -10 Q10 -20 48 -3 Q10 -12 -34 -6Z" fill="#fff" opacity="0.8" />
      <path d="M-14 -17 L-14 17" stroke="#e53a2a" strokeWidth="6" opacity="0.9" />
      <path d="M28 -12 Q44 -9 57 0 Q44 9 28 12 Q35 0 28 -12Z" fill="url(#finGrad)" />
      <circle cx="6" cy="0" r="10.5" fill="#d9e4f5" stroke="#e53a2a" strokeWidth="3" />
      <circle cx="6" cy="0" r="7.5" fill="url(#glassGrad)" />
      <ellipse cx="3.5" cy="-3" rx="3" ry="1.8" fill="#fff" opacity="0.85" />
    </g>
  );
}

export const Rocket = memo(RocketBase);
