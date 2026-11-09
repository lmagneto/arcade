import type { JackpotInfo, PlayerPanelData, RoundPlayer, RoundState } from '../types';
import { useStageScale } from '../round/useStageScale';
import { JackpotBar } from './JackpotBar';
import { RoundPlayers } from './RoundPlayers';
import { RecentMultipliers } from './RecentMultipliers';
import { SpaceScene } from './SpaceScene';
import { FlightPath } from './FlightPath';
import { MultiplierDisplay } from './MultiplierDisplay';
import { PlayerPanelRow } from './PlayerPanelRow';
import { AgeRestrictionBadge } from './AgeRestrictionBadge';

export const STAGE_W = 1672;
export const STAGE_H = 941;

interface Props {
  round: RoundState;
  jackpots: JackpotInfo[];
  players: PlayerPanelData[];
  /** Players with a bet in the current round (left column). */
  roundPlayers: RoundPlayer[];
  /** Short status text, e.g. engine unavailable or a connection error. */
  notice?: string;
}

/** Purely presentational: feed it RoundState from the simulation or from the backend. */
export function GameScreen({ round, jackpots, players, roundPlayers, notice }: Props) {
  const scale = useStageScale(STAGE_W, STAGE_H);
  return (
    <main
  className="arcade-viewport"
  onContextMenu={(event) => event.preventDefault()}
>
      <div className="arcade-stage" style={{ transform: `translate(-50%, -50%) scale(${scale})` }}>
        <SpaceScene phase={round.phase}>
          <FlightPath phase={round.phase} progress={round.progress} countdown={round.countdown} />
          <MultiplierDisplay phase={round.phase} multiplier={round.multiplier} countdown={round.countdown} />
        </SpaceScene>
        <JackpotBar jackpots={jackpots} />
        <RecentMultipliers history={round.history} />
        <RoundPlayers players={roundPlayers} />
        {notice ? <div className="notice" role="status">{notice}</div> : null}
        <AgeRestrictionBadge />
        <PlayerPanelRow players={players} confirm={round.phase === 'countdown' && round.countdown > 0} />
      </div>
    </main>
  );
}
