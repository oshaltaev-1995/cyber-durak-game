import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { DeckConfig } from '../api/game-api.models';
import { KibaCapabilities, PvPRoomJoin, PvPRoomStatus } from './pvp.models';

@Injectable({ providedIn: 'root' })
export class PvPApiService {
  private readonly http = inject(HttpClient);

  getCapabilities(): Observable<KibaCapabilities> {
    return this.http.get<KibaCapabilities>('/api/capabilities');
  }

  createRoom(
    nickname: string | null,
    capacity: 2 | 3 | 4 = 2,
    deckConfig: DeckConfig = { deck_profile: 'classic', deck_count: 1 },
  ): Observable<PvPRoomJoin> {
    const defaultDeck = deckConfig.deck_profile === 'classic' && deckConfig.deck_count === 1;
    return this.http.post<PvPRoomJoin>('/api/pvp/rooms', {
      nickname,
      capacity,
      ...(defaultDeck ? {} : deckConfig),
    });
  }

  getRoom(inviteCode: string): Observable<PvPRoomStatus> {
    return this.http.get<PvPRoomStatus>(`/api/pvp/rooms/${encodeURIComponent(inviteCode)}`);
  }

  joinRoom(inviteCode: string, nickname: string | null): Observable<PvPRoomJoin> {
    return this.http.post<PvPRoomJoin>(`/api/pvp/rooms/${encodeURIComponent(inviteCode)}/join`, {
      nickname,
    });
  }
}
