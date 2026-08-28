import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import {
  Achievement,
  CosmeticEquipRequest,
  CosmeticLoadout,
  CosmeticsResponse,
  DEFAULT_COSMETIC_LOADOUT,
  MatchHistoryResponse,
  MatchStatistics,
  ProgressionSummary,
} from './profile.models';

@Injectable({ providedIn: 'root' })
export class ProfileService {
  private readonly http = inject(HttpClient);
  readonly currentLoadout = signal<CosmeticLoadout>(DEFAULT_COSMETIC_LOADOUT);

  getStatistics(): Observable<MatchStatistics> {
    return this.http.get<MatchStatistics>('/api/stats');
  }

  getMatches(
    limit = 20,
    offset = 0,
    opponentType: 'BOT' | 'PVP' | null = null,
  ): Observable<MatchHistoryResponse> {
    return this.http.get<MatchHistoryResponse>('/api/matches', {
      params: {
        limit,
        offset,
        ...(opponentType === null ? {} : { opponent_type: opponentType }),
      },
    });
  }

  getProgression(): Observable<ProgressionSummary> {
    return this.http.get<ProgressionSummary>('/api/progression');
  }

  getAchievements(): Observable<readonly Achievement[]> {
    return this.http.get<readonly Achievement[]>('/api/achievements');
  }

  getCosmetics(): Observable<CosmeticsResponse> {
    return this.http
      .get<CosmeticsResponse>('/api/cosmetics')
      .pipe(tap((response) => this.currentLoadout.set(response.loadout)));
  }

  equipCosmetics(request: CosmeticEquipRequest): Observable<CosmeticsResponse> {
    return this.http
      .patch<CosmeticsResponse>('/api/profile/cosmetics', request)
      .pipe(tap((response) => this.currentLoadout.set(response.loadout)));
  }

  resetCosmetics(): void {
    this.currentLoadout.set(DEFAULT_COSMETIC_LOADOUT);
  }
}
