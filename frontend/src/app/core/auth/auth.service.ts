import { HttpClient, HttpErrorResponse, HttpResponse } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { catchError, Observable, of, tap } from 'rxjs';
import { AuthMessage, CurrentUser, LoginRequest, RegisterRequest } from './auth.models';
import { Locale } from '../i18n/locale';
import { TranslationService } from '../i18n/translation.service';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly i18n = inject(TranslationService);

  readonly currentUser = signal<CurrentUser | null>(null);
  readonly initialized = signal(false);

  refresh(): Observable<CurrentUser | null> {
    return this.http.get<CurrentUser>('/api/auth/me').pipe(
      tap((user) => {
        this.setAuthenticated(user);
      }),
      catchError((error: unknown) => {
        this.currentUser.set(null);
        this.initialized.set(true);
        if (error instanceof HttpErrorResponse && error.status === 401) {
          return of(null);
        }
        return of(null);
      }),
    );
  }

  register(request: RegisterRequest): Observable<CurrentUser> {
    return this.http
      .post<CurrentUser>('/api/auth/register', request)
      .pipe(tap((user) => this.setAuthenticated(user)));
  }

  login(request: LoginRequest): Observable<CurrentUser> {
    return this.http
      .post<CurrentUser>('/api/auth/login', request)
      .pipe(tap((user) => this.setAuthenticated(user)));
  }

  logout(): Observable<void> {
    return this.http
      .post<void>('/api/auth/logout', null)
      .pipe(tap(() => this.setAuthenticated(null)));
  }

  logoutAll(): Observable<void> {
    return this.http
      .post<void>('/api/auth/logout-all', null)
      .pipe(tap(() => this.setAuthenticated(null)));
  }

  sendVerification(): Observable<AuthMessage> {
    return this.http.post<AuthMessage>('/api/auth/verification/send', null);
  }

  confirmVerification(token: string): Observable<CurrentUser> {
    return this.http
      .post<CurrentUser>('/api/auth/verification/confirm', { token })
      .pipe(tap((user) => this.setAuthenticated(user)));
  }

  forgotPassword(email: string): Observable<AuthMessage> {
    return this.http.post<AuthMessage>('/api/auth/password/forgot', { email });
  }

  resetPassword(token: string, newPassword: string): Observable<AuthMessage> {
    return this.http.post<AuthMessage>('/api/auth/password/reset', {
      token,
      new_password: newPassword,
    });
  }

  updateDisplayName(displayName: string): Observable<CurrentUser> {
    return this.http
      .patch<CurrentUser>('/api/profile', { display_name: displayName })
      .pipe(tap((user) => this.setAuthenticated(user)));
  }

  updatePreferredLocale(preferredLocale: Locale): Observable<CurrentUser> {
    return this.http
      .patch<CurrentUser>('/api/profile', { preferred_locale: preferredLocale })
      .pipe(tap((user) => this.setAuthenticated(user)));
  }

  exportData(): Observable<HttpResponse<Blob>> {
    return this.http.get('/api/account/export', {
      observe: 'response',
      responseType: 'blob',
    });
  }

  deleteAccount(password: string): Observable<void> {
    return this.http
      .post<void>('/api/account/delete', { password, confirmation: 'DELETE' })
      .pipe(tap(() => this.setAuthenticated(null)));
  }

  private setAuthenticated(user: CurrentUser | null): void {
    this.currentUser.set(user);
    this.initialized.set(true);
    if (user !== null) this.i18n.useAccountLocale(user.preferred_locale);
  }
}
