import type { JackpotInfo, PlayerPanelData, RoundPlayer, RoundResult } from './types';

// Development-only sample values. Replace with backend data.
export const SAMPLE_JACKPOTS: JackpotInfo[] = [
  { id: 'grand', label: 'GRAND JACKPOT', amount: 2000.45, color: '#d62bd6', icon: 'crown' },
  { id: 'major', label: 'MAJOR JACKPOT', amount: 1200.00, color: '#2a8cff', icon: 'diamond' },
  { id: 'global', label: 'GLOBAL JACKPOT', amount: 8167.39, color: '#ff8a1f', icon: 'globe' },
  { id: 'mini', label: 'MINI JACKPOT', amount: 5430.16, color: '#8a4bff', icon: 'star' },
  { id: 'minor', label: 'MINOR JACKPOT', amount: 851.67, color: '#2a6cff', icon: 'coins' },
];

export const SAMPLE_PLAYERS: PlayerPanelData[] = [
  { id: 1, balance: 0, bet: 10, color: '#f5b92a' },
  { id: 2, balance: 0, bet: 10, color: '#2e8bff' },
  { id: 3, balance: 0, bet: 10, color: '#ff4a1c' },
  { id: 4, balance: 0, bet: 10, color: '#9b4dff' },
  { id: 5, balance: 0, bet: 10, color: '#22d65a' },
];

export const SAMPLE_HISTORY: RoundResult[] = [
  3.42, 1.18, 2.56, 1.09, 6.21, 1.33, 2.07, 12.45, 1.78, 1.24,
  4.36, 1.11, 2.89, 1.03, 5.62, 1.26, 3.91, 1.19, 2.14, 8.37,
].map((multiplier, i) => ({ id: -(i + 1), multiplier }));

const BETS = [10, 20, 50, 10, 100, 30, 10, 200, 20, 10];
export const SAMPLE_ROUND_PLAYERS: RoundPlayer[] = Array.from({ length: 24 }, (_, i) => ({
  id: `sample-${i}`,
  name: `astro-${String(4594 + i * 137).padStart(5, '0')}`,
  bet: BETS[i % BETS.length],
}));
