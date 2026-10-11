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
    [20, ['very-dense']],
    [23, ['very-dense']],
    [26, ['very-dense']],
    [30, ['very-dense']],
  ] as const)(
    'renders %i reachable cards with the adaptive density class',
    async (count, classes) => {
      const fixture = TestBed.createComponent(HandComponent);
      fixture.componentRef.setInput('cards', cards(count));
      fixture.componentRef.setInput('selectedIds', new Set<string>());
      await fixture.whenStable();

      const element = fixture.nativeElement as HTMLElement;
      const strip = element.querySelector('.card-strip') as HTMLElement;
      expect(element.querySelectorAll('app-playing-card')).toHaveLength(count);
      expect([...strip.classList].filter((name) => name !== 'card-strip')).toEqual(classes);
      expect(strip.getAttribute('class')).not.toContain('hidden');
    },
  );

  it('keeps value and hint indicators in the visible strip of a 26-card hand', async () => {
    const fixture = TestBed.createComponent(HandComponent);
    const hand = cards(26);
    fixture.componentRef.setInput('cards', hand);
    fixture.componentRef.setInput('selectedIds', new Set([hand[13].code]));
    fixture.componentRef.setInput('suggestedIds', new Set([hand[0].code, hand[25].code]));
    fixture.componentRef.setInput('continuationIds', new Set([hand[12].code]));
    await fixture.whenStable();

    const rendered = (fixture.nativeElement as HTMLElement).querySelectorAll('.playing-card');
    expect(rendered).toHaveLength(26);
    for (const index of [0, 12, 13, 25]) {
      expect(rendered[index].classList).toContain('dense');
      expect(rendered[index].querySelector('.value')).not.toBeNull();
    }
    expect(rendered[0].querySelector('.suggested-badge')).not.toBeNull();
    expect(rendered[12].classList).toContain('continuation');
    expect(rendered[13].classList).toContain('selected');
  });

  it.each([14, 20, 23, 26, 31])(
    'keeps first, middle, and last values plus Hint/selection markers exposed for %i cards',
    async (count) => {
      const fixture = TestBed.createComponent(HandComponent);
      const hand = cards(count);
      const middle = Math.floor(count / 2);
      fixture.componentRef.setInput('cards', hand);
      fixture.componentRef.setInput('selectedIds', new Set([hand[middle].code]));
      fixture.componentRef.setInput('suggestedIds', new Set([hand[0].code, hand[count - 1].code]));
      fixture.componentRef.setInput('continuationIds', new Set([hand[middle - 1].code]));
      await fixture.whenStable();

      const element = fixture.nativeElement as HTMLElement;
      const strip = element.querySelector('.card-strip') as HTMLElement;
      const rendered = element.querySelectorAll('.playing-card');
      expect(getComputedStyle(strip).overflowX).toBe('auto');
      for (const index of [0, middle - 1, middle, count - 1]) {
        expect(rendered[index].querySelector('.value')).not.toBeNull();
      }
      expect(rendered[0].querySelector('.suggested-badge')).not.toBeNull();
      expect(rendered[middle - 1].classList).toContain('continuation');
      expect(rendered[middle].classList).toContain('selected');
      expect(rendered[count - 1].querySelector('.suggested-badge')).not.toBeNull();
    },
  );

  it('keeps every card selectable in a large overlapped hand', async () => {
    const fixture = TestBed.createComponent(HandComponent);
    fixture.componentRef.setInput('cards', cards(14));
    fixture.componentRef.setInput('selectedIds', new Set<string>());
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

  it('highlights suggested cards but keeps selected styling authoritative', async () => {
    const fixture = TestBed.createComponent(HandComponent);
    fixture.componentRef.setInput('cards', cards(3));
    fixture.componentRef.setInput('selectedIds', new Set(['6C']));
    fixture.componentRef.setInput('suggestedIds', new Set(['6C', '7C']));
    await fixture.whenStable();

    const rendered = (fixture.nativeElement as HTMLElement).querySelectorAll('.playing-card');
    expect(rendered[0].classList).toContain('selected');
    expect(rendered[0].classList).not.toContain('suggested');
    expect(rendered[1].classList).toContain('suggested');
  });

  it('keeps a non-suggested legal continuation normal, enabled, and clickable', async () => {
    const fixture = TestBed.createComponent(HandComponent);
    fixture.componentRef.setInput('cards', cards(7));
    fixture.componentRef.setInput('selectedIds', new Set<string>());
    fixture.componentRef.setInput('suggestedIds', new Set(['6C', '7C', '8C', '9C', '10C']));
    fixture.componentRef.setInput(
      'continuationIds',
      new Set(['6C', '7C', '8C', '9C', '10C', 'JC']),
    );
    const emitted = vi.spyOn(fixture.componentInstance.cardSelected, 'emit');
    await fixture.whenStable();

    const rendered = (fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>(
      '.playing-card',
    );
    const sixth = rendered[5];
    expect(sixth.classList).toContain('continuation');
    expect(sixth.classList).not.toContain('suggested');
    expect(sixth.disabled).toBe(false);
    sixth.click();
    expect(emitted).toHaveBeenCalledWith('JC');
  });

  it('selects exact duplicate faces independently by physical ID', async () => {
    const duplicates: readonly GameCard[] = [
      { ...cards(1)[0], id: 'deck-1:KH', code: 'KH', rank: 'K', suit: 'hearts' },
      { ...cards(1)[0], id: 'deck-2:KH', code: 'KH', rank: 'K', suit: 'hearts' },
    ];
    const fixture = TestBed.createComponent(HandComponent);
    fixture.componentRef.setInput('cards', duplicates);
    fixture.componentRef.setInput('selectedIds', new Set(['deck-1:KH']));
    const emitted = vi.spyOn(fixture.componentInstance.cardSelected, 'emit');
    await fixture.whenStable();

    const rendered = (fixture.nativeElement as HTMLElement).querySelectorAll('.playing-card');
    expect(rendered).toHaveLength(2);
    expect(rendered[0].classList).toContain('selected');
    expect(rendered[1].classList).not.toContain('selected');
    (rendered[1] as HTMLButtonElement).click();
    expect(emitted).toHaveBeenCalledWith('deck-2:KH');
  });

  it('highlights only the physical duplicate named by a hint', async () => {
    const duplicates: readonly GameCard[] = [
      { ...cards(1)[0], id: 'deck-1:KH', code: 'KH', rank: 'K', suit: 'hearts' },
      { ...cards(1)[0], id: 'deck-2:KH', code: 'KH', rank: 'K', suit: 'hearts' },
    ];
    const fixture = TestBed.createComponent(HandComponent);
    fixture.componentRef.setInput('cards', duplicates);
    fixture.componentRef.setInput('selectedIds', new Set<string>());
    fixture.componentRef.setInput('suggestedIds', new Set(['deck-2:KH']));
    await fixture.whenStable();

    const rendered = (fixture.nativeElement as HTMLElement).querySelectorAll('.playing-card');
    expect(rendered[0].classList).not.toContain('suggested');
    expect(rendered[1].classList).toContain('suggested');
  });
});
