import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
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
    expect(text).toContain('Старые покрытые атаки такой прямой подсказки больше не дают');
    expect(text).toContain('Покрывается только текущий пакет');
    expect(text).toContain('После первой успешной защиты перевод закрыт');
    expect(text).toContain('последними картами');
    expect(text).toContain('максимально близкими');
  });
});
