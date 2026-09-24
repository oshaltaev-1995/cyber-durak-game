import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { CurrentUser } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import { MatchStatistics, ProgressionSummary } from '../core/profile/profile.models';
import { ProfileService } from '../core/profile/profile.service';
import { TranslationService } from '../core/i18n/translation.service';

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
  protected readonly i18n = inject(TranslationService);

  protected readonly pending = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal(false);
  protected readonly securityMessage = signal<string | null>(null);
  protected readonly statistics = signal<MatchStatistics | null>(null);
  protected readonly statisticsPending = signal(false);
  protected readonly statisticsError = signal(false);
  protected readonly progression = signal<ProgressionSummary | null>(null);
  protected readonly progressionPending = signal(false);
  protected readonly progressionError = signal(false);
  protected readonly exportPending = signal(false);
  protected readonly exportError = signal(false);
  protected readonly deleteOpen = signal(false);
  protected readonly deletePending = signal(false);
  protected readonly deleteError = signal<string | null>(null);
  protected readonly form = new FormGroup({
    display_name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(50)],
    }),
  });
  protected readonly deleteForm = new FormGroup({
    password: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required],
    }),
    confirmed: new FormControl(false, {
      nonNullable: true,
      validators: [Validators.requiredTrue],
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

  protected logoutAll(): void {
    if (this.pending()) return;
    this.pending.set(true);
    this.auth
      .logoutAll()
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: () => void this.router.navigateByUrl('/'),
        error: (error: unknown) => this.error.set(this.messageFor(error)),
      });
  }

  protected resendVerification(): void {
    if (this.pending()) return;
    this.pending.set(true);
    this.securityMessage.set(null);
    this.auth
      .sendVerification()
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (value) =>
          this.securityMessage.set(
            value.message === 'already_verified'
              ? this.i18n.t('profile.alreadyVerified')
              : this.i18n.t('profile.verificationSent'),
          ),
        error: () => this.error.set(this.i18n.t('profile.verificationFailed')),
      });
  }

  protected downloadData(): void {
    if (this.exportPending()) return;
    this.exportPending.set(true);
    this.exportError.set(false);
    this.auth
      .exportData()
      .pipe(finalize(() => this.exportPending.set(false)))
      .subscribe({
        next: (response) => {
          const blob = response.body;
          if (blob === null) {
            this.exportError.set(true);
            return;
          }
          const disposition = response.headers.get('content-disposition') ?? '';
          const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? 'kiba-data-export.json';
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = filename;
          link.click();
          URL.revokeObjectURL(url);
        },
        error: () => this.exportError.set(true),
      });
  }

  protected showDeleteConfirmation(): void {
    this.deleteError.set(null);
    this.deleteOpen.set(true);
  }

  protected cancelDelete(): void {
    if (this.deletePending()) return;
    this.deleteOpen.set(false);
    this.deleteError.set(null);
    this.deleteForm.reset({ password: '', confirmed: false });
  }

  protected deleteAccount(): void {
    if (this.deletePending() || this.deleteForm.invalid) {
      this.deleteForm.markAllAsTouched();
      return;
    }
    this.deletePending.set(true);
    this.deleteError.set(null);
    this.auth
      .deleteAccount(this.deleteForm.controls.password.value)
      .pipe(finalize(() => this.deletePending.set(false)))
      .subscribe({
        next: () => void this.router.navigateByUrl('/'),
        error: (error: unknown) => {
          this.deleteError.set(
            error instanceof HttpErrorResponse && error.status === 401
              ? this.i18n.t('profile.deleteWrongPassword')
              : this.i18n.t('profile.deleteFailed'),
          );
        },
      });
  }

  protected joinedAt(user: CurrentUser): string {
    return this.i18n.formatDate(user.created_at, { dateStyle: 'long' });
  }

  protected winRate(value: number): string {
    return this.i18n.formatNumber(value, { maximumFractionDigits: 1 });
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
      return this.i18n.t('profile.sessionEnded');
    }
    return this.i18n.t('profile.saveFailed');
  }
}
