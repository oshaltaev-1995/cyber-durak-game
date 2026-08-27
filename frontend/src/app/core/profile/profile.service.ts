import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { MatchHistoryResponse, MatchStatistics } from './profile.models';

@Injectable({ providedIn: 'root' })
export class ProfileService {
  private readonly http = inject(HttpClient);

  getStatistics(): Observable<MatchStatistics> {
    return this.http.get<MatchStatistics>('/api/stats');
  }

  getMatches(limit = 20, offset = 0): Observable<MatchHistoryResponse> {
    return this.http.get<MatchHistoryResponse>('/api/matches', {
      params: { limit, offset },
    });
  }
}
