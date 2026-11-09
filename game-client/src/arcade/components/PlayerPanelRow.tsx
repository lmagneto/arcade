import { memo } from 'react';
import type { PlayerPanelData } from '../types';
import { PlayerPanel } from './PlayerPanel';

function PlayerPanelRowBase({ players, confirm }: { players: PlayerPanelData[]; confirm?: boolean }) {
  return (
    <ul className="pp-row">
      {players.map((p) => (
        <PlayerPanel key={p.id} player={p} confirm={confirm} />
      ))}
    </ul>
  );
}

export const PlayerPanelRow = memo(PlayerPanelRowBase);
