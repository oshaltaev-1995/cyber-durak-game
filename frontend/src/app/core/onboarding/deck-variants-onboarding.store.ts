import { Injectable } from '@angular/core';

export const KIBA_DECK_VARIANTS_ONBOARDING_KEY = 'kiba.deckVariantsOnboarding.v1';

@Injectable({ providedIn: 'root' })
export class DeckVariantsOnboardingStore {
  hasSeen(): boolean {
    return localStorage.getItem(KIBA_DECK_VARIANTS_ONBOARDING_KEY) === 'true';
  }

  markSeen(): void {
    localStorage.setItem(KIBA_DECK_VARIANTS_ONBOARDING_KEY, 'true');
  }
}
