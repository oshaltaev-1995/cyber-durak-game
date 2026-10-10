import { GameCard, JokerColor, SUIT_SYMBOLS } from '../core/api/game-api.models';

/** Format a public card for compact, player-facing presentation. */
export const formatCardShort = (
  card: GameCard,
  jokerName: (color: JokerColor) => string = (color) =>
    color === 'red' ? 'Red Joker' : 'Black Joker',
): string =>
  card.joker_color
    ? jokerName(card.joker_color)
    : `${card.rank}${card.suit === null ? '' : SUIT_SYMBOLS[card.suit]}`;
