import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../core/auth/auth.service';
import { Achievement } from '../core/profile/profile.models';
import { ProfileService } from '../core/profile/profile.service';

@Component({
  selector: 'app-achievements-page',
  imports: [RouterLink],
  templateUrl: './achievements-page.html',
  styleUrl: './achievements-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AchievementsPageComponent implements OnInit {
  protected readonly auth = inject(AuthService);
  private readonly profile = inject(ProfileService);

  protected readonly achievements = signal<readonly Achievement[]>([]);
  protected readonly pending = signal(false);
  protected readonly error = signal(false);

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

  protected unlockedAt(value: string): string {
    return new Intl.DateTimeFormat('ru', { dateStyle: 'long' }).format(new Date(value));
  }

  private load(): void {
    this.pending.set(true);
    this.error.set(false);
    this.profile
      .getAchievements()
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (achievements) => this.achievements.set(achievements),
        error: () => this.error.set(true),
      });
  }
}
