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
import { usePlaneEngineSound } from '../round/usePlaneEngineSound';

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
  const planeSound = usePlaneEngineSound(round.phase, round.multiplier);

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
        <button
          className="plane-sound-toggle"
          type="button"
          onClick={planeSound.toggle}
          aria-pressed={planeSound.enabled}
          aria-label={planeSound.enabled ? 'Mute plane sound' : 'Enable plane sound'}
          title={planeSound.enabled ? 'Mute plane sound' : 'Enable plane sound'}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M3 9v6h4l5 4V5L7 9H3z" />
            {planeSound.enabled ? (
              <>
                <path d="M16 9a5 5 0 0 1 0 6" />
                <path d="M18.5 6.5a9 9 0 0 1 0 11" />
              </>
            ) : (
              <>
                <path d="m16 9 5 6" />
                <path d="m21 9-5 6" />
              </>
            )}
          </svg>
          <span>{planeSound.enabled ? 'SOUND ON' : 'SOUND OFF'}</span>
        </button>
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
