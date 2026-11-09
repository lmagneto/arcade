import { useEffect, useRef, useState } from 'react';
import {
  cashOutBet,
  placeBet,
  type CurrentRound,
  type PlayerBetInfo,
  type PlayerStation,
} from '../../api';
import type { RoundState } from '../types';

/** Virtual assets moved between balance and bet per right-click / scroll notch. */
export const BET_STEP = 10;
const PANEL_COUNT = 8;

/** Button names the mouse bridge may use for a left click. */
const LEFT_BUTTONS = new Set(['LEFT_DOWN', 'LEFT_UP']);

export type BetStatus = 'idle' | 'queued' | 'placed' | 'inplay';

export interface BetResult {
  kind: 'win' | 'loss';
  /** Total paid back for a win, stake lost for a loss. */
  amount: number;
  multiplier: number;
  capped: boolean;
}

export interface SlotView {
  /** Bet amount shown in the BET box (server stake once placed, else staged). */
  stake: number;
  /** Amount staged locally and not yet held by the server. */
  staged: number;
  status: BetStatus;
  result: BetResult | null;
}

export type MouseButtonEvent = { button: string; eventId: number };
export type MouseEventData = MouseButtonEvent & { batch?: MouseButtonEvent[] };

export const EMPTY_SLOT: SlotView = {
  stake: 0,
  staged: 0,
  status: 'idle',
  result: null,
};

const cents = (n: number) => Math.round(n * 100) / 100;
const num = (v: string | null | undefined) => Number(v) || 0;

interface Options {
  players: PlayerStation[];
  bets: PlayerBetInfo[];
  mouseEvents: Record<number, MouseEventData>;
  round: CurrentRound | null;
  roundState: RoundState;
  deviceCredential: string;
  /** Re-fetch wallets and bets from the server. */
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
}

/**
 * Bet lifecycle. The server holds the money and decides every result:
 *
 *  right-click / scroll  stage the bet amount locally (balance shown minus the staged amount)
 *  left click            place the staged bet on the NEXT round (sent once a round is waiting)
 *  left click in flight  cash out; the server prices it at its own multiplier
 *  round crash           the server settles the loss onto the major account
 */
