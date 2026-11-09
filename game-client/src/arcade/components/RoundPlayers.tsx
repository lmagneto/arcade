import { memo } from 'react';
import type { RoundPlayer } from '../types';

/** Everyone who has a bet in the current round (left column). */
function RoundPlayersBase({ players }: { players: RoundPlayer[] }) {
  return (
    <section className="rp" aria-label="Players in this round">
      <h2 className="rp__title">PLAYERS IN ROUND</h2>
      <ul className="rp__list">
        {players.length === 0 ? <li className="rp__empty">No bets yet</li> : null}
        {players.map((p) => (
          <li key={p.id} className="rp__row">
            <span className="rp__name">{p.name}</span>
            <span className="rp__bet">{p.bet.toFixed(2)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export const RoundPlayers = memo(RoundPlayersBase);
