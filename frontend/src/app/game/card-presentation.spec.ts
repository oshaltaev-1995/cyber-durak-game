import { GameCard, Suit } from '../core/api/game-api.models';
import { formatCardShort } from './card-presentation';

const card = (code: string, rank: string, suit: Suit): GameCard => ({
  code,
  rank,
  suit,
  base_value: 0,
  effective_value: 0,
  is_trump: false,
});

describe('formatCardShort', () => {
  it.each([
    ['JD', 'J', 'diamonds', 'J♦'],
    ['QD', 'Q', 'diamonds', 'Q♦'],
    ['10H', '10', 'hearts', '10♥'],
    ['AS', 'A', 'spades', 'A♠'],
  ] as const)('formats %s with a player-facing suit symbol', (code, rank, suit, expected) => {
    expect(formatCardShort(card(code, rank, suit))).toBe(expected);
  });
});
