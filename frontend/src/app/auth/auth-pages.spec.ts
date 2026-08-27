import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';
import { CurrentUser, LoginRequest, RegisterRequest } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import { LoginPageComponent } from './login-page';
import { ProfilePageComponent } from './profile-page';
import { RegisterPageComponent } from './register-page';

const user: CurrentUser = {
  id: 'user-1',
  email: 'player@example.com',
  display_name: 'Игрок',
  created_at: '2026-08-27T10:00:00+00:00',
};

interface AuthStub {
  currentUser: ReturnType<typeof signal<CurrentUser | null>>;
  initialized: ReturnType<typeof signal<boolean>>;
  refresh: ReturnType<typeof vi.fn<() => Observable<CurrentUser | null>>>;
  register: ReturnType<typeof vi.fn<(request: RegisterRequest) => Observable<CurrentUser>>>;
  login: ReturnType<typeof vi.fn<(request: LoginRequest) => Observable<CurrentUser>>>;
  logout: ReturnType<typeof vi.fn<() => Observable<void>>>;
  updateDisplayName: ReturnType<typeof vi.fn<(name: string) => Observable<CurrentUser>>>;
}

describe('account pages', () => {
  let auth: AuthStub;

  beforeEach(() => {
    auth = {
      currentUser: signal<CurrentUser | null>(null),
      initialized: signal(true),
      refresh: vi.fn(() => of(null)),
      register: vi.fn(() => of(user)),
      login: vi.fn(() => of(user)),
      logout: vi.fn(() => of(undefined)),
      updateDisplayName: vi.fn((name) => of({ ...user, display_name: name })),
    };
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: auth }],
    });
  });

  function input(fixture: ComponentFixture<unknown>, name: string, value: string): void {
    const element = (fixture.nativeElement as HTMLElement).querySelector(
      `[formcontrolname="${name}"]`,
    ) as HTMLInputElement;
    element.value = value;
    element.dispatchEvent(new Event('input'));
  }

  it('renders login and submits credentials', () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    const fixture = TestBed.createComponent(LoginPageComponent);
    fixture.detectChanges();

    input(fixture, 'email', user.email);
    input(fixture, 'password', 'password123');
    (fixture.nativeElement as HTMLElement)
      .querySelector('form')
      ?.dispatchEvent(new Event('submit'));
    fixture.detectChanges();

    expect(auth.login).toHaveBeenCalledWith({ email: user.email, password: 'password123' });
    expect(navigate).toHaveBeenCalledWith('/profile');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Играть без входа');
  });

  it('shows a generic invalid-credentials error', () => {
    auth.login.mockReturnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 401,
            error: { detail: { code: 'invalid_credentials' } },
          }),
      ),
    );
    const fixture = TestBed.createComponent(LoginPageComponent);
    fixture.detectChanges();
    input(fixture, 'email', user.email);
    input(fixture, 'password', 'incorrect');
    (fixture.nativeElement as HTMLElement)
      .querySelector('form')
      ?.dispatchEvent(new Event('submit'));
    fixture.detectChanges();

    expect(
      (fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')?.textContent,
    ).toContain('Неверный email или пароль');
  });

  it('reinforces guest-first registration and creates an account', () => {
    vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    const fixture = TestBed.createComponent(RegisterPageComponent);
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Играть можно и без регистрации',
    );
    input(fixture, 'email', user.email);
    input(fixture, 'display_name', user.display_name);
    input(fixture, 'password', 'password123');
    (fixture.nativeElement as HTMLElement)
      .querySelector('form')
      ?.dispatchEvent(new Event('submit'));
    fixture.detectChanges();

    expect(auth.register).toHaveBeenCalledWith({
      email: user.email,
      display_name: user.display_name,
      password: 'password123',
    });
  });

  it('renders and updates an authenticated profile without fake statistics', () => {
    auth.currentUser.set(user);
    const fixture = TestBed.createComponent(ProfilePageComponent);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Игрок');
    expect(text).toContain(user.email);
    expect(text).toContain('появятся в следующем этапе');
    expect(text).not.toContain('XP');

    input(fixture, 'display_name', 'Новое имя');
    (fixture.nativeElement as HTMLElement)
      .querySelector('form')
      ?.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(auth.updateDisplayName).toHaveBeenCalledWith('Новое имя');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Имя сохранено');
  });

  it('logs out and shows guest profile choices', () => {
    auth.currentUser.set(user);
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    const fixture = TestBed.createComponent(ProfilePageComponent);
    fixture.detectChanges();
    const logout = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Выйти',
    );
    logout?.click();
    fixture.detectChanges();

    expect(auth.logout).toHaveBeenCalledOnce();
    expect(navigate).toHaveBeenCalledWith('/');

    auth.currentUser.set(null);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('играете без аккаунта');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Играть');
  });
});
