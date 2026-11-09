import { memo } from 'react';
import type { CSSProperties, ReactElement } from 'react';
import type { JackpotIcon, JackpotInfo } from '../types';

const ICONS: Record<JackpotIcon, ReactElement> = {
  crown: <path d="M3 20 5 8l5 5 2-8 2 8 5-5 2 12z" fill="#ffc83a" stroke="#ff9a1f" strokeWidth="1.2" />,
  diamond: <path d="M6 4h12l5 6-11 12L1 10z M1 10h22" fill="#5cc8ff" stroke="#e6f6ff" strokeWidth="1.2" />,
  globe: (
    <g fill="none" stroke="#ffb02e" strokeWidth="1.8">
      <circle cx="12" cy="12" r="9" />
      <ellipse cx="12" cy="12" rx="4" ry="9" />
      <path d="M3 12h18M5 7h14M5 17h14" />
    </g>
  ),
  star: <path d="m12 2 3 7 7.5.6-5.7 4.9 1.8 7.4L12 18l-6.6 3.9 1.8-7.4L1.5 9.6 9 9z" fill="#ffd3ff" stroke="#fff" strokeWidth="1" />,
  coins: (
    <g fill="#ffc83a" stroke="#c98200" strokeWidth="1.2">
      <ellipse cx="12" cy="18" rx="8" ry="3.2" />
      <ellipse cx="12" cy="13" rx="8" ry="3.2" />
      <ellipse cx="12" cy="8" rx="8" ry="3.2" />
    </g>
  ),
};

const fmt = (n: number) => `KSh ${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

interface Props {
  jackpots: JackpotInfo[];
}

function JackpotBarBase({ jackpots }: Props) {
  return (
    <ul className="jackpots">
      {jackpots.map((j) => (
        <li key={j.id} className="jackpot" style={{ '--c': j.color } as CSSProperties}>
          <div className="jackpot__head">
            <svg className="jackpot__icon" viewBox="0 0 24 24" aria-hidden="true">{ICONS[j.icon]}</svg>
            <span className="jackpot__label">{j.label}</span>
          </div>
          <div className="jackpot__amount">{fmt(j.amount)}</div>
        </li>
      ))}
    </ul>
  );
}

export const JackpotBar = memo(JackpotBarBase);
