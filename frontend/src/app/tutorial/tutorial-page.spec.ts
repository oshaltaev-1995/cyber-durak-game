import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { TranslationService } from '../core/i18n/translation.service';
import { TutorialPageComponent } from './tutorial-page';
import { TUTORIAL_LESSONS_EN, TUTORIAL_LESSONS_RU } from './tutorial-data';

describe('TutorialPageComponent', () => {
  let fixture: ComponentFixture<TutorialPageComponent>;

  beforeEach(async () => {
    sessionStorage.clear();
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
    const lesson = TUTORIAL_LESSONS_RU[fromIndex];
    const exercise = lesson.exercise;
    if (exercise !== null) {
      const answer = exercise.choices.find((choice) => choice.id === exercise.answer);
      expect(answer).toBeDefined();
      button((answer as { label: string }).label).click();
      fixture.detectChanges();
    }
    if (lesson.practical !== undefined) {
      const cards = (fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>(
        '.practical-cards button',
      );
      cards[0].click();
      cards[1].click();
      fixture.detectChanges();
      button('Покрыть').click();
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
    expect(element.querySelector('[role="progressbar"]')?.textContent).toContain('1 / 9');
    expect(button('Назад').disabled).toBe(true);
    expect(element.querySelector('a[href="/play"]')?.textContent).toContain('Пропустить');
  });

  it('offers an explicit return only when a recoverable bot game exists', () => {
    expect((fixture.nativeElement as HTMLElement).querySelector('.back-to-game')).toBeNull();
    fixture.destroy();
    sessionStorage.setItem('kiba.activeBotGameId', 'game-in-progress');
    fixture = TestBed.createComponent(TutorialPageComponent);
    fixture.detectChanges();

    const link = (fixture.nativeElement as HTMLElement).querySelector(
      '.back-to-game',
    ) as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe('/play');
    expect(link.textContent).toContain('Вернуться в игру');
    expect(sessionStorage.getItem('kiba.activeBotGameId')).toBe('game-in-progress');
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
    advanceTo(6);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Сумма и среднее');
    expect(text).toContain('(12 + 18) / 2 = 15');
    expect(text).toContain('никогда не округляется');
    expect(text).toContain('Активная атака — отдельная величина');
  });

  it('teaches the latest multi-card defense total as a throw-in target', () => {
    advanceTo(5);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('J(12) + 8(8) = 20');
    expect(text).toContain('A = 20');
    expect(text).toContain('ряд минимум из пяти рангов');
    expect(text).toContain('10, J, K, A + Q → ряд 10–A');
  });

  it('shows the exact transfer snowball lesson', () => {
    advanceTo(7);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Перевод');
    expect(text).toContain('18 → 36 → 72');
    expect(text).toContain('После первой успешной защиты');
    expect(text).toContain('точную часть перевода');
    expect(text).toContain('7 → 7 + 7 → 21');
    expect(text).toContain('лимит пересчитывается');
  });

  it('teaches the card-selection then action interaction without an API game', () => {
    advanceTo(4);
    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Попробуйте покрыть');
    expect(element.textContent).toContain('Выберите карты для защиты');
    expect(button('Далее').disabled).toBe(true);

    const cards = element.querySelectorAll<HTMLButtonElement>('.practical-cards button');
    cards[2].click();
    fixture.detectChanges();
    expect(element.textContent).toContain('6♠');
    button('Покрыть').click();
    fixture.detectChanges();
    expect(element.querySelector('[role="status"]')?.textContent).toContain('Нужны именно J и 7');
    expect(button('Далее').disabled).toBe(true);

    cards[2].click();
    cards[0].click();
    cards[1].click();
    fixture.detectChanges();
    expect(element.textContent).toContain('J♣ + 7♦');
    expect(element.textContent).toContain('сумма 19');
    button('Покрыть').click();
    fixture.detectChanges();
    expect(element.querySelector('[role="status"]')?.textContent).toContain('Верно');
    expect(button('Далее').disabled).toBe(false);
  });

  it('uses canonical final-card wording and player language in both locales', () => {
    const russian = TUTORIAL_LESSONS_RU.map((lesson) => [
      lesson.lead,
      ...lesson.points,
      lesson.note,
    ]).join(' ');
    const english = TUTORIAL_LESSONS_EN.map((lesson) => [
      lesson.lead,
      ...lesson.points,
      lesson.note,
    ]).join(' ');

    expect(russian).toContain('последней картой или картами из руки');
    expect(english).toContain('final card or cards from hand');
    expect(english).not.toContain('server validates');
    expect(english).not.toContain('direct anchors');
    expect(english).not.toContain('exact core');
    expect(russian).not.toContain('сервер проверит');
    expect(russian).not.toContain('точное ядро');
  });

  it('finishes all nine lessons with play, rules, and replay choices', () => {
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

  it('provides all nine English lessons and preserves the current step on runtime switch', () => {
    expect(TUTORIAL_LESSONS_EN).toHaveLength(9);
    advance(0);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Двойной козырь');

    TestBed.inject(TranslationService).setLocale('en');
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Dual trump');
    expect(text).toContain('2 / 9');
    button('8♥ = 16').click();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Compare doubled effective values',
    );
  });
});
