// Stage coordinates match the 1672x941 reference frame.
const P = [
  [210, 705],
  [700, 690],
  [1100, 600],
  [1380, 318],
] as const;

export interface PathSample {
  x: number;
  y: number;
  angle: number; // degrees, direction of travel
}

export function sampleAt(t: number): PathSample {
  const u = 1 - t;
  const a = u * u * u, b = 3 * u * u * t, c = 3 * u * t * t, d = t * t * t;
  const x = a * P[0][0] + b * P[1][0] + c * P[2][0] + d * P[3][0];
  const y = a * P[0][1] + b * P[1][1] + c * P[2][1] + d * P[3][1];
  const dx = 3 * u * u * (P[1][0] - P[0][0]) + 6 * u * t * (P[2][0] - P[1][0]) + 3 * t * t * (P[3][0] - P[2][0]);
  const dy = 3 * u * u * (P[1][1] - P[0][1]) + 6 * u * t * (P[2][1] - P[1][1]) + 3 * t * t * (P[3][1] - P[2][1]);
  return { x, y, angle: (Math.atan2(dy, dx) * 180) / Math.PI };
}

export function pathUpTo(t: number, steps = 40): string {
  const n = Math.max(2, Math.ceil(steps * Math.max(t, 0.02)));
  let d = '';
  for (let i = 0; i <= n; i++) {
    const s = sampleAt((t * i) / n);
    d += `${i === 0 ? 'M' : 'L'}${s.x.toFixed(1)} ${s.y.toFixed(1)} `;
  }
  return d;
}

export const START_POINT = sampleAt(0);

const VISUAL_MAX = 10; // multiplier at which the rocket reaches the end of the path

/** Cosmetic mapping from a multiplier to a 0..1 position on the flight path. */
export const progressFor = (m: number) =>
  Math.min(1, Math.log(Math.max(1, m)) / Math.log(VISUAL_MAX)) * 0.96;

/** Wedge-shaped exhaust trail: a bright top edge plus a fill that widens toward the rocket. */
export function wedgePaths(t: number, steps = 48): { top: string; area: string } {
  const n = Math.max(2, Math.ceil(steps * Math.max(t, 0.02)));
  const top: string[] = [];
  const bottom: string[] = [];
  for (let i = 0; i <= n; i++) {
    const k = i / n;
    const s = sampleAt(t * k);
    const taper = 1 - Math.pow(Math.max(0, (k - 0.82) / 0.18), 2); // narrows to the rocket's tail
    const hw = (8 + 170 * k * k * Math.min(1, t * 1.6)) * taper;
    top.push(`${s.x.toFixed(1)} ${s.y.toFixed(1)}`);
    bottom.push(`${s.x.toFixed(1)} ${(s.y + hw).toFixed(1)}`);
  }
  return { top: `M${top.join(' L')}`, area: `M${top.join(' L')} L${bottom.reverse().join(' L')}Z` };
}