export function usePlayerBets({
  players,
  bets,
  mouseEvents,
  round,
  roundState,
  deviceCredential,
  onRefresh,
  onError,
}: Options): Record<number, SlotView> {
  const [staged, setStaged] = useState<Record<number, number>>({});
  const [queued, setQueued] = useState<Record<number, boolean>>({});

  const stagedRef = useRef(staged);
  const queuedRef = useRef(queued);
  const busyRef = useRef<Record<number, boolean>>({});
  const lastProcessed = useRef<Record<number, number>>({});
  const live = useRef({ players, bets, round, roundState, deviceCredential });

  // Keep the latest inputs for async handlers (declared before the effects that read it).
  useEffect(() => {
    live.current = { players, bets, round, roundState, deviceCredential };
  }, [players, bets, round, roundState, deviceCredential]);

  const writeStaged = (next: Record<number, number>) => {
    stagedRef.current = next;
    setStaged(next);
  };
  const writeQueued = (next: Record<number, boolean>) => {
    queuedRef.current = next;
    setQueued(next);
  };

  const activeBetFor = (slotNumber: number) => {
    const { bets: all, round: r } = live.current;
    return all.find(
      (b) =>
        b.slot_number === slotNumber &&
        b.status === 'PLACED' &&
        r !== null &&
        b.round_id === r.id,
    );
  };

  async function sendBet(slotNumber: number) {
    const amount = cents(stagedRef.current[slotNumber] ?? 0);
    if (amount <= 0 || busyRef.current[slotNumber]) return;

    busyRef.current[slotNumber] = true;
    try {
      await placeBet(live.current.deviceCredential, slotNumber, amount.toFixed(2));
      await onRefresh();
      writeStaged({ ...stagedRef.current, [slotNumber]: 0 });
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Bet could not be placed.');
    } finally {
      busyRef.current[slotNumber] = false;
      writeQueued({ ...queuedRef.current, [slotNumber]: false });
    }
  }

  async function sendCashOut(slotNumber: number) {
    if (busyRef.current[slotNumber]) return;

    busyRef.current[slotNumber] = true;
    try {
      await cashOutBet(live.current.deviceCredential, slotNumber);
      await onRefresh();
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Cash out failed.');
      void onRefresh().catch(() => undefined);
    } finally {
      busyRef.current[slotNumber] = false;
    }
  }

  // A bet queued during a flight is sent as soon as the next round is waiting.
  useEffect(() => {
    if (round?.status !== 'WAITING') return;

    for (const [key, isQueued] of Object.entries(queuedRef.current)) {
      if (isQueued) void sendBet(Number(key));
    }
  }, [round?.id, round?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  // Mouse events.
  useEffect(() => {
    for (const [slotText, event] of Object.entries(mouseEvents)) {
      const n = Number(slotText);
      if (!Number.isInteger(n) || n < 1 || n > PANEL_COUNT) continue;

      for (const e of event.batch ?? [event]) {
        if (e.eventId <= (lastProcessed.current[n] ?? 0)) continue;
        lastProcessed.current[n] = e.eventId;

        const { players: ps, round: r } = live.current;
        const active = activeBetFor(n);
        const available = num(ps.find((p) => p.slot_number === n)?.wallet_balance);
        const current = stagedRef.current[n] ?? 0;
        const locked = Boolean(active) || queuedRef.current[n] || busyRef.current[n];

        if (e.button === 'RIGHT_DOWN' && !locked) {
          // Right click: bet up, balance down (never below 0).
          writeStaged({ ...stagedRef.current, [n]: cents(Math.min(current + BET_STEP, available)) });
        } else if (e.button === 'WHEEL' && !locked) {
          // Scroll: bet down, balance up (never below 0 bet).
          writeStaged({ ...stagedRef.current, [n]: cents(Math.max(0, current - BET_STEP)) });
        } else if (LEFT_BUTTONS.has(e.button)) {
          if (active && r?.status === 'RUNNING') {
            void sendCashOut(n); // exit mid-round at the server's multiplier
          } else if (!active && !locked && current > 0) {
            if (r?.status === 'WAITING') {
              void sendBet(n); // a round is waiting: bet on it now
            } else {
              writeQueued({ ...queuedRef.current, [n]: true }); // bet on the next round
            }
          }
        }
      }
    }
  }, [mouseEvents]); // eslint-disable-line react-hooks/exhaustive-deps

  // Derive what each panel shows.
  const views: Record<number, SlotView> = {};

  for (let n = 1; n <= PANEL_COUNT; n++) {
    const stagedAmount = staged[n] ?? 0;
    const active = bets.find(
      (b) => b.slot_number === n && b.status === 'PLACED' && round !== null && b.round_id === round.id,
    );

    if (active) {
      views[n] = {
        stake: num(active.stake),
        staged: 0,
        status: round?.status === 'RUNNING' ? 'inplay' : 'placed',
        result: null,
      };
      continue;
    }

    let result: BetResult | null = null;
    if (stagedAmount === 0 && !queued[n]) {
      const settled = bets
        .filter((b) => b.slot_number === n && (b.status === 'CASHED_OUT' || b.status === 'LOST'))
        .sort((a, b) => b.round_number - a.round_number)[0];

      if (settled?.status === 'CASHED_OUT') {
        result = {
          kind: 'win',
          amount: num(settled.payout),
          multiplier: num(settled.cashout_multiplier),
          capped: settled.payout_capped,
        };
      } else if (settled?.status === 'LOST') {
        result = { kind: 'loss', amount: num(settled.stake), multiplier: 0, capped: false };
      }
    }

    views[n] = {
      stake: stagedAmount,
      staged: stagedAmount,
      status: queued[n] ? 'queued' : 'idle',
      result,
    };
  }

  return views;
}
