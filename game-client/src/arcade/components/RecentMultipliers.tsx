import { memo } from 'react';
import type { RoundResult } from '../types';
import { tierColor } from '../round/tier';

/** Completed-round results along the top edge, newest first. */
function RecentMultipliersBase({ history }: { history: RoundResult[] }) {
  return (
    <section className="recent-bar" aria-label="Recent multipliers">
      <h2 className="recent-bar__title">RECENT MULTIPLIERS</h2>
      <ul className="recent-bar__list">
        {history.slice(0, 24).map((r) => (
          <li key={r.id} className="recent-bar__chip" style={{ color: tierColor(r.multiplier) }}>
            {r.multiplier.toFixed(2)}x
          </li>
        ))}
      </ul>
    </section>
  );
}

export const RecentMultipliers = memo(RecentMultipliersBase);
