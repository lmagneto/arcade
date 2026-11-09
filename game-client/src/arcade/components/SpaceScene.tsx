import { memo, useMemo } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import type { RoundPhase } from '../types';

function stars() {
  let s = 11;
  const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  return Array.from({ length: 150 }, (_, i) => ({
    i, x: rnd() * 1672, y: rnd() * 780, r: 0.5 + rnd() * 1.7, o: 0.3 + rnd() * 0.7, d: rnd() * 5,
  }));
}

function Logo() {
  return (
    <svg className="logo" viewBox="0 0 360 200" aria-label="Arcade Bets">
      <defs>
        <linearGradient id="lgA" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fff" /><stop offset="1" stopColor="#a9ccff" /></linearGradient>
        <linearGradient id="lgB" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fff6b0" /><stop offset="0.6" stopColor="#ffc21f" /><stop offset="1" stopColor="#ff7a00" /></linearGradient>
        <linearGradient id="lgR" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#ff4fd8" /><stop offset="0.5" stopColor="#7a3cff" /><stop offset="1" stopColor="#ffb02e" /></linearGradient>
      </defs>
      <g transform="rotate(-14 180 100)">
        <ellipse cx="180" cy="100" rx="168" ry="64" fill="none" stroke="url(#lgR)" strokeWidth="9" opacity="0.9" />
        <ellipse cx="180" cy="100" rx="168" ry="64" fill="none" stroke="#fff" strokeWidth="1.5" opacity="0.7" />
      </g>
      <g transform="rotate(-14 180 100) skewX(-14)" fontFamily="'Russo One', Impact, 'Arial Black', sans-serif" textAnchor="middle">
        <g fill="#1a0650" stroke="#1a0650" strokeWidth="14" strokeLinejoin="round">
          <text x="190" y="95" fontSize="62">ARCADE</text>
          <text x="180" y="153" fontSize="62">BETS</text>
        </g>
        <g strokeWidth="6" stroke="#6a2cff" paintOrder="stroke" strokeLinejoin="round">
          <text x="190" y="88" fontSize="62" fill="url(#lgA)">ARCADE</text>
          <text x="180" y="146" fontSize="62" fill="url(#lgB)">BETS</text>
        </g>
      </g>
      <path d="m318 120 7 14 15-3-10 11 8 13-14-6-11 10 1-15-14-8 15-3z" fill="#ffd34a" transform="scale(.55) translate(250 90)" />
    </svg>
  );
}

const DRIFTERS = [
  { y: 180, s: 70, d: 34, t: -3 }, { y: 420, s: 40, d: 26, t: -8 }, { y: 310, s: 110, d: 46, t: -20 },
  { y: 560, s: 50, d: 30, t: -14 }, { y: 240, s: 30, d: 22, t: -5 }, { y: 500, s: 90, d: 40, t: -26 },
  { y: 130, s: 44, d: 28, t: -11 },
];

const drift = (y: number, s: number, d: number, t: number): CSSProperties => ({ top: y, width: s, height: s, animationDuration: `${d}s`, animationDelay: `${t}s` });

function SpaceBackdropBase() {
  const field = useMemo(stars, []);
  return (
    <>
      <div className="nebula nebula--a" />
      <div className="nebula nebula--b" />
      <svg className="scene__stars" viewBox="0 0 1672 941" aria-hidden="true">
        {field.map((s) => (
          <circle key={s.i} cx={s.x} cy={s.y} r={s.r} fill="#d6e8ff" opacity={s.o} className={s.i % 5 === 0 ? 'twinkle' : undefined} style={{ animationDelay: `${s.d}s` }} />
        ))}
      </svg>
      <i className="shoot" style={{ top: 150, left: 900, animationDelay: '1s' }} />
      <i className="shoot" style={{ top: 260, left: 1250, animationDelay: '6s' }} />
      <div className="layer layer--pad">
        <div className="planet planet--left" />
        <div className="planet planet--right" />
        <div className="moon" style={{ left: 1309, top: 133, width: 96 }} />
        <div className="moon" style={{ left: 485, top: 286, width: 36 }} />
        <div className="moon" style={{ left: 765, top: 470, width: 60 }} />
        <svg className="scene__clouds" viewBox="0 0 1672 300" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <filter id="soft"><feGaussianBlur stdDeviation="16" /></filter>
            <linearGradient id="cloudG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#4aa8ff" /><stop offset="1" stopColor="#0a2f8a" /></linearGradient>
          </defs>
          <g filter="url(#soft)" fill="url(#cloudG)" opacity="0.95">
            {[0, 150, 330, 510, 690, 870, 1050, 1230, 1410, 1600].map((x, i) => (
              <ellipse key={x} cx={x + 40} cy={110 + (i % 3) * 34} rx={160} ry={62 + (i % 2) * 22} />
            ))}
          </g>
          <g filter="url(#soft)" fill="#d6ecff" opacity="0.8">
            {[60, 280, 520, 760, 1000, 1240, 1480].map((x, i) => (
              <ellipse key={x} cx={x} cy={165 + (i % 2) * 26} rx={120} ry={44} />
            ))}
          </g>
        </svg>
      </div>
      <div className="layer layer--deep">
        <div className="slope" />
        {DRIFTERS.map((o) => (
          <i key={o.y} className="drift" style={drift(o.y, o.s, o.d, o.t)} />
        ))}
        <i className="drift orb" style={drift(250, 300, 20, -7)} />
      </div>
    </>
  );
}

const SpaceBackdrop = memo(SpaceBackdropBase);
const LogoMemo = memo(Logo);

/** Scene wrapper. `phase` switches between the launch-pad backdrop and the deep-space flight backdrop. */
export function SpaceScene({ phase, children }: { phase: RoundPhase; children: ReactNode }) {
  return (
    <div className="scene" data-phase={phase}>
      <SpaceBackdrop />
      <LogoMemo />
      {children}
      <div className="vignette" />
    </div>
  );
}
