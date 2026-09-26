import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideRouter, Router } from '@angular/router';
import { of } from 'rxjs';
import { App } from './app';
import { routes } from './app.routes';
import { GameApiService } from './core/api/game-api.service';
import { AuthService } from './core/auth/auth.service';
import { TranslationService } from './core/i18n/translation.service';
import { DEFAULT_COSMETIC_LOADOUT } from './core/profile/profile.models';
import { ProfileService } from './core/profile/profile.service';
import { KIBA_FIRST_RUN_SEEN_KEY } from './core/onboarding/first-run.store';

describe('App', () => {
  const currentUser = signal<{
    id: string;
    email: string;
    display_name: string;
    created_at: string;
  } | null>(null);

  beforeEach(async () => {
    localStorage.clear();
    localStorage.setItem('kiba.preferred-locale', 'ru');
    localStorage.setItem(KIBA_FIRST_RUN_SEEN_KEY, 'true');
    currentUser.set(null);
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideRouter(routes),
        { provide: GameApiService, useValue: { createGame: () => of(null) } },
        {
          provide: AuthService,
          useValue: { currentUser, initialized: signal(true), refresh: () => of(null) },
        },
        {
          provide: ProfileService,
          useValue: {
            currentLoadout: signal(DEFAULT_COSMETIC_LOADOUT),
            getCosmetics: () => of({ items: [], loadout: DEFAULT_COSMETIC_LOADOUT }),
            resetCosmetics: vi.fn(),
          },
        },
      ],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('renders the compact product shell and landing choices', async () => {
    const fixture = TestBed.createComponent(App);
    await TestBed.inject(Router).navigateByUrl('/');
    await fixture.whenStable();
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.brand')?.textContent).toContain('KIBA');
    expect(compiled.querySelector('h1')?.textContent).toContain('KIBA');
    expect(compiled.textContent).toContain('Карточная игра с арифметикой');
    expect(compiled.querySelector('a[href="/play"]')?.textContent).toContain('Играть');
    expect(compiled.querySelector('a[href="/tutorial"]')?.textContent).toContain('Обучение');
    expect(compiled.querySelector('a[href="/rules"]')?.textContent).toContain('Правила');
    expect(compiled.querySelector('a[href="/login"]')?.textContent).toContain('Войти');
    expect(compiled.querySelector('a[href="/register"]')?.textContent).toContain(
      'Создайте аккаунт',
    );
    expect(compiled.querySelector('a[href="/privacy"]')?.textContent).toContain(
      'Конфиденциальность',
    );
    expect(compiled.querySelector('a[href="/terms"]')?.textContent).toContain('Условия');
    expect(compiled.querySelector('a[href^="mailto:"]')?.getAttribute('href')).toBe(
      'mailto:support@cyberdurak.com',
    );
  });

  it('puts a localized skip link first and moves keyboard focus to route main content', async () => {
    const fixture = TestBed.createComponent(App);
    await TestBed.inject(Router).navigateByUrl('/');
    await fixture.whenStable();
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    const skip = element.querySelector('.skip-link') as HTMLAnchorElement;
    const main = element.querySelector('#main-content') as HTMLElement;

    expect(element.querySelector('a')).toBe(skip);
    expect(skip.textContent).toContain('Перейти к основному содержанию');
    skip.click();
    expect(document.activeElement).toBe(main);

    TestBed.inject(TranslationService).setLocale('en');
    fixture.detectChanges();
    expect(skip.textContent).toContain('Skip to main content');
  });

  it('shows the account display name in navigation after authentication', () => {
    currentUser.set({
      id: 'user-1',
      email: 'player@example.com',
      display_name: 'КибаИгрок',
      created_at: '2026-08-27T10:00:00+00:00',
    });
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const profile = (fixture.nativeElement as HTMLElement).querySelector('a[href="/profile"]');
    expect(profile?.textContent).toContain('КибаИгрок');
    expect((fixture.nativeElement as HTMLElement).querySelector('a[href="/login"]')).toBeNull();
  });

  it('routes to tutorial and rules without starting a gameplay API call', async () => {
    const createGame = vi.fn(() => of(null));
    TestBed.overrideProvider(GameApiService, { useValue: { createGame } });
    const fixture = TestBed.createComponent(App);
    const router = TestBed.inject(Router);

    await router.navigateByUrl('/tutorial');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Цель и карты');

    await router.navigateByUrl('/rules');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Правила игры');
    expect(createGame).not.toHaveBeenCalled();
  });

  it('does not mount first-run onboarding on deep links or gameplay recovery routes', async () => {
    localStorage.removeItem(KIBA_FIRST_RUN_SEEN_KEY);
    sessionStorage.setItem('kiba.activeBotGameId', 'recoverable-game');
    const fixture = TestBed.createComponent(App);
    const router = TestBed.inject(Router);

    await router.navigateByUrl('/tutorial');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('.first-run')).toBeNull();

    expect(routes.find((route) => route.path === 'join/:inviteCode')?.component).not.toBe(
      routes.find((route) => route.path === '')?.component,
    );
    expect(routes.find((route) => route.path === 'play')?.component).not.toBe(
      routes.find((route) => route.path === '')?.component,
    );
    expect(sessionStorage.getItem('kiba.activeBotGameId')).toBe('recoverable-game');
  });
});
