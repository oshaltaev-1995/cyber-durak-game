import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  CARD_ACTIONS,
  CardActionType,
  DeckConfig,
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

  createGame(
    totalPlayers: 2 | 3 | 4 = 2,
    deckConfig: DeckConfig = { deck_profile: 'classic', deck_count: 1 },
  ): Observable<GameResponse> {
    const defaultDeck = deckConfig.deck_profile === 'classic' && deckConfig.deck_count === 1;
    const body =
      totalPlayers === 2 && defaultDeck
        ? null
        : {
            ...(totalPlayers === 2 ? {} : { total_players: totalPlayers }),
            ...(defaultDeck ? {} : deckConfig),
          };
    return this.http.post<GameResponse>(this.gamesUrl, body);
  }

  getGame(gameId: string): Observable<GameResponse> {
    return this.http.get<GameResponse>(`${this.gamesUrl}/${gameId}`);
  }

  restartGame(gameId: string): Observable<GameResponse> {
    return this.http.post<GameResponse>(`${this.gamesUrl}/${gameId}/restart`, null);
  }

  getHints(gameId: string, selectedPhysicalIds: readonly string[]): Observable<HintResponse> {
    return this.http.post<HintResponse>(`${this.gamesUrl}/${gameId}/hints`, {
      selected_physical_ids: selectedPhysicalIds,
    });
  }

  submitAction(
    gameId: string,
    action: HumanActionType,
    physicalCardIds: readonly string[] = [],
  ): Observable<GameResponse> {
    const request: HumanActionRequest = CARD_ACTIONS.has(action)
      ? { action: action as CardActionType, card_ids: physicalCardIds }
      : { action: action as 'TAKE' | 'BITO' };
    return this.http.post<GameResponse>(`${this.gamesUrl}/${gameId}/actions`, request);
  }
}
