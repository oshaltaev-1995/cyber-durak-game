import { Injectable } from '@angular/core';

const ACTIVE_BOT_GAME_ID_KEY = 'kiba.activeBotGameId';

@Injectable({ providedIn: 'root' })
export class BotGameSessionStore {
  save(gameId: string): void {
    const normalized = gameId.trim();
    if (normalized.length === 0) return;
    try {
      sessionStorage.setItem(ACTIVE_BOT_GAME_ID_KEY, normalized);
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
}
