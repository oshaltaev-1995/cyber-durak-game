import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { CurrentUser } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import { MatchStatistics, ProgressionSummary } from '../core/profile/profile.models';
import { ProfileService } from '../core/profile/profile.service';

@Component({
  selector: 'app-profile-page',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './profile-page.html',
  styleUrl: './auth-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfilePageComponent implements OnInit {
  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  protected readonly profile = inject(ProfileService);

  protected readonly pending = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal(false);
  protected readonly statistics = signal<MatchStatistics | null>(null);
  protected readonly statisticsPending = signal(false);
  protected readonly statisticsError = signal(false);
  protected readonly progression = signal<ProgressionSummary | null>(null);
  protected readonly progressionPending = signal(false);
  protected readonly progressionError = signal(false);
  protected readonly form = new FormGroup({
    display_name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(50)],
    }),
  });

  ngOnInit(): void {
    const current = this.auth.currentUser();
    if (current !== null) {
      this.loadUser(current);
      this.loadStatistics();
      this.loadProgression();
      return;
    }
    this.auth.refresh().subscribe((user) => {
      if (user !== null) {
        this.loadUser(user);
        this.loadStatistics();
        this.loadProgression();
      }
    });
  }

  protected save(): void {
    if (this.pending() || this.form.invalid || this.auth.currentUser() === null) {
      this.form.markAllAsTouched();
      return;
    }
    this.pending.set(true);
    this.error.set(null);
    this.success.set(false);
    this.auth
      .updateDisplayName(this.form.controls.display_name.value)
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (user) => {
          this.loadUser(user);
          this.success.set(true);
        },
        error: (error: unknown) => this.error.set(this.messageFor(error)),
      });
  }

  protected logout(): void {
    if (this.pending()) {
      return;
    }
    this.pending.set(true);
    this.auth
      .logout()
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: () => void this.router.navigateByUrl('/'),
        error: (error: unknown) => this.error.set(this.messageFor(error)),
      });
  }

  protected joinedAt(user: CurrentUser): string {
    return new Intl.DateTimeFormat('ru', { dateStyle: 'long' }).format(new Date(user.created_at));
  }

  protected winRate(value: number): string {
    return new Intl.NumberFormat('ru', { maximumFractionDigits: 1 }).format(value);
  }

  private loadUser(user: CurrentUser): void {
    this.form.controls.display_name.setValue(user.display_name);
  }

  private loadStatistics(): void {
    this.statisticsPending.set(true);
    this.statisticsError.set(false);
    this.profile
      .getStatistics()
      .pipe(finalize(() => this.statisticsPending.set(false)))
      .subscribe({
        next: (statistics) => this.statistics.set(statistics),
        error: () => this.statisticsError.set(true),
      });
  }

  private loadProgression(): void {
    this.progressionPending.set(true);
    this.progressionError.set(false);
    this.profile
      .getProgression()
      .pipe(finalize(() => this.progressionPending.set(false)))
      .subscribe({
        next: (progression) => this.progression.set(progression),
        error: () => this.progressionError.set(true),
      });
  }

  private messageFor(error: unknown): string {
    if (error instanceof HttpErrorResponse && error.status === 401) {
      return 'Сессия завершилась. Войдите снова.';
    }
    return 'Не удалось сохранить профиль. Попробуйте снова.';
  }
}
