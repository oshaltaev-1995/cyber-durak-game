import { DeckConfig, DeckCount, DeckProfile } from '../api/game-api.models';

export const DEFAULT_DECK_CONFIG: DeckConfig = {
  deck_profile: 'classic',
  deck_count: 1,
};

export function deckCardCount(profile: DeckProfile, deckCount: DeckCount): number {
  return (profile === 'classic' ? 36 : 54) * deckCount;
}

export function isDefaultDeckConfig(config: DeckConfig): boolean {
  return config.deck_profile === 'classic' && config.deck_count === 1;
}

export function cardIdentity(card: { readonly id?: string; readonly code: string }): string {
  return card.id ?? card.code;
}
