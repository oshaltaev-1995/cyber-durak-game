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
} from './game-api.models';

@Injectable({ providedIn: 'root' })
export class GameApiService {
  private readonly http = inject(HttpClient);
  private readonly gamesUrl = '/api/games';

  createGame(): Observable<GameResponse> {
    return this.http.post<GameResponse>(this.gamesUrl, null);
  }

  getGame(gameId: string): Observable<GameResponse> {
    return this.http.get<GameResponse>(`${this.gamesUrl}/${gameId}`);
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
