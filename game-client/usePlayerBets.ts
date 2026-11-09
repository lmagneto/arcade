import { useEffect, useRef, useState } from 'react';
import type { CurrentRound, PlayerStation } from '../../api';
import type { RoundState } from '../types';

/** Virtual assets moved between balance and bet per right-click / scroll notch. */
export const BET_STEP = 10;
const PANEL_COUNT = 8;

/** Button names the mouse bridge may use for a left click. */
const LEFT_BUTTONS = new Set(['LEFT_DOWN', 'LEFT', 'LEFT_CLICK']);

export type BetStatus = 'idle' | 'queued' | 'inplay';

export interface BetResult {
  kind: 'win' | 'loss';
  /** Payout for a win, lost stake for a loss. */
  amount: number;
  multiplier: number;
}

export interface SlotBet {
  /** Amount currently set aside as the bet (adjusted, queued or in play). */
  stake: number;
  status: BetStatus;
  /** A queued bet may not join this round id (it was already flying when the bet was placed). */
  joinAfter: string | null;
  /** Round the bet is playing in while status === 'inplay'. */
  roundId: string | null;
  /** Net winnings/losses already settled, added to the server wallet. */
  net: number;
  result: BetResult | null;
}

export type MouseButtonEvent = { button: string; eventId: number };
export type MouseEventData = MouseButtonEvent & { batch?: MouseButtonEvent[] };

export const EMPTY_SLOT: SlotBet = {
  stake: 0,
  status: 'idle',
  joinAfter: null,
  roundId: null,
  net: 0,
  result: null,
};

const cents = (n: number) => Math.round(n * 100) / 100;

const serverWallet = (players: PlayerStation[], slotNumber: number) =>
  Number(players.find((p) => p.slot_number === slotNumber)?.wallet_balance) || 0;

/**
 * Per-player bet lifecycle (all client-side):
 *  idle    : right-click raises the bet, scroll lowers it (balance moves the opposite way)
 *  left click while idle with a bet  -> queued (locked) for the NEXT round
 *  queued  -> inplay when a new round starts flying
 *  left click while inplay -> cash out: balance += bet x current multiplier
 *  inplay  -> lost if the round crashes before the player cashes out
 */
export function usePlayerBets(
  players: PlayerStation[],
  mouseEvents: Record<number, MouseEventData>,
  round: CurrentRound | null,
  roundState: RoundState,
): Record<number, SlotBet> {
  const [slots, setSlots] = useState<Record<number, SlotBet>>({});
  const slotsRef = useRef<Record<number, SlotBet>>({});
  const lastProcessed = useRef<Record<number, number>>({});
  const live = useRef({ players, round, roundState });

  // Keep the latest inputs available to the event handler (declared first so it runs first).
  useEffect(() => {
    live.current = { players, round, roundState };
  }, [players, round, roundState]);

  const commit = (next: Record<number, SlotBet>) => {
    slotsRef.current = next;
    setSlots(next);
  };

  // Round transitions: queued -> inplay, inplay -> lost on crash.
  useEffect(() => {
    if (!round) return;

    const next = { ...slotsRef.current };
    let changed = false;

    for (const [key, slot] of Object.entries(next)) {
      const n = Number(key);

      if (
        slot.status === 'queued' &&
        round.status === 'RUNNING' &&
        round.id !== slot.joinAfter
      ) {
        next[n] = { ...slot, status: 'inplay', roundId: round.id, result: null };
        changed = true;
      } else if (
        slot.status === 'inplay' &&
        (slot.roundId !== round.id ||
          round.status === 'CRASHED' ||
          round.status === 'COMPLETED')
      ) {
        next[n] = {
          ...slot,
          net: cents(slot.net - slot.stake),
          stake: 0,
          status: 'idle',
          roundId: null,
          result: {
            kind: 'loss',
            amount: slot.stake,
            multiplier: Number(round.final_multiplier) || 0,
          },
        };
        changed = true;
      }
    }

    if (changed) commit(next);
  }, [round?.id, round?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  // Mouse events.
  useEffect(() => {
    const next = { ...slotsRef.current };
    let changed = false;

    for (const [slotText, event] of Object.entries(mouseEvents)) {
      const n = Number(slotText);
      if (!Number.isInteger(n) || n < 1 || n > PANEL_COUNT) continue;

      for (const e of event.batch ?? [event]) {
        if (e.eventId <= (lastProcessed.current[n] ?? 0)) continue;
        lastProcessed.current[n] = e.eventId;

        const { players: ps, round: r, roundState: rs } = live.current;
        const slot = { ...(next[n] ?? EMPTY_SLOT) };
        const wallet = cents(serverWallet(ps, n) + slot.net);

        if (e.button === 'RIGHT_DOWN' && slot.status === 'idle') {
          // Right click: bet up, balance down (never below 0).
          slot.stake = cents(Math.min(slot.stake + BET_STEP, wallet));
          slot.result = null;
        } else if (e.button === 'WHEEL' && slot.status === 'idle') {
          // Scroll: bet down, balance up (never below 0 bet).
          slot.stake = cents(Math.max(0, slot.stake - BET_STEP));
          slot.result = null;
        } else if (LEFT_BUTTONS.has(e.button)) {
          if (slot.status === 'idle' && slot.stake > 0) {
            // Place the bet for the NEXT round.
            const roundAlreadyStarted =
              r && r.status !== 'WAITING' && r.status !== 'ABORTED';
            slot.status = 'queued';
            slot.joinAfter = roundAlreadyStarted ? r.id : null;
            slot.result = null;
          } else if (
            slot.status === 'inplay' &&
            r?.status === 'RUNNING' &&
            r.id === slot.roundId
          ) {
            // Exit mid-round: bet x current multiplier goes back to the balance.
            const multiplier = rs.multiplier;
            const payout = cents(slot.stake * multiplier);
            slot.net = cents(slot.net - slot.stake + payout);
            slot.result = { kind: 'win', amount: payout, multiplier };
            slot.stake = 0;
            slot.status = 'idle';
            slot.roundId = null;
          } else {
            continue;
          }
        } else {
          continue;
        }

        next[n] = slot;
        changed = true;
      }
    }

    if (changed) commit(next);
  }, [mouseEvents]);

  return slots;
}
