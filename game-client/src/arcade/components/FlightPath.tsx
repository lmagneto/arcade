import { memo } from 'react';
import type { CSSProperties } from 'react';
import { sampleAt, wedgePaths } from '../round/flightGeometry';
import type { RoundPhase } from '../types';
import { Rocket } from './Rocket';

interface Props {
  phase: RoundPhase;
  progress: number;
  countdown: number;
}

const DEFS = (
  <defs>
    <linearGradient id="wedgeGrad" gradientUnits="userSpaceOnUse" x1="210" y1="0" x2="1380" y2="0">
      <stop offset="0" stopColor="#ff6a00" stopOpacity="0.15" />
      <stop offset="0.55" stopColor="#ff9d1c" stopOpacity="0.8" />
      <stop offset="1" stopColor="#ffe04a" stopOpacity="0.95" />
    </linearGradient>
    <linearGradient id="flameGrad" x1="1" y1="0" x2="0" y2="0">
      <stop offset="0" stopColor="#ffd34a" /><stop offset="0.5" stopColor="#ff8a1f" /><stop offset="1" stopColor="#ff5a00" stopOpacity="0" />
    </linearGradient>
    <linearGradient id="finGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ff6a50" /><stop offset="1" stopColor="#c42d20" /></linearGradient>
    <radialGradient id="glassGrad" cx="0.35" cy="0.3" r="0.8"><stop offset="0" stopColor="#8fe3ff" /><stop offset="0.5" stopColor="#1f7be8" /><stop offset="1" stopColor="#0a2a78" /></radialGradient>
    <linearGradient id="trailGrad" gradientUnits="userSpaceOnUse" x1="210" y1="705" x2="1380" y2="318"><stop offset="0" stopColor="#ff7a00" stopOpacity="0.3" /><stop offset="0.6" stopColor="#ffb02e" /><stop offset="1" stopColor="#fff2b0" /></linearGradient>
    <linearGradient id="bodyGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ffffff" /><stop offset="1" stopColor="#c9d4ea" /></linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="5" result="b" />
      <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
    </filter>
  </defs>
);

function FlightPathBase({ phase, progress, countdown }: Props) {
  if (phase === 'countdown') {
    const ignite = countdown > 0 && countdown <= 0.8;
    return (
      <svg className="flight" viewBox="0 0 1672 941" aria-hidden="true">
        {DEFS}
        <g className={ignite ? 'pad pad--ignite' : 'pad'}>
          <Rocket x={836} y={266} angle={-90} flying={ignite} />
        </g>
      </svg>
    );
  }

  const end = sampleAt(progress);
  const { top, area } = wedgePaths(progress);
  const away = phase === 'ended';
  const rad = (end.angle * Math.PI) / 180;
  const awayStyle = { '--dx': `${(Math.cos(rad) * 1300).toFixed(0)}px`, '--dy': `${(Math.sin(rad) * 1300).toFixed(0)}px` } as CSSProperties;

  return (
    <svg className="flight" viewBox="0 0 1672 941" aria-hidden="true">
      {DEFS}
      <g className={away ? 'trail trail--fade' : 'trail'}>
        <path d={area} fill="url(#wedgeGrad)" />
        <path d={top} fill="none" stroke="url(#trailGrad)" strokeWidth="5" strokeLinecap="round" filter="url(#glow)" />
      </g>
      <g className={away ? 'away' : 'launch'} style={away ? awayStyle : undefined}>
        <Rocket x={end.x} y={end.y} angle={end.angle} flying={!away} />
      </g>
    </svg>
  );
}

export const FlightPath = memo(FlightPathBase);
