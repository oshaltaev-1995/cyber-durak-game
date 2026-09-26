import { TestBed } from '@angular/core/testing';
import { GameCard } from '../../../core/api/game-api.models';
import { HandComponent } from './hand';

const ranks = ['6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'] as const;
const suits = ['clubs', 'diamonds', 'hearts', 'spades'] as const;
const suitCodes = ['C', 'D', 'H', 'S'] as const;

function cards(count: number): readonly GameCard[] {
  return Array.from({ length: count }, (_, index) => {
    const rank = ranks[index % ranks.length];
    const suitIndex = Math.floor(index / ranks.length) % suits.length;
    return {
      code: `${rank}${suitCodes[suitIndex]}`,
      rank,
      suit: suits[suitIndex],
      base_value: index + 6,
      effective_value: index + 6,
      is_trump: false,
    };
  });
}

describe('HandComponent', () => {
  it.each([
    [7, []],
    [10, ['large']],
    [14, ['dense']],
    [18, ['very-dense']],
  ] as const)(
    'renders %i reachable cards with the adaptive density class',
    async (count, classes) => {
      const fixture = TestBed.createComponent(HandComponent);
      fixture.componentRef.setInput('cards', cards(count));
      fixture.componentRef.setInput('selectedCodes', new Set<string>());
      await fixture.whenStable();

      const element = fixture.nativeElement as HTMLElement;
      const strip = element.querySelector('.card-strip') as HTMLElement;
      expect(element.querySelectorAll('app-playing-card')).toHaveLength(count);
      expect([...strip.classList].filter((name) => name !== 'card-strip')).toEqual(classes);
      expect(strip.getAttribute('class')).not.toContain('hidden');
    },
  );

  it('keeps every card selectable in a large overlapped hand', async () => {
    const fixture = TestBed.createComponent(HandComponent);
    fixture.componentRef.setInput('cards', cards(14));
    fixture.componentRef.setInput('selectedCodes', new Set<string>());
    const emitted = vi.spyOn(fixture.componentInstance.cardSelected, 'emit');
    await fixture.whenStable();

    const buttons = (fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>(
      'app-playing-card button',
    );
    buttons[0].click();
    buttons[buttons.length - 1].click();
    expect(emitted).toHaveBeenNthCalledWith(1, '6C');
    expect(emitted).toHaveBeenNthCalledWith(2, '10D');
  });
});
