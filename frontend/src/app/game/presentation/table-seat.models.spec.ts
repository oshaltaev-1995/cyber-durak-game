import { Seat } from '../../core/api/game-api.models';
import { relativeSeatPosition } from './table-seat.models';

describe('relativeSeatPosition', () => {
  const assertRing = (ring: readonly Seat[]): void => {
    ring.forEach((viewer) => {
      const mapping = Object.fromEntries(
        ring.map((seat) => [seat, relativeSeatPosition(ring, viewer, seat)]),
      );
      expect(mapping[viewer]).toBe('bottom');
      if (ring.length === 2) {
        expect(Object.values(mapping)).toEqual(expect.arrayContaining(['bottom', 'top']));
      } else if (ring.length === 3) {
        expect(relativeSeatPosition(ring, viewer, ring[(ring.indexOf(viewer) + 1) % 3])).toBe(
          'left',
        );
        expect(relativeSeatPosition(ring, viewer, ring[(ring.indexOf(viewer) + 2) % 3])).toBe(
          'top',
        );
      } else {
        expect(relativeSeatPosition(ring, viewer, ring[(ring.indexOf(viewer) + 1) % 4])).toBe(
          'left',
        );
        expect(relativeSeatPosition(ring, viewer, ring[(ring.indexOf(viewer) + 2) % 4])).toBe(
          'top',
        );
        expect(relativeSeatPosition(ring, viewer, ring[(ring.indexOf(viewer) + 3) % 4])).toBe(
          'right',
        );
      }
    });
  };

  it('rotates both two-player viewers to the bottom', () => {
    assertRing(['one', 'two']);
  });

  it('preserves the approved bottom-left-top three-player geometry for every viewer', () => {
    assertRing(['one', 'two', 'three']);
  });

  it('preserves clockwise bottom-left-top-right adjacency for every viewer', () => {
    assertRing(['one', 'two', 'three', 'four']);
  });
});
