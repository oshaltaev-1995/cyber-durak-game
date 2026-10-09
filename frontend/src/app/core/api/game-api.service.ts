import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  CARD_ACTIONS,
  CardActionType,
  GameResponse,
  HintResponse,
  HumanActionRequest,
  HumanActionType,
  KibaCapabilities,
} from './game-api.models';

@Injectable({ providedIn: 'root' })
export class GameApiService {
  private readonly http = inject(HttpClient);
  private readonly gamesUrl = '/api/games';

  getCapabilities(): Observable<KibaCapabilities> {
    return this.http.get<KibaCapabilities>('/api/capabilities');
  }

  createGame(totalPlayers: 2 | 3 | 4 = 2): Observable<GameResponse> {
    return this.http.post<GameResponse>(
      this.gamesUrl,
      totalPlayers === 2 ? null : { total_players: totalPlayers },
    );
  }

  getGame(gameId: string): Observable<GameResponse> {
    return this.http.get<GameResponse>(`${this.gamesUrl}/${gameId}`);
  }

  restartGame(gameId: string): Observable<GameResponse> {
    return this.http.post<GameResponse>(`${this.gamesUrl}/${gameId}/restart`, null);
  }

  getHints(gameId: string, selectedCardIds: readonly string[]): Observable<HintResponse> {
    return this.http.post<HintResponse>(`${this.gamesUrl}/${gameId}/hints`, {
      selected_card_ids: selectedCardIds,
    });
  }

  submitAction(
    gameId: string,
    action: HumanActionType,
    cardCodes: readonly string[] = [],
  ): Observable<GameResponse> {
    const request: HumanActionRequest = CARD_ACTIONS.has(action)
      ? { action: action as CardActionType, cards: cardCodes }
      : { action: action as 'TAKE' | 'BITO' };
    return this.http.post<GameResponse>(`${this.gamesUrl}/${gameId}/actions`, request);
  }
}
