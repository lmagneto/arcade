export type RoundPhase = 'countdown' | 'flying' | 'ended';

export interface RoundResult {
  id: number;
  multiplier: number;
}

/** Everything the UI needs to draw a round. A backend feed must produce this same shape. */
export interface RoundState {
  phase: RoundPhase;
  countdown: number; // seconds left (fractional) while phase === 'countdown'
  multiplier: number; // current (or final) multiplier
  progress: number; // 0..1 position of the rocket along the flight path
  history: RoundResult[]; // newest first, completed rounds only
}

export type JackpotIcon = 'crown' | 'diamond' | 'globe' | 'star' | 'coins';

export interface JackpotInfo {
  id: string;
  label: string;
  amount: number;
  color: string;
  icon: JackpotIcon;
}

export interface RoundPlayer {
  id: string;
  name: string;
  bet: number;
}

export interface PlayerPanelData {
  id: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8;
  balance: number; // available balance (wallet minus current bet)
  bet: number;
  color: string;
  active?: boolean; // false dims the panel (no player/slot inactive)
  /** Short bet status shown above the panel, e.g. "BET PLACED" or "CASH OUT 25.00". */
  statusText?: string;
  statusKind?: 'info' | 'live' | 'win' | 'loss';
  mouseEvent?: string;
  blinkId?: number;
}
