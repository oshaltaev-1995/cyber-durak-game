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
    expect(parseLocale('ru-RU')).toBe('ru');
    expect(parseLocale('en-US')).toBe('en');
    expect(parseLocale('de-DE')).toBe('en');
  });

  it.each([
    ['ru-RU', 'ru'],
    ['en-US', 'en'],
  ] as const)('uses %s on a first visit', (browserLanguage, expected) => {
    localStorage.removeItem(KIBA_LOCALE_STORAGE_KEY);
    vi.spyOn(window.navigator, 'language', 'get').mockReturnValue(browserLanguage);
    const service = TestBed.inject(TranslationService);

    expect(service.locale()).toBe(expected);
    expect(localStorage.getItem(KIBA_LOCALE_STORAGE_KEY)).toBe(expected);
    expect(document.documentElement.lang).toBe(expected);
  });

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
