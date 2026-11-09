import { useEffect, useRef, useState } from 'react';
import type { CurrentRound } from '../../api';
import type { RoundResult, RoundState } from '../types';
import { progressFor } from './flightGeometry';

const INITIAL: RoundState = { phase: 'countdown', countdown: 0, multiplier: 1, progress: 0, history: [] };
const MAX_HISTORY = 50;

interface Tween {
  roundId: string;
  from: number;
  to: number;
  cur: number;
  start: number; // time the current segment began
  dur: number; // segment length, matched to the observed poll interval
}

const num = (v: string | null | undefined, fallback: number) => {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : fallback;
};

/**
 * Turns the backend's CurrentRound into the RoundState the UI draws.
 * The backend stays authoritative: the on-screen multiplier only glides toward values the
 * server has already reported (about one poll behind) and never runs ahead of them.
 * Nothing here decides payouts, results or settlement.
 */
export function useServerRound(round: CurrentRound | null): RoundState {
  const [state, setState] = useState<RoundState>(INITIAL);
  const roundRef = useRef<CurrentRound | null>(round);
  const tween = useRef<Tween>({ roundId: '', from: 1, to: 1, cur: 1, start: 0, dur: 1000 });
  const recorded = useRef(new Set<string>());
  const history = useRef<RoundResult[]>([]);

  useEffect(() => {
    roundRef.current = round;
  }, [round]);

  useEffect(() => {
    let raf = 0;

    const tick = (now: number) => {
      const r = roundRef.current;
      const t = tween.current;
      let next: RoundState = { ...INITIAL, history: history.current };

      if (r) {
        if (t.roundId !== r.id) {
          t.roundId = r.id;
          t.from = t.to = t.cur = 1;
          t.start = now;
          t.dur = 1000;
        }

        if (r.status === 'RUNNING') {
          const target = Math.max(1, num(r.display_multiplier, 1));
          if (target !== t.to) {
            t.dur = Math.min(1500, Math.max(300, now - t.start));
            t.from = t.cur;
            t.to = target;
            t.start = now;
          }
          const k = Math.min(1, (now - t.start) / t.dur);
          t.cur = t.from + (t.to - t.from) * k;
          next = { phase: 'flying', countdown: 0, multiplier: t.cur, progress: progressFor(t.cur), history: history.current };
        } else if (r.status === 'CRASHED' || r.status === 'COMPLETED') {
          const final = num(r.final_multiplier, num(r.display_multiplier, t.to));
          t.cur = t.to = final;
          if (!recorded.current.has(r.id)) {
            recorded.current.add(r.id);
            history.current = [{ id: r.round_number, multiplier: final }, ...history.current].slice(0, MAX_HISTORY);
          }
          next = { phase: 'ended', countdown: 0, multiplier: final, progress: progressFor(final), history: history.current };
        } else {
          // WAITING or ABORTED: show the countdown to the scheduled start, if there is one.
          const startAt = r.scheduled_start_at ? Date.parse(r.scheduled_start_at) : NaN;
          const countdown = Number.isFinite(startAt) ? Math.max(0, (startAt - Date.now()) / 1000) : 0;
          t.cur = t.to = 1;
          next = { phase: 'countdown', countdown, multiplier: 1, progress: 0, history: history.current };
        }
      }

      // Only re-render when something visible changed.
      setState((prev) =>
        prev.phase === next.phase &&
        prev.countdown.toFixed(1) === next.countdown.toFixed(1) &&
        prev.history === next.history &&
        prev.multiplier.toFixed(2) === next.multiplier.toFixed(2) &&
        Math.abs(prev.progress - next.progress) < 0.0005
          ? prev
          : next,
      );
      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return state;
}
