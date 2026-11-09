import { memo } from 'react';
import type { RoundPhase } from '../types';

interface Props {
  phase: RoundPhase;
  multiplier: number;
  countdown: number;
}

function MultiplierDisplayBase({ phase, multiplier, countdown }: Props) {
  if (phase === 'countdown') {
    return (
      <div className="mult mult--wait" role="status">
        {countdown > 0 ? <div className="mult__timer">{countdown.toFixed(1)}s</div> : null}
        <div className="mult__caption">PLACE YOUR BET</div>
      </div>
    );
  }
  return (
    <div className={phase === 'ended' ? 'mult mult--ended' : 'mult'} data-tier={multiplier < 2 ? 1 : multiplier < 5 ? 2 : multiplier < 10 ? 3 : 4}>
      <div className="mult__value" style={{ transform: `scale(${1 + Math.min(multiplier - 1, 9) * 0.012})` }}>{multiplier.toFixed(2)}x</div>
      {phase === 'ended' ? <div className="mult__caption mult__caption--end">ROUND ENDED</div> : null}
    </div>
  );
}

export const MultiplierDisplay = memo(MultiplierDisplayBase);
