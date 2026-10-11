/** Stable R11 visual-state matrix used by component tests and manual viewport review. */
export const R11_GAMEPLAY_FIXTURES = [
  { id: 'active-short-bout', players: 2, packets: 1, hand: 7 },
  { id: 'active-long-bout', players: 2, packets: 12, hand: 14 },
  { id: 'left-seat-large-hand', players: 3, packets: 3, hand: 7, leftHand: 24 },
  { id: 'right-seat-large-hand', players: 4, packets: 3, hand: 7, rightHand: 24 },
  { id: 'local-hand-20-plus', players: 2, packets: 2, hand: 24 },
  { id: 'local-hand-30-plus', players: 2, packets: 2, hand: 32 },
  { id: 'exposed-ordinary-source', players: 2, packets: 1, hand: 7, source: 'ordinary' },
  { id: 'exposed-joker-source', players: 2, packets: 1, hand: 7, source: 'joker' },
  { id: 'three-player-many-defenses', players: 3, packets: 1, hand: 8, hints: true },
  { id: 'partial-street', players: 2, packets: 0, hand: 7, hints: true },
  { id: 'partial-arithmetic', players: 2, packets: 0, hand: 7, hints: true },
  { id: 'long-bot-cascade', players: 4, packets: 5, hand: 7, botEvents: 8 },
  { id: 'human-turn-after-cascade', players: 4, packets: 5, hand: 7, botEvents: 4 },
  { id: 'attention-expired', players: 2, packets: 1, hand: 7, attention: true },
  { id: 'attention-reduced-motion', players: 2, packets: 1, hand: 7, attention: true },
  { id: 'terminal-three-player-tie', players: 3, packets: 5, hand: 0, terminal: true },
  { id: 'terminal-four-player', players: 4, packets: 8, hand: 0, terminal: true },
  { id: 'mixed-two-human-two-bot', players: 4, packets: 4, hand: 12 },
  { id: 'three-player-hints', players: 3, packets: 2, hand: 14, hints: true },
  { id: 'four-player-hints', players: 4, packets: 2, hand: 14, hints: true },
] as const;

export type R11GameplayFixture = (typeof R11_GAMEPLAY_FIXTURES)[number];
