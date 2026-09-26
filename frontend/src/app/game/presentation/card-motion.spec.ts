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
  opponentHandCount: 7,
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

  it('moves a hidden opponent card toward the table and reveals only its public face', () => {
    const motions = planCardMotions(snapshot(), snapshot({ tableCards: [eight] }), {
      remoteCardCount: 1,
      remotePlayedCards: [eight],
    });

    expect(motions[0]).toEqual(
      expect.objectContaining({
        from: 'top',
        to: 'table',
        card: eight,
        startsHidden: true,
        endsHidden: false,
      }),
    );
  });

  it('moves TAKE cards toward the defender and BITO cards toward discard', () => {
    const previous = snapshot({ tableCards: [six, seven] });
    const take = planCardMotions(previous, snapshot({ tableCards: [] }), {
      resolvedTo: 'opponent',
    });
    const bito = planCardMotions(previous, snapshot({ tableCards: [], discardCount: 2 }), {
      resolvedTo: 'discard',
    });

    expect(take.filter((motion) => motion.from === 'table' && motion.to === 'top')).toHaveLength(2);
    expect(take.every((motion) => motion.card !== null && motion.endsHidden)).toBe(true);
    expect(bito.filter((motion) => motion.to === 'discard')).toHaveLength(2);
  });

  it('stages authoritative refill in the supplied engine order', () => {
    const previous = snapshot({ localHand: [six], drawPileCount: 4 });
    const next = snapshot({ localHand: [six, seven], opponentHandCount: 8, drawPileCount: 2 });
    const motions = planCardMotions(previous, next, { refillOrder: 'opponent-first' });
    const refill = motions
      .filter((motion) => motion.from === 'deck')
      .sort((left, right) => left.delayMs - right.delayMs);

    expect(refill).toHaveLength(2);
    expect(refill[0].to).toBe('top');
    expect(refill[1].to).toBe('bottom');
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
