import { Injectable } from '@angular/core';

export const KIBA_MULTIPLAYER_ONBOARDING_KEY = 'kiba.multiplayerOnboarding.v1';

@Injectable({ providedIn: 'root' })
export class MultiplayerOnboardingStore {
  hasSeen(): boolean {
    return localStorage.getItem(KIBA_MULTIPLAYER_ONBOARDING_KEY) === 'true';
  }

  markSeen(): void {
    localStorage.setItem(KIBA_MULTIPLAYER_ONBOARDING_KEY, 'true');
  }
}
