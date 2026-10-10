import { TestBed } from '@angular/core/testing';
import { GameCard, TrumpState } from '../../../core/api/game-api.models';
import { TrumpIndicatorComponent } from './trump-indicator';

const joker = (color: 'red' | 'black'): GameCard => ({
  id: `deck-1:joker:${color}`,
  code: color === 'red' ? 'RJ' : 'BJ',
  rank: 'Joker',
  suit: null,
  joker_color: color,
  base_value: 25,
  effective_value: 50,
  is_trump: true,
});

describe('TrumpIndicatorComponent', () => {
  it.each([
    ['red', '♥ ♦ и Красный Джокер', ['♣', '♠', 'Чёрный Джокер']],
    ['black', '♣ ♠ и Чёрный Джокер', ['♥', '♦', 'Красный Джокер']],
  ] as const)(
    'explains the %s Joker top without the opposite family',
    async (color, expected, absent) => {
      const fixture = TestBed.createComponent(TrumpIndicatorComponent);
      const source = joker(color);
      fixture.componentRef.setInput('exposedCard', source);
      fixture.componentRef.setInput('drawPileCount', 108);
      fixture.componentRef.setInput('trump', {
        active: true,
        source_card: source,
        trump_rank: null,
        trump_suit: null,
      } satisfies TrumpState);
      await fixture.whenStable();

      const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
      expect(text).toContain(expected);
      expect(text).toContain('108');
      for (const value of absent) expect(text).not.toContain(value);
    },
  );

  it('shows no trump and no stale Joker family when the draw pile is empty', async () => {
    const fixture = TestBed.createComponent(TrumpIndicatorComponent);
    fixture.componentRef.setInput('exposedCard', null);
    fixture.componentRef.setInput('drawPileCount', 0);
    fixture.componentRef.setInput('trump', {
      active: false,
      source_card: null,
      trump_rank: null,
      trump_suit: null,
    } satisfies TrumpState);
    await fixture.whenStable();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Без козыря');
    expect(text).not.toContain('Красный Джокер');
    expect(text).not.toContain('Чёрный Джокер');
  });
});
