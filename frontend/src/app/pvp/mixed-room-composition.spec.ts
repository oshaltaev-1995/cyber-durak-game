import { humanPlayerOptions, nextHumanPlayerCount } from './mixed-room-composition';

describe('mixed room composition', () => {
  it('offers only valid human counts for each table size', () => {
    expect(humanPlayerOptions(2)).toEqual([2]);
    expect(humanPlayerOptions(3)).toEqual([2, 3]);
    expect(humanPlayerOptions(4)).toEqual([2, 3, 4]);
  });

  it('keeps all-human selections all-human when the table size changes', () => {
    expect(nextHumanPlayerCount(3, 3, 4)).toBe(4);
    expect(nextHumanPlayerCount(4, 4, 3)).toBe(3);
    expect(nextHumanPlayerCount(3, 3, 2)).toBe(2);
  });

  it('preserves or clamps an explicitly mixed human count', () => {
    expect(nextHumanPlayerCount(4, 2, 3)).toBe(2);
    expect(nextHumanPlayerCount(3, 2, 4)).toBe(2);
    expect(nextHumanPlayerCount(4, 3, 2)).toBe(2);
  });
});
