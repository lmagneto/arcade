
import { memo } from 'react';
import type { CSSProperties } from 'react';
import type { PlayerPanelData } from '../types';

const money = (n: number | undefined) =>
  (Number(n) || 0).toFixed(2);

function PlayerPanelBase({
  player,
  confirm,
}: {
  player: PlayerPanelData;
  confirm?: boolean;
}) {
  

  return (
    <li
      className={player.active === false ? 'pp pp--inactive' : 'pp'}
      style={{ '--c': player.color } as CSSProperties}
      aria-label={`Player ${player.id}`}
    >
      {player.blinkId !== undefined && (
        <span
          key={player.blinkId}
          className="pp__blink"
          aria-hidden="true"
        />
      )}

      {player.statusText ? (
        <span className={`pp__status pp__status--${player.statusKind ?? 'info'}`}>
          {player.statusText}
        </span>
      ) : confirm ? (
        <span className="pp__confirm">
          <svg viewBox="0 0 16 22" width="14" height="19" aria-hidden="true">
            <rect x="1" y="1" width="14" height="20" rx="7" fill="#fff" stroke="#bcd8ff" />
            <path d="M8 1v8M1 9h14" stroke="#2a6cff" />
            <path d="M1 9V8a7 7 0 0 1 7-7v8z" fill="#2a8cff" />
          </svg>
          to Confirm
        </span>
      ) : null}

      <span className="pp__num">{player.id}</span>

      <div className="pp__cell">
        <span className="pp__label">BALANCE</span>
        <span className="pp__value">{money(player.balance)}</span>
      </div>

      <div className="pp__cell">
        <span className="pp__label">BET</span>
        <span className="pp__value">{money(player.bet)}</span>
      </div>

     
    </li>
  );
}

export const PlayerPanel = memo(PlayerPanelBase);
