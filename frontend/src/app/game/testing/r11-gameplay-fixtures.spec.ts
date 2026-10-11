import { describe, expect, it } from 'vitest';
import { R11_GAMEPLAY_FIXTURES } from './r11-gameplay-fixtures';

describe('R11 deterministic gameplay fixture matrix', () => {
  it('covers all twenty restored UX states with stable unique IDs', () => {
    expect(R11_GAMEPLAY_FIXTURES).toHaveLength(20);
    expect(new Set(R11_GAMEPLAY_FIXTURES.map((fixture) => fixture.id)).size).toBe(20);
    expect(R11_GAMEPLAY_FIXTURES.map((fixture) => fixture.id)).toEqual([
      'active-short-bout',
      'active-long-bout',
      'left-seat-large-hand',
      'right-seat-large-hand',
      'local-hand-20-plus',
      'local-hand-30-plus',
      'exposed-ordinary-source',
      'exposed-joker-source',
      'three-player-many-defenses',
      'partial-street',
      'partial-arithmetic',
      'long-bot-cascade',
      'human-turn-after-cascade',
      'attention-expired',
      'attention-reduced-motion',
      'terminal-three-player-tie',
      'terminal-four-player',
      'mixed-two-human-two-bot',
      'three-player-hints',
      'four-player-hints',
    ]);
  });
});
