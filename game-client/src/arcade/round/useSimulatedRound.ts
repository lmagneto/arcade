import { useEffect, useState } from 'react';
import type { RoundPhase, RoundResult, RoundState } from '../types';
import { progressFor } from './flightGeometry';

/**
 * SIMULATION ONLY. Crash points and multiplier growth are generated in the browser
 * purely to drive the animation. They must never decide payouts or settlement.
 * A backend-driven hook (e.g. useServerRound) should return the same RoundState.
 */
const COUNTDOWN_S = 7;
const ENDED_S = 3;
const GROWTH_PER_S = 0.07;

function drawCrash(): number {
  const raw = 0.97 / (1 - Math.random());
  return Math.round(Math.min(20, Math.max(1.05, raw)) * 100) / 100;
}

export function useSimulatedRound(initialHistory: RoundResult[]): RoundState {
  const [state, setState] = useState<RoundState>({
    phase: 'countdown',
    countdown: COUNTDOWN_S,
    multiplier: 1,
    progress: 0,
    history: initialHistory,
  });

  useEffect(() => {
    let raf = 0;
    let phase: RoundPhase = 'countdown';
    let phaseStart = performance.now();
    let crashAt = drawCrash();
    let nextId = Date.now();

    const tick = (now: number) => {
      const el = (now - phaseStart) / 1000;

      if (phase === 'countdown') {
        const left = COUNTDOWN_S - el;
        if (left <= 0) {
          phase = 'flying';
          phaseStart = now;
          setState((s) => ({ ...s, phase: 'flying', countdown: 0, multiplier: 1, progress: 0 }));
        } else {
          const c = Math.ceil(left * 10) / 10;
          setState((s) =>
            s.phase === 'countdown' && s.countdown === c
              ? s
              : { ...s, phase: 'countdown', countdown: c, multiplier: 1, progress: 0 },
          );
        }
      } else if (phase === 'flying') {
        const m = Math.exp(GROWTH_PER_S * el);
        if (m >= crashAt) {
          phase = 'ended';
          phaseStart = now;
          const final = crashAt;
          setState((s) => ({
            ...s,
            phase: 'ended',
            multiplier: final,
            progress: progressFor(final),
            history: [{ id: nextId++, multiplier: final }, ...s.history].slice(0, 50),
          }));
        } else {
          setState((s) => ({ ...s, multiplier: m, progress: progressFor(m) }));
        }
      } else if (el >= ENDED_S) {
        phase = 'countdown';
        phaseStart = now;
        crashAt = drawCrash();
        setState((s) => ({ ...s, phase: 'countdown', countdown: COUNTDOWN_S, multiplier: 1, progress: 0 }));
      }
      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return state;
}
