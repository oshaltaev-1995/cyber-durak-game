import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../core/auth/auth.service';
import { TranslationService } from '../core/i18n/translation.service';

@Component({
  selector: 'app-reset-password-page',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './reset-password-page.html',
  styleUrl: './auth-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ResetPasswordPageComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  protected readonly i18n = inject(TranslationService);
  protected readonly token = this.route.snapshot.queryParamMap.get('token') ?? '';
  protected readonly pending = signal(false);
  protected readonly complete = signal(false);
  protected readonly error = signal<string | null>(
    this.token ? null : this.i18n.t('auth.invalidToken'),
  );
  protected readonly form = new FormGroup({
    password: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.minLength(8), Validators.maxLength(128)],
    }),
    confirm: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
  });

  ngOnInit(): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: {},
      replaceUrl: true,
    });
  }

  protected submit(): void {
    const value = this.form.getRawValue();
    if (this.pending() || this.form.invalid || !this.token || value.password !== value.confirm) {
      this.form.markAllAsTouched();
      if (value.password !== value.confirm) this.error.set(this.i18n.t('auth.passwordMismatch'));
      return;
    }
    this.pending.set(true);
    this.error.set(null);
    this.auth
      .resetPassword(this.token, value.password)
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: () => this.complete.set(true),
        error: (error: unknown) =>
          this.error.set(
            error instanceof HttpErrorResponse && error.status === 400
              ? this.i18n.t('auth.tokenExpired')
              : this.i18n.t('auth.resetFailed'),
          ),
      });
  }
}
