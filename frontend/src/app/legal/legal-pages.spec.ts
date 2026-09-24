import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { TranslationService } from '../core/i18n/translation.service';
import { PrivacyPageComponent } from './privacy-page';
import { TermsPageComponent } from './terms-page';

describe('legal pages', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideRouter([{ path: 'privacy', component: PrivacyPageComponent }])],
    });
  });

  it('renders the English Privacy Policy with controller and contact details', () => {
    const i18n = TestBed.inject(TranslationService);
    i18n.setLocale('en');
    const fixture = TestBed.createComponent(PrivacyPageComponent);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('Privacy Policy');
    expect(text).toContain('Oleg Shaltaev');
    expect(text).toContain('Finland');
    expect(text).toContain('support@cyberdurak.com');
    expect(text).toContain('Your rights');
    expect(text).toContain('Cookies and browser storage');
  });

  it('renders the English Terms with the important public-beta sections', () => {
    TestBed.inject(TranslationService).setLocale('en');
    const fixture = TestBed.createComponent(TermsPageComponent);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('Terms of Use');
    expect(text).toContain('Service provider');
    expect(text).toContain('Acceptable use');
    expect(text).toContain('Oleg Shaltaev');
    expect(text).toContain('support@cyberdurak.com');
  });

  it('switches legal copy to Russian without changing the current route', async () => {
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/privacy');
    const i18n = TestBed.inject(TranslationService);
    i18n.setLocale('en');
    const fixture = TestBed.createComponent(PrivacyPageComponent);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Privacy Policy');

    i18n.setLocale('ru');
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Политика конфиденциальности',
    );
    expect(router.url).toBe('/privacy');
  });

  it('renders Russian Terms on the same localized route', () => {
    TestBed.inject(TranslationService).setLocale('ru');
    const fixture = TestBed.createComponent(TermsPageComponent);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('Условия использования');
    expect(text).toContain('Поставщик сервиса');
    expect(text).toContain('Допустимое использование');
  });
});
