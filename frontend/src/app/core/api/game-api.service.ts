import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  CARD_ACTIONS,
  CardActionType,
  GameResponse,
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
