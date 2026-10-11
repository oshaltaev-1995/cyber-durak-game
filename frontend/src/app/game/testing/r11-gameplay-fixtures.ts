/** Stable R11 visual-state matrix used by component tests and manual viewport review. */
export const R11_GAMEPLAY_FIXTURES = [
  { id: 'active-short-bout', players: 2, packets: 1, hand: 7 },
  { id: 'active-long-bout', players: 2, packets: 12, hand: 14 },
  { id: 'local-hand-20-plus', players: 2, packets: 2, hand: 24 },
  { id: 'multi-packet-defense', players: 2, packets: 6, hand: 14 },
  { id: 'four-player-table', players: 4, packets: 3, hand: 7 },
  { id: 'mixed-two-human-two-bot', players: 4, packets: 4, hand: 12 },
  { id: 'terminal-three-player-tie', players: 3, packets: 5, hand: 0, terminal: true },
  { id: 'terminal-four-player', players: 4, packets: 8, hand: 0, terminal: true },
  { id: 'exposed-ordinary-source', players: 2, packets: 1, hand: 7, source: 'ordinary' },
  { id: 'exposed-joker-source', players: 2, packets: 1, hand: 7, source: 'joker' },
  { id: 'consecutive-bot-cascade', players: 4, packets: 5, hand: 7, botEvents: 6 },
  { id: 'human-turn-after-cascade', players: 4, packets: 5, hand: 7, botEvents: 4 },
  { id: 'multiplayer-hints', players: 4, packets: 2, hand: 14, hints: true },
] as const;

export type R11GameplayFixture = (typeof R11_GAMEPLAY_FIXTURES)[number];
