import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { KibaCapabilities, PvPRoomJoin, PvPRoomStatus } from './pvp.models';

@Injectable({ providedIn: 'root' })
export class PvPApiService {
  private readonly http = inject(HttpClient);

  getCapabilities(): Observable<KibaCapabilities> {
    return this.http.get<KibaCapabilities>('/api/capabilities');
  }

  createRoom(nickname: string | null, capacity: 2 | 3 | 4 = 2): Observable<PvPRoomJoin> {
    return this.http.post<PvPRoomJoin>('/api/pvp/rooms', { nickname, capacity });
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
