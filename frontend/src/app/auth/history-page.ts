import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../core/auth/auth.service';
import { MatchHistoryItem } from '../core/profile/profile.models';
import { ProfileService } from '../core/profile/profile.service';

@Component({
  selector: 'app-history-page',
  imports: [RouterLink],
  templateUrl: './history-page.html',
  styleUrl: './history-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HistoryPageComponent implements OnInit {
  protected readonly auth = inject(AuthService);
  private readonly profile = inject(ProfileService);

  protected readonly matches = signal<readonly MatchHistoryItem[]>([]);
  protected readonly total = signal(0);
  protected readonly pending = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly filter = signal<'ALL' | 'BOT' | 'PVP'>('ALL');

  ngOnInit(): void {
    if (this.auth.currentUser() !== null) {
      this.load();
      return;
    }
    this.auth.refresh().subscribe((user) => {
      if (user !== null) {
        this.load();
      }
    });
  }

  protected outcomeLabel(outcome: MatchHistoryItem['outcome']): string {
    return { WIN: 'Победа', LOSS: 'Поражение', DRAW: 'Ничья' }[outcome];
  }

  protected completedAt(value: string): string {
    return new Intl.DateTimeFormat('ru', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value));
  }

  protected duration(seconds: number): string {
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds % 60;
    return minutes > 0 ? `${minutes} мин ${remainder} сек` : `${remainder} сек`;
  }

  protected opponentLabel(match: MatchHistoryItem): string {
    return match.opponent_type === 'PVP'
      ? `против ${match.opponent_display_name ?? 'игрока'}`
      : 'против бота';
  }

  protected setFilter(filter: 'ALL' | 'BOT' | 'PVP'): void {
    if (this.filter() === filter) return;
    this.filter.set(filter);
    this.load();
  }

  private load(): void {
    this.pending.set(true);
    this.error.set(null);
    const selectedFilter = this.filter();
    this.profile
      .getMatches(20, 0, selectedFilter === 'ALL' ? null : selectedFilter)
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (response) => {
          this.matches.set(response.items);
          this.total.set(response.total);
        },
        error: (error: unknown) => {
          this.error.set(
            error instanceof HttpErrorResponse && error.status === 401
              ? 'Войдите, чтобы посмотреть историю.'
              : 'Не удалось загрузить историю партий.',
          );
        },
      });
  }
}
