import { Injectable } from '@angular/core';

export const KIBA_FIRST_RUN_SEEN_KEY = 'kiba.firstRunSeen';

@Injectable({ providedIn: 'root' })
export class FirstRunStore {
  hasSeenWelcome(): boolean {
    return localStorage.getItem(KIBA_FIRST_RUN_SEEN_KEY) === 'true';
  }

  markWelcomeSeen(): void {
    localStorage.setItem(KIBA_FIRST_RUN_SEEN_KEY, 'true');
  }
}
