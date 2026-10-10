import {
  DeckVariantsOnboardingStore,
  KIBA_DECK_VARIANTS_ONBOARDING_KEY,
} from './deck-variants-onboarding.store';

describe('DeckVariantsOnboardingStore', () => {
  beforeEach(() => localStorage.removeItem(KIBA_DECK_VARIANTS_ONBOARDING_KEY));

  it('versions first-use deck guidance independently from multiplayer guidance', () => {
    const store = new DeckVariantsOnboardingStore();
    expect(store.hasSeen()).toBe(false);
    store.markSeen();
    expect(store.hasSeen()).toBe(true);
    expect(KIBA_DECK_VARIANTS_ONBOARDING_KEY).not.toBe('kiba.multiplayerOnboarding.v1');
  });
});
