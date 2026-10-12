import { Injectable } from '@angular/core';

const ACTIVE_BOT_GAME_ID_KEY = 'kiba.activeBotGameId';
const BOT_SETUP_REQUESTED_KEY = 'kiba.botSetupRequested';

@Injectable({ providedIn: 'root' })
export class BotGameSessionStore {
  save(gameId: string): void {
    const normalized = gameId.trim();
    if (normalized.length === 0) return;
    try {
      sessionStorage.setItem(ACTIVE_BOT_GAME_ID_KEY, normalized);
      sessionStorage.removeItem(BOT_SETUP_REQUESTED_KEY);
    } catch {
      // The current game remains usable when browser storage is unavailable.
    }
  }

  get(): string | null {
    try {
      const gameId = sessionStorage.getItem(ACTIVE_BOT_GAME_ID_KEY)?.trim() ?? '';
      if (gameId.length > 0) return gameId;
      this.clear();
    } catch {
      // Treat unavailable browser storage like an empty tab session.
    }
    return null;
  }

  clear(): void {
    try {
      sessionStorage.removeItem(ACTIVE_BOT_GAME_ID_KEY);
    } catch {
      // There is nothing else to clear when browser storage is unavailable.
    }
  }

  requestSetup(): void {
    try {
      sessionStorage.removeItem(ACTIVE_BOT_GAME_ID_KEY);
      sessionStorage.setItem(BOT_SETUP_REQUESTED_KEY, 'true');
    } catch {
      // The current page still returns to setup when browser storage is unavailable.
    }
  }

  setupRequested(): boolean {
    try {
      return sessionStorage.getItem(BOT_SETUP_REQUESTED_KEY) === 'true';
    } catch {
      return false;
    }
  }
}
