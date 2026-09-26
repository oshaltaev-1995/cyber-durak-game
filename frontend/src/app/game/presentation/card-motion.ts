import { Injectable, signal } from '@angular/core';
import { GameCard, HumanActionType } from '../../core/api/game-api.models';

export type MotionAnchor = 'top' | 'bottom' | 'left' | 'right' | 'table' | 'deck' | 'discard';

export interface CardMotion {
  readonly id: string;
  readonly from: MotionAnchor;
  readonly to: MotionAnchor;
  readonly card: GameCard | null;
  readonly startsHidden: boolean;
  readonly endsHidden: boolean;
  readonly delayMs: number;
}

export interface MotionSnapshot {
  readonly localHand: readonly GameCard[];
  readonly opponentHandCount: number;
  readonly drawPileCount: number;
  readonly discardCount: number;
  readonly tableCards: readonly GameCard[];
}

export interface MotionContext {
  readonly localAction?: HumanActionType;
  readonly localCards?: readonly GameCard[];
  readonly remoteCardCount?: number;
  readonly remotePlayedCards?: readonly GameCard[];
  readonly resolvedTo?: 'local' | 'opponent' | 'discard';
  readonly refillOrder?: 'local-first' | 'opponent-first';
}

const CARD_ACTIONS = new Set<HumanActionType>(['INITIAL_ATTACK', 'DEFEND', 'TRANSFER', 'THROW_IN']);

let sequence = 0;

export function planCardMotions(
  previous: MotionSnapshot,
  next: MotionSnapshot,
  context: MotionContext,
): readonly CardMotion[] {
  const motions: CardMotion[] = [];
  const batch = ++sequence;
  const push = (
    from: MotionAnchor,
    to: MotionAnchor,
    card: GameCard | null,
    startsHidden: boolean,
    endsHidden: boolean,
    phase: number,
    index: number,
  ): void => {
    motions.push({
      id: `${batch}-${phase}-${index}-${from}-${to}-${card?.code ?? 'hidden'}`,
      from,
      to,
      card,
      startsHidden,
      endsHidden,
      delayMs: phase * 180 + index * 55,
    });
  };

  const localCards = context.localCards ?? [];
  if (context.localAction !== undefined && CARD_ACTIONS.has(context.localAction)) {
    localCards.forEach((card, index) => push('bottom', 'table', card, false, false, 0, index));
  }

  const remoteCards = context.remotePlayedCards ?? [];
  const remoteCount = Math.max(context.remoteCardCount ?? remoteCards.length, remoteCards.length);
  for (let index = 0; index < remoteCount; index += 1) {
    push('top', 'table', remoteCards[index] ?? null, true, false, 0, index);
  }

  if (previous.tableCards.length > 0 && context.resolvedTo) {
    const destination =
      context.resolvedTo === 'local'
        ? 'bottom'
        : context.resolvedTo === 'opponent'
          ? 'top'
          : 'discard';
    const resolvedCards = [...previous.tableCards, ...localCards].filter(
      (card, index, cards) =>
        cards.findIndex((candidate) => candidate.code === card.code) === index,
    );
    resolvedCards.forEach((card, index) =>
      push('table', destination, card, false, destination === 'top', 1, index),
    );
  }

  const drawn = Math.max(0, previous.drawPileCount - next.drawPileCount);
  if (drawn > 0) {
    const previousCodes = new Set(previous.localHand.map((card) => card.code));
    const tableCodes = new Set(previous.tableCards.map((card) => card.code));
    const localArrivals = next.localHand.filter(
      (card) => !previousCodes.has(card.code) && !tableCodes.has(card.code),
    );
    const localDrawCount = Math.min(drawn, localArrivals.length);
    const opponentDrawCount = drawn - localDrawCount;
    const localFirst = context.refillOrder !== 'opponent-first';
    const localOffset = localFirst ? 0 : opponentDrawCount;
    const opponentOffset = localFirst ? localDrawCount : 0;
    localArrivals
      .slice(0, localDrawCount)
      .forEach((card, index) => push('deck', 'bottom', card, true, false, 2, index + localOffset));
    for (let index = 0; index < opponentDrawCount; index += 1) {
      push('deck', 'top', null, true, true, 2, index + opponentOffset);
    }
  }

  return motions;
}

@Injectable()
export class CardMotionController {
  readonly motions = signal<readonly CardMotion[]>([]);
  private clearTimer: ReturnType<typeof setTimeout> | null = null;

  play(motions: readonly CardMotion[]): void {
    this.clear();
    if (motions.length === 0 || this.prefersReducedMotion()) return;
    this.motions.set(motions);
    const longestDelay = Math.max(...motions.map((motion) => motion.delayMs));
    this.clearTimer = setTimeout(() => {
      this.clearTimer = null;
      this.motions.set([]);
    }, longestDelay + 620);
  }

  clear(): void {
    if (this.clearTimer !== null) clearTimeout(this.clearTimer);
    this.clearTimer = null;
    this.motions.set([]);
  }

  private prefersReducedMotion(): boolean {
    return (
      typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
    );
  }
}
