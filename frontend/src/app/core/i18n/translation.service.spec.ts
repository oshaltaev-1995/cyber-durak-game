import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { KIBA_LOCALE_STORAGE_KEY, parseLocale } from './locale';
import { localeInterceptor } from './locale.interceptor';
import { TranslationService } from './translation.service';
import { en } from './translations/en';
import { ru } from './translations/ru';

describe('runtime localization', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    TestBed.resetTestingModule();
  });

  it('keeps RU and EN catalogues complete and parses the supported browser languages', () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(ru).sort());
    expect(en['meta.default']).toBe('KIBA — Arithmetic Durak');
    expect(ru['meta.default']).toBe('KIBA — Арифметический дурак');
    expect(parseLocale('ru-RU')).toBe('ru');
    expect(parseLocale('en-US')).toBe('en');
    expect(parseLocale('de-DE')).toBe('en');
  });

  it.each(['ru-RU', 'en-US', 'de-DE'])(
    'defaults a new %s browser to English',
    (browserLanguage) => {
      localStorage.removeItem(KIBA_LOCALE_STORAGE_KEY);
      vi.spyOn(window.navigator, 'language', 'get').mockReturnValue(browserLanguage);
      const service = TestBed.inject(TranslationService);

      expect(service.locale()).toBe('en');
      expect(localStorage.getItem(KIBA_LOCALE_STORAGE_KEY)).toBe('en');
      expect(document.documentElement.lang).toBe('en');
    },
  );

  it('lets persisted choice override the browser and switches immediately', () => {
    localStorage.setItem(KIBA_LOCALE_STORAGE_KEY, 'ru');
    vi.spyOn(window.navigator, 'language', 'get').mockReturnValue('en-US');
    const service = TestBed.inject(TranslationService);

    expect(service.t('nav.play')).toBe('Играть');
    service.setLocale('en');
    expect(service.t('nav.play')).toBe('Play');
    expect(localStorage.getItem(KIBA_LOCALE_STORAGE_KEY)).toBe('en');
    expect(document.documentElement.lang).toBe('en');
  });

  it.each([
    [1, 'карту'],
    [2, 'карты'],
    [4, 'карты'],
    [5, 'карт'],
    [11, 'карт'],
    [14, 'карт'],
    [21, 'карту'],
    [22, 'карты'],
    [25, 'карт'],
  ])('renders the Russian TAKE message for %i with %s', (count, cards) => {
    localStorage.setItem(KIBA_LOCALE_STORAGE_KEY, 'ru');
    const service = TestBed.inject(TranslationService);

    expect(service.t('game.youTook', { count, cards: service.takeCardCount(count) })).toBe(
      `Вы взяли ${count} ${cards}`,
    );
  });

  it('keeps nominative card labels and English TAKE wording unchanged', () => {
    localStorage.setItem(KIBA_LOCALE_STORAGE_KEY, 'ru');
    const service = TestBed.inject(TranslationService);

    expect(service.cardCount(1)).toBe('карта');
    expect(service.takeCardCount(1)).toBe('карту');
    service.setLocale('en');
    expect(service.t('game.youTook', { count: 1, cards: service.takeCardCount(1) })).toBe(
      'You took 1 card',
    );
    expect(service.t('game.youTook', { count: 2, cards: service.takeCardCount(2) })).toBe(
      'You took 2 cards',
    );
  });

  it('adds the active locale to API requests', () => {
    localStorage.setItem(KIBA_LOCALE_STORAGE_KEY, 'en');
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([localeInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    const http = TestBed.inject(HttpClient);
    const testing = TestBed.inject(HttpTestingController);

    http.get('/api/achievements').subscribe();
    const request = testing.expectOne('/api/achievements');
    expect(request.request.headers.get('Accept-Language')).toBe('en');
    request.flush([]);
    testing.verify();
  });
});
