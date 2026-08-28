import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';
import { CurrentUser, LoginRequest, RegisterRequest } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import {
  DEFAULT_COSMETIC_LOADOUT,
  MatchStatistics,
  ProgressionSummary,
} from '../core/profile/profile.models';
import { ProfileService } from '../core/profile/profile.service';
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
  logoutAll: ReturnType<typeof vi.fn<() => Observable<void>>>;
  sendVerification: ReturnType<typeof vi.fn<() => Observable<{ message: string }>>>;
  updateDisplayName: ReturnType<typeof vi.fn<(name: string) => Observable<CurrentUser>>>;
}

const statistics: MatchStatistics = {
  games_played: 12,
  wins: 7,
  losses: 4,
  draws: 1,
  win_rate: 58.33,
  current_win_streak: 2,
  best_win_streak: 3,
  total_transfers: 5,
  total_takes: 4,
  total_throw_ins: 8,
  highest_transfer_target: 72,
  arithmetic_mean_throw_ins: 2,
  bot_games: 9,
  bot_wins: 5,
  pvp_games: 3,
  pvp_wins: 2,
};

const progression: ProgressionSummary = {
  total_xp: 675,
  level: 4,
  level_start_xp: 450,
  next_level_xp: 800,
  xp_into_level: 225,
  xp_needed_for_next_level: 125,
  progress_fraction: 225 / 350,
  achievements_unlocked: 3,
  achievements_total: 8,
};

describe('account pages', () => {
  let auth: AuthStub;
  let profile: {
    getStatistics: ReturnType<typeof vi.fn>;
    getProgression: ReturnType<typeof vi.fn>;
    currentLoadout: ReturnType<typeof signal>;
  };

  beforeEach(() => {
    auth = {
      currentUser: signal<CurrentUser | null>(null),
      initialized: signal(true),
      refresh: vi.fn(() => of(null)),
      register: vi.fn(() => of(user)),
      login: vi.fn(() => of(user)),
      logout: vi.fn(() => of(undefined)),
      logoutAll: vi.fn(() => of(undefined)),
      sendVerification: vi.fn(() => of({ message: 'verification_sent' })),
      updateDisplayName: vi.fn((name) => of({ ...user, display_name: name })),
    };
    profile = {
      getStatistics: vi.fn(() => of(statistics)),
      getProgression: vi.fn(() => of(progression)),
      currentLoadout: signal(DEFAULT_COSMETIC_LOADOUT),
    };
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: auth },
        { provide: ProfileService, useValue: profile },
      ],
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

  it('renders and updates an authenticated profile with persisted statistics', () => {
    auth.currentUser.set(user);
    const fixture = TestBed.createComponent(ProfilePageComponent);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Игрок');
    expect(text).toContain(user.email);
    expect(text).toContain('Статистика');
    expect(text).toContain('58,3%');
    expect(text).toContain('История партий');
    expect(text).toContain('Против бота 9 / 5 побед');
    expect(text).toContain('PvP 3 / 2 побед');
    expect(profile.getStatistics).toHaveBeenCalledOnce();
    expect(profile.getProgression).toHaveBeenCalledOnce();
    expect(text).toContain('Уровень 4');
    expect(text).toContain('675 XP');
    expect(text).toContain('До следующего уровня: 125 XP');
    expect(text).toContain('Достижения: 3 / 8');
    const progress = (fixture.nativeElement as HTMLElement).querySelector('progress');
    expect(progress?.getAttribute('value')).toBe('225');
    expect(progress?.getAttribute('max')).toBe('350');

    input(fixture, 'display_name', 'Новое имя');
    (fixture.nativeElement as HTMLElement)
      .querySelector('form')
      ?.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(auth.updateDisplayName).toHaveBeenCalledWith('Новое имя');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Имя сохранено');
  });

  it('shows verification state and can resend without gating the profile', () => {
    auth.currentUser.set({ ...user, email_verified: false });
    const fixture = TestBed.createComponent(ProfilePageComponent);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Email не подтверждён');
    const resend = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.includes('Отправить письмо'),
    );
    resend?.click();
    fixture.detectChanges();
    expect(auth.sendVerification).toHaveBeenCalledOnce();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Письмо отправлено');

    auth.currentUser.set({ ...user, email_verified: true });
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Email подтверждён');
  });

  it('reports a failed initial verification delivery without losing the account', () => {
    auth.currentUser.set({ ...user, email_verified: false, verification_email_sent: false });
    const fixture = TestBed.createComponent(ProfilePageComponent);
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Не удалось отправить письмо');
    expect(text).toContain('Аккаунт создан');
    expect(text).toContain('Отправить письмо ещё раз');
  });

  it('shows a useful empty match-history state for a new account', () => {
    auth.currentUser.set(user);
    profile.getStatistics.mockReturnValue(of({ ...statistics, games_played: 0 }));
    const fixture = TestBed.createComponent(ProfilePageComponent);
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Пока нет сыгранных партий');
    expect(text).toContain('Играть');
  });

  it('renders the equipped profile frame without changing identity data', () => {
    auth.currentUser.set(user);
    profile.currentLoadout.set({
      ...DEFAULT_COSMETIC_LOADOUT,
      profile_frame_code: 'WINNER_FRAME',
    });
    const fixture = TestBed.createComponent(ProfilePageComponent);
    fixture.detectChanges();

    const title = (fixture.nativeElement as HTMLElement).querySelector('.profile-title');
    expect(title?.classList.contains('frame-winner')).toBe(true);
    expect(title?.textContent).toContain('Игрок');
  });

  it('shows a statistics loading failure without hiding profile controls', () => {
    auth.currentUser.set(user);
    profile.getStatistics.mockReturnValue(throwError(() => new Error('offline')));
    const fixture = TestBed.createComponent(ProfilePageComponent);
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Не удалось загрузить статистику');
    expect(text).toContain('Сохранить');
  });

  it('shows a progression loading failure independently', () => {
    auth.currentUser.set(user);
    profile.getProgression.mockReturnValue(throwError(() => new Error('offline')));
    const fixture = TestBed.createComponent(ProfilePageComponent);
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Не удалось загрузить прогресс');
    expect(text).toContain('Статистика');
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
