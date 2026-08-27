import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  Achievement,
  MatchHistoryResponse,
  MatchStatistics,
  ProgressionSummary,
} from './profile.models';

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

  getProgression(): Observable<ProgressionSummary> {
    return this.http.get<ProgressionSummary>('/api/progression');
  }

  getAchievements(): Observable<readonly Achievement[]> {
    return this.http.get<readonly Achievement[]>('/api/achievements');
  }
}
