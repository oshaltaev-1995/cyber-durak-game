import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { TranslationService } from '../core/i18n/translation.service';
import { RulesPageComponent } from './rules-page';

describe('RulesPageComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RulesPageComponent],
      providers: [provideRouter([])],
    }).compileComponents();
  });

  it('renders the complete user-facing rules structure', () => {
    const fixture = TestBed.createComponent(RulesPageComponent);
    fixture.detectChanges();
    const headings = [...(fixture.nativeElement as HTMLElement).querySelectorAll('h2')].map(
      (heading) => heading.textContent?.trim(),
    );

    expect(headings).toContain('Цель игры');
    expect(headings).toContain('Колода и раздача');
    expect(headings).toContain('Двойной козырь');
    expect(headings).toContain('Как покрывать');
    expect(headings).toContain('Как подкидывать');
    expect(headings).toContain('Среднее арифметическое');
    expect(headings).toContain('Победа и ничья');
  }, 15_000);

  it('includes canonical first-attacker, mean, transfer, refill, and draw rules', () => {
    const fixture = TestBed.createComponent(RulesPageComponent);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('игрок с самым младшим козырем');
    expect(text).toContain('30 / 2 = 15');
    expect(text).toContain('18 → 36 → 72');
    expect(text).toContain('3 / 5 + 4 карты → 6 / 6');
    expect(text).toContain('обе руки пусты — Ничья');
  });

  it('uses player language rather than internal implementation terminology', () => {
    const fixture = TestBed.createComponent(RulesPageComponent);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).not.toContain('BoutState');
    expect(text).not.toContain('direct_anchor_cards');
    expect(text).not.toContain('GamePhase');
    expect(text).not.toContain('Fraction');
  });

  it('includes the recovered throw-in, packet, endgame, and refill corrections', () => {
    const fixture = TestBed.createComponent(RulesPageComponent);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('7 + J');
    expect(text).toContain('J(12) + 8(8) = 20');
    expect(text).toContain('A = 20');
    expect(text).toContain('Старые покрытые атаки такой прямой подсказки больше не дают');
    expect(text).toContain('Покрывается только текущий пакет');
    expect(text).toContain('После первой успешной защиты перевод закрыт');
    expect(text).toContain('последними картами');
    expect(text).toContain('максимально близкими');
    expect(text).toContain('Продвинутое правило: Ряд');
    expect(text).toContain('10–A');
    expect(text).toContain('новая цель 7 + 14 = 21');
    expect(text).toContain('9 + 9 + 9');
  });

  it('renders the complete canonical English rules at runtime', () => {
    const fixture = TestBed.createComponent(RulesPageComponent);
    TestBed.inject(TranslationService).setLocale('en');
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('lowest trump');
    expect(text).toContain('Arithmetic mean');
    expect(text).toContain('latest defense is also a target');
    expect(text).toContain('Advanced rule: Rank run');
    expect(text).toContain('exact core may be extended');
    expect(text).toContain('hand sizes as close as possible');
    expect(text).toContain('both hands empty — Draw');
  });
});
