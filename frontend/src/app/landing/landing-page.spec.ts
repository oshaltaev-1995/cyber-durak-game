import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { AuthService } from '../core/auth/auth.service';
import { TranslationService } from '../core/i18n/translation.service';
import { KIBA_FIRST_RUN_SEEN_KEY } from '../core/onboarding/first-run.store';
import { LandingPageComponent } from './landing-page';

describe('LandingPageComponent first-run welcome', () => {
  let fixture: ComponentFixture<LandingPageComponent>;

  const create = (): void => {
    fixture = TestBed.createComponent(LandingPageComponent);
    fixture.detectChanges();
  };

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [LandingPageComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { currentUser: signal(null) } },
      ],
    }).compileComponents();
  });

  it('shows a concise English welcome on the first visit', () => {
    create();
    const element = fixture.nativeElement as HTMLElement;

    expect(element.querySelector('.first-run h1')?.textContent).toContain('Welcome to KIBA');
    expect(element.textContent).toContain('Trump doubles');
    expect(element.textContent).toContain('Several cards can defend or transfer');
    expect(element.textContent).toContain('Public Beta');
    expect(element.querySelector('.hero')).toBeNull();
  });

  it('marks the welcome seen and sends the primary action to the tutorial', () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    create();

    const button = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (candidate) => candidate.textContent?.trim() === 'Start tutorial',
    ) as HTMLButtonElement;
    button.click();

    expect(localStorage.getItem(KIBA_FIRST_RUN_SEEN_KEY)).toBe('true');
    expect(navigate).toHaveBeenCalledWith('/tutorial');
  });

  it('keeps the tutorial optional and sends Play now directly to the game', () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    create();

    const button = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (candidate) => candidate.textContent?.trim() === 'Play now',
    ) as HTMLButtonElement;
    button.click();

    expect(localStorage.getItem(KIBA_FIRST_RUN_SEEN_KEY)).toBe('true');
    expect(navigate).toHaveBeenCalledWith('/play');
  });

  it('does not show the welcome again after it has been seen', () => {
    localStorage.setItem(KIBA_FIRST_RUN_SEEN_KEY, 'true');
    create();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('.first-run')).toBeNull();
    expect(element.querySelector('.hero')).not.toBeNull();
  });

  it('renders natural Russian welcome copy after an explicit locale choice', () => {
    TestBed.inject(TranslationService).setLocale('ru');
    create();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Добро пожаловать в KIBA');
    expect(text).toContain('Начать обучение');
    expect(text).toContain('Играть сразу');
    expect(text).toContain('Публичная бета');
  });
});
