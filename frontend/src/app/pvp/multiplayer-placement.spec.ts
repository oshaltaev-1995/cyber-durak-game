import { deriveMultiplayerPlacements } from './multiplayer-placement';

describe('deriveMultiplayerPlacements', () => {
  it.each([
    [
      [['one'], ['two'], ['three'], ['four']],
      [1, 2, 3, 4],
    ],
    [
      [['one', 'two'], ['three'], ['four']],
      [1, 1, 3, 4],
    ],
    [
      [['one'], ['two', 'three'], ['four']],
      [1, 2, 2, 4],
    ],
    [
      [['one'], ['two'], ['three', 'four']],
      [1, 2, 3, 3],
    ],
    [[['one', 'two', 'three', 'four']], [1, 1, 1, 1]],
  ] as const)('uses standard competition ranking for %j', (groups, expected) => {
    expect(deriveMultiplayerPlacements(groups)).toEqual(
      groups.flatMap((group, groupIndex) =>
        group.map((seat) => ({
          seat,
          rank: expected[groups.slice(0, groupIndex).flat().length],
        })),
      ),
    );
  });
});
