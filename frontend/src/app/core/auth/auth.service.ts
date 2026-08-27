import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { catchError, Observable, of, tap } from 'rxjs';
import { CurrentUser, LoginRequest, RegisterRequest } from './auth.models';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);

  readonly currentUser = signal<CurrentUser | null>(null);
  readonly initialized = signal(false);

  refresh(): Observable<CurrentUser | null> {
    return this.http.get<CurrentUser>('/api/auth/me').pipe(
      tap((user) => {
        this.currentUser.set(user);
        this.initialized.set(true);
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

  updateDisplayName(displayName: string): Observable<CurrentUser> {
    return this.http
      .patch<CurrentUser>('/api/profile', { display_name: displayName })
      .pipe(tap((user) => this.setAuthenticated(user)));
  }

  private setAuthenticated(user: CurrentUser | null): void {
    this.currentUser.set(user);
    this.initialized.set(true);
  }
}
