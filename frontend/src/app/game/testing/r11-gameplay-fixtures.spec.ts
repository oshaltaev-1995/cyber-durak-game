import { describe, expect, it } from 'vitest';
import { R11_GAMEPLAY_FIXTURES } from './r11-gameplay-fixtures';

describe('R11 deterministic gameplay fixture matrix', () => {
  it('covers all thirteen restored UX states with stable unique IDs', () => {
    expect(R11_GAMEPLAY_FIXTURES).toHaveLength(13);
    expect(new Set(R11_GAMEPLAY_FIXTURES.map((fixture) => fixture.id)).size).toBe(13);
    expect(R11_GAMEPLAY_FIXTURES.map((fixture) => fixture.id)).toEqual([
      'active-short-bout',
      'active-long-bout',
      'local-hand-20-plus',
      'multi-packet-defense',
      'four-player-table',
      'mixed-two-human-two-bot',
      'terminal-three-player-tie',
      'terminal-four-player',
      'exposed-ordinary-source',
      'exposed-joker-source',
      'consecutive-bot-cascade',
      'human-turn-after-cascade',
      'multiplayer-hints',
    ]);
  });
});
