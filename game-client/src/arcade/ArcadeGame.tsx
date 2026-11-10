import { useEffect, useMemo, useState } from 'react';
import type {
  CurrentRound,
  EngineHealth,
  PlayerBetInfo,
  PlayerStation,
} from '../api';
import { GameScreen } from './components/GameScreen';
import { useServerRound } from './round/useServerRound';
import {
  EMPTY_SLOT,
  usePlayerBets,
  type MouseEventData,
  type SlotView,
} from './round/usePlayerBets';
import type { JackpotInfo, PlayerPanelData, RoundPlayer } from './types';
import './arcade.css';

const PANEL_COLORS = [
  '#f5b92a',
  '#2e8bff',
  '#ff4a1c',
  '#9b4dff',
  '#22d65a',
  '#00c9b7',
  '#ff65a3',
  '#a8d83e',
];

const PANEL_COUNT = 8;

const walletOf = (slot: PlayerStation | undefined) =>
  slot ? Number(slot.wallet_balance) || 0 : 0;

function statusFor(
  view: SlotView,
  multiplier: number,
): Pick<PlayerPanelData, 'statusText' | 'statusKind'> {
  if (view.status === 'queued') {
    return { statusText: 'BET QUEUED - NEXT ROUND', statusKind: 'info' };
  }
  if (view.status === 'placed') {
    return { statusText: 'BET PLACED', statusKind: 'info' };
  }
  if (view.status === 'inplay') {
    return {
      statusText: `CASH OUT ${(view.stake * multiplier).toFixed(2)}`,
      statusKind: 'live',
    };
  }
  if (view.result?.kind === 'win') {
    return {
      statusText: `CASHED OUT ${view.result.amount.toFixed(2)} @ ${view.result.multiplier.toFixed(2)}x`,
      statusKind: 'win',
    };
  }
  if (view.result?.kind === 'loss') {
    return {
      statusText: `LOST -${view.result.amount.toFixed(2)}`,
      statusKind: 'loss',
    };
  }
  return {};
}

function toPanels(
  players: PlayerStation[],
  mouseEvents: Record<number, MouseEventData>,
  views: Record<number, SlotView>,
  multiplier: number,
): PlayerPanelData[] {
  return Array.from({ length: PANEL_COUNT }, (_, i) => {
    const slotNumber = i + 1;
    const slot = players.find((p) => p.slot_number === slotNumber);
    const mouseEvent = mouseEvents[slotNumber];
    const view = views[slotNumber] ?? EMPTY_SLOT;
    const balance = walletOf(slot) - view.staged;

    return {
      id: slotNumber as PlayerPanelData['id'],
      balance: Math.max(0, balance),
      bet: view.stake,
      color: PANEL_COLORS[i],
      active: slot?.status === 'ACTIVE',
      ...statusFor(view, multiplier),
      mouseEvent: mouseEvent?.button ?? '',
      blinkId:
        mouseEvent?.button === 'WHEEL'
          ? mouseEvent.eventId
          : undefined,
    };
  }).filter((panel) => panel.active);
}

function toRoundPlayers(
  players: PlayerStation[],
  views: Record<number, SlotView>,
): RoundPlayer[] {
  return players
    .filter((p) => p.status === 'ACTIVE')
    .filter((p) => {
      const status = views[p.slot_number]?.status;
      return status === 'placed' || status === 'inplay';
    })
    .map((p) => ({
      id: p.slot_id,
      name: p.display_name,
      bet: views[p.slot_number].stake,
    }));
}

interface Props {
  round: CurrentRound | null;
  players: PlayerStation[];
  bets: PlayerBetInfo[];
  jackpots: JackpotInfo[];
  deviceCredential: string;
  onRefresh: () => Promise<void>;
  health: EngineHealth | null;
  message: string;
  mouseEvents: Record<number, MouseEventData>;
}

export function ArcadeGame({
  round,
  players,
  bets,
  jackpots,
  deviceCredential,
  onRefresh,
  health,
  message,
  mouseEvents,
}: Props) {
  const state = useServerRound(round);
  const [actionError, setActionError] = useState('');

  useEffect(() => {
    if (!actionError) return;
    const timer = window.setTimeout(() => setActionError(''), 3000);
    return () => window.clearTimeout(timer);
  }, [actionError]);

  const views = usePlayerBets({
    players,
    bets,
    mouseEvents,
    round,
    roundState: state,
    deviceCredential,
    onRefresh,
    onError: setActionError,
  });

  const panels = useMemo(
    () => toPanels(players, mouseEvents, views, state.multiplier),
    [players, mouseEvents, views, state.multiplier],
  );

  const roundPlayers = useMemo(
    () => toRoundPlayers(players, views),
    [players, views],
  );

  const notice = health && !health.healthy
    ? health.status === 'STARTING'
      ? 'Engine starting - please wait'
      : 'Engine unavailable'
    : actionError || message;

  return (
    <GameScreen
      round={state}
      jackpots={jackpots}
      players={panels}
      roundPlayers={roundPlayers}
      notice={notice}
    />
  );
}