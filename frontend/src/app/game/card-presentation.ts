import { GameCard, SUIT_SYMBOLS } from '../core/api/game-api.models';

/** Format a public card for compact, player-facing presentation. */
export const formatCardShort = (card: GameCard): string => `${card.rank}${SUIT_SYMBOLS[card.suit]}`;
