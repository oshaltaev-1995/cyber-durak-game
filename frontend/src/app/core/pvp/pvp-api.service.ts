import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { PvPRoomJoin, PvPRoomStatus } from './pvp.models';

@Injectable({ providedIn: 'root' })
export class PvPApiService {
  private readonly http = inject(HttpClient);

  createRoom(nickname: string | null): Observable<PvPRoomJoin> {
    return this.http.post<PvPRoomJoin>('/api/pvp/rooms', { nickname });
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
