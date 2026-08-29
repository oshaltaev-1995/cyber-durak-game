import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { TranslationService } from '../core/i18n/translation.service';
import { TutorialPageComponent } from './tutorial-page';
import { TUTORIAL_LESSONS_EN, TUTORIAL_LESSONS_RU } from './tutorial-data';

describe('TutorialPageComponent', () => {
  let fixture: ComponentFixture<TutorialPageComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TutorialPageComponent],
      providers: [provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(TutorialPageComponent);
    fixture.detectChanges();
  });

  const button = (label: string): HTMLButtonElement => {
    const match = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (candidate) => candidate.textContent?.trim() === label,
    );
    expect(match).toBeDefined();
    return match as HTMLButtonElement;
  };

  const advance = (fromIndex: number): void => {
    const exercise = TUTORIAL_LESSONS_RU[fromIndex].exercise;
    if (exercise !== null) {
      const answer = exercise.choices.find((choice) => choice.id === exercise.answer);
      expect(answer).toBeDefined();
      button((answer as { label: string }).label).click();
      fixture.detectChanges();
    }
    button(fromIndex === TUTORIAL_LESSONS_RU.length - 1 ? 'Завершить' : 'Далее').click();
    fixture.detectChanges();
  };

  const advanceTo = (targetIndex: number): void => {
    for (let index = 0; index < targetIndex; index += 1) {
      advance(index);
    }
  };

  it('opens at lesson one with readable progress and navigation', () => {
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('h1')?.textContent).toContain('Цель и карты');
    expect(element.querySelector('[role="progressbar"]')?.textContent).toContain('1 / 8');
    expect(button('Назад').disabled).toBe(true);
    expect(element.querySelector('a[href="/play"]')?.textContent).toContain('Пропустить');
  });

  it('moves forward and back without an API-backed game', () => {
    advance(0);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Двойной козырь');
    button('Назад').click();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Цель и карты');
  });

  it('keeps an incorrect trump choice usable and explains the correct scripted choice', () => {
    advance(0);
    button('8♥ = 16').click();
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('[role="status"]')?.textContent).toContain('удвоенную стоимость');
    expect(button('Далее').disabled).toBe(true);

    button('6♥ = 12').click();
    fixture.detectChanges();
    expect(element.querySelector('[role="status"]')?.textContent).toContain('Верно');
    expect(button('Далее').disabled).toBe(false);
  });

  it('teaches the exact arithmetic mean without rounding or authoritative client logic', () => {
    advanceTo(5);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Сумма и среднее');
    expect(text).toContain('(12 + 18) / 2 = 15');
    expect(text).toContain('никогда не округляется');
    expect(text).toContain('Активная атака — отдельная величина');
  });

  it('teaches the latest multi-card defense total as a throw-in target', () => {
    advanceTo(4);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('J(12) + 8(8) = 20');
    expect(text).toContain('A = 20');
    expect(text).toContain('ряд минимум из пяти рангов');
    expect(text).toContain('10, J, K, A + Q → ряд 10–A');
  });

  it('shows the exact transfer snowball lesson', () => {
    advanceTo(6);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Перевод');
    expect(text).toContain('18 → 36 → 72');
    expect(text).toContain('После первой успешной защиты');
    expect(text).toContain('точное ядро');
    expect(text).toContain('7 → 7 + 7 → 21');
  });

  it('finishes all eight lessons with play, rules, and replay choices', () => {
    for (let index = 0; index < TUTORIAL_LESSONS_RU.length; index += 1) {
      advance(index);
    }

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('h1')?.textContent).toContain('Готово');
    expect(element.querySelector('a[href="/play"]')?.textContent).toContain('Играть');
    expect(element.querySelector('a[href="/rules"]')?.textContent).toContain('Правила');

    button('Пройти ещё раз').click();
    fixture.detectChanges();
    expect(element.textContent).toContain('Цель и карты');
  });

  it('provides all eight English lessons and preserves the current step on runtime switch', () => {
    expect(TUTORIAL_LESSONS_EN).toHaveLength(8);
    advance(0);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Двойной козырь');

    TestBed.inject(TranslationService).setLocale('en');
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Dual trump');
    expect(text).toContain('2 / 8');
    button('8♥ = 16').click();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Compare doubled effective values',
    );
  });
});
