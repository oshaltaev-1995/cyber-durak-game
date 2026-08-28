import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { AuthService } from '../core/auth/auth.service';
import { ForgotPasswordPageComponent } from './forgot-password-page';
import { ResetPasswordPageComponent } from './reset-password-page';
import { VerifyEmailPageComponent } from './verify-email-page';

function input(fixture: ComponentFixture<unknown>, name: string, value: string): void {
  const element = (fixture.nativeElement as HTMLElement).querySelector(
    `[formcontrolname="${name}"]`,
  ) as HTMLInputElement;
  element.value = value;
  element.dispatchEvent(new Event('input'));
}

describe('account security pages', () => {
  const auth = {
    currentUser: signal(null),
    forgotPassword: vi.fn(() => of({ message: 'password_reset_requested' })),
    resetPassword: vi.fn(() => of({ message: 'password_reset' })),
    confirmVerification: vi.fn(() =>
      of({
        id: 'user-1',
        email: 'player@example.com',
        display_name: 'Игрок',
        created_at: '2026-08-28T10:00:00Z',
        email_verified: true,
      }),
    ),
  };

  beforeEach(() => {
    auth.forgotPassword.mockClear();
    auth.resetPassword.mockClear();
    auth.confirmVerification.mockClear();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: auth },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { queryParamMap: { get: () => 'safe-test-token' } } },
        },
      ],
    });
  });

  it('uses a generic forgot-password confirmation', () => {
    const fixture = TestBed.createComponent(ForgotPasswordPageComponent);
    fixture.detectChanges();
    input(fixture, 'email', 'unknown@example.com');
    (fixture.nativeElement as HTMLElement)
      .querySelector('form')
      ?.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(auth.forgotPassword).toHaveBeenCalledWith('unknown@example.com');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Если аккаунт может получить письмо',
    );
  });

  it('submits a query token with matching new passwords without displaying the token', () => {
    const fixture = TestBed.createComponent(ResetPasswordPageComponent);
    fixture.detectChanges();
    input(fixture, 'password', 'new-password');
    input(fixture, 'confirm', 'new-password');
    (fixture.nativeElement as HTMLElement)
      .querySelector('form')
      ?.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(auth.resetPassword).toHaveBeenCalledWith('safe-test-token', 'new-password');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('safe-test-token');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Все прежние сессии');
  });

  it('confirms email from the query token and renders success', () => {
    const fixture = TestBed.createComponent(VerifyEmailPageComponent);
    fixture.detectChanges();
    expect(auth.confirmVerification).toHaveBeenCalledWith('safe-test-token');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Email подтверждён');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('safe-test-token');
  });
});
