import { Injectable, signal } from '@angular/core';

export const KIBA_HINTS_ENABLED_KEY = 'kiba.hintsEnabled';

@Injectable({ providedIn: 'root' })
export class HintPreferenceService {
  readonly enabled = signal(this.readPreference());

  setEnabled(enabled: boolean): void {
    this.enabled.set(enabled);
    localStorage.setItem(KIBA_HINTS_ENABLED_KEY, String(enabled));
  }

  private readPreference(): boolean {
    return localStorage.getItem(KIBA_HINTS_ENABLED_KEY) !== 'false';
  }
}
