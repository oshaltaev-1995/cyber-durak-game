import { GameCard } from '../../core/api/game-api.models';
import { CardMotionController, MotionSnapshot, planCardMotions } from './card-motion';

const card = (code: string): GameCard => ({
  code,
  rank: code.slice(0, -1),
  suit: 'clubs',
  base_value: 6,
  effective_value: 6,
  is_trump: false,
});

const six = card('6C');
const seven = card('7C');
const eight = card('8C');

const snapshot = (overrides: Partial<MotionSnapshot> = {}): MotionSnapshot => ({
  localHand: [six, seven],
  remoteHands: { top: 7 },
  drawPileCount: 20,
  discardCount: 0,
  tableCards: [],
  ...overrides,
});

describe('card motion presentation planning', () => {
  it.each(['INITIAL_ATTACK', 'DEFEND', 'TRANSFER', 'THROW_IN'] as const)(
    'moves accepted local %s cards from the bottom hand to the table',
    (action) => {
      const motions = planCardMotions(snapshot(), snapshot({ localHand: [seven] }), {
        localAction: action,
        localCards: [six],
      });

      expect(motions).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ from: 'bottom', to: 'table', card: six }),
        ]),
      );
    },
  );

  it.each(['left', 'top', 'right'] as const)(
    'moves a hidden %s opponent card toward the table and reveals only its public face',
    (remoteFrom) => {
      const motions = planCardMotions(snapshot(), snapshot({ tableCards: [eight] }), {
        remoteCardCount: 1,
        remotePlayedCards: [eight],
        remoteFrom,
      });

      expect(motions[0]).toEqual(
        expect.objectContaining({
          from: remoteFrom,
          to: 'table',
          card: eight,
          startsHidden: true,
          endsHidden: false,
        }),
      );
    },
  );

  it('orders consecutive remote plays from their distinct stable seats', () => {
    const motions = planCardMotions(snapshot(), snapshot({ tableCards: [seven, eight] }), {
      remotePlays: [
        { from: 'left', count: 1, cards: [seven] },
        { from: 'right', count: 1, cards: [eight] },
      ],
    });

    expect(motions.map((motion) => motion.from)).toEqual(['left', 'right']);
    expect(motions.map((motion) => motion.card)).toEqual([seven, eight]);
    expect(motions[1].delayMs).toBeGreaterThan(motions[0].delayMs);
  });

  it.each(['left', 'top', 'right', 'bottom'] as const)(
    'moves TAKE cards toward a %s defender',
    (resolvedTo) => {
      const previous = snapshot({ tableCards: [six, seven] });
      const take = planCardMotions(previous, snapshot({ tableCards: [] }), { resolvedTo });

      expect(
        take.filter((motion) => motion.from === 'table' && motion.to === resolvedTo),
      ).toHaveLength(2);
      expect(take.every((motion) => motion.card !== null)).toBe(true);
      expect(take.every((motion) => motion.endsHidden)).toBe(resolvedTo !== 'bottom');
    },
  );

  it('moves BITO cards toward discard', () => {
    const previous = snapshot({ tableCards: [six, seven] });
    const bito = planCardMotions(previous, snapshot({ tableCards: [], discardCount: 2 }), {
      resolvedTo: 'discard',
    });

    expect(bito.filter((motion) => motion.to === 'discard')).toHaveLength(2);
  });

  it('keeps exact visual duplicates as separate motion identities', () => {
    const first = { ...card('KH'), id: 'deck-1:KH', rank: 'K', suit: 'hearts' as const };
    const second = { ...card('KH'), id: 'deck-2:KH', rank: 'K', suit: 'hearts' as const };
    const previous = snapshot({ tableCards: [first, second] });
    const motions = planCardMotions(previous, snapshot({ tableCards: [] }), {
      resolvedTo: 'discard',
    });

    expect(motions).toHaveLength(2);
    expect(motions.map((motion) => motion.card?.id)).toEqual(['deck-1:KH', 'deck-2:KH']);
    expect(new Set(motions.map((motion) => motion.id)).size).toBe(2);
  });

  it('stages authoritative refill deltas toward every participant position', () => {
    const previous = snapshot({ localHand: [six], drawPileCount: 4 });
    const next = snapshot({
      localHand: [six, seven],
      remoteHands: { left: 1, top: 7, right: 1 },
      drawPileCount: 1,
    });
    const motions = planCardMotions(previous, next, {});
    const refill = motions
      .filter((motion) => motion.from === 'deck')
      .sort((left, right) => left.delayMs - right.delayMs);

    expect(refill.map((motion) => motion.to)).toEqual(['bottom', 'left', 'right']);
  });

  it('does not produce a play animation without an accepted transition context', () => {
    expect(planCardMotions(snapshot(), snapshot(), {})).toEqual([]);
  });
});

describe('CardMotionController', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('suppresses flight animation for reduced-motion users', () => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({ matches: true })),
    );
    const controller = new CardMotionController();
    const planned = planCardMotions(snapshot(), snapshot(), {
      localAction: 'INITIAL_ATTACK',
      localCards: [six],
    });

    controller.play(planned);
    expect(controller.motions()).toEqual([]);
  });
});
