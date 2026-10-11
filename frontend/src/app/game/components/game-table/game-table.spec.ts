import { TestBed } from '@angular/core/testing';
import { AttackPacket, GameCard } from '../../../core/api/game-api.models';
import { GameTableComponent } from './game-table';

const card: GameCard = {
  id: 'deck-1:6C',
  code: '6C',
  rank: '6',
  suit: 'clubs',
  joker_color: null,
  base_value: 6,
  effective_value: 6,
  is_trump: false,
};

const packet = (index: number): AttackPacket => ({
  attack_cards: [{ ...card, id: `deck-1:${index}C`, code: `${index}C` }],
  attack_value: index,
  defense_cards: [],
  defense_value: null,
  closed: false,
  throw_in_reasons: [],
});

describe('GameTableComponent scroll follow', () => {
  it('keeps new packets visible only while the reader remains near the bottom', async () => {
    const fixture = TestBed.createComponent(GameTableComponent);
    fixture.componentRef.setInput(
      'packets',
      Array.from({ length: 8 }, (_, index) => packet(index)),
    );
    fixture.componentRef.setInput('arithmetic', {
      total_effective_value: 48,
      physical_card_count: 8,
      arithmetic_mean: '6',
    });
    fixture.componentRef.setInput('activeAttackValue', 6);
    fixture.componentRef.setInput('directAnchors', []);
    await fixture.whenStable();

    const viewport = (fixture.nativeElement as HTMLElement).querySelector('.table') as HTMLElement;
    Object.defineProperties(viewport, {
      scrollHeight: { configurable: true, value: 900 },
      clientHeight: { configurable: true, value: 300 },
    });
    viewport.scrollTop = 600;
    fixture.componentRef.setInput('packets', [
      ...Array.from({ length: 8 }, (_, index) => packet(index)),
      packet(9),
    ]);
    fixture.detectChanges();
    expect(viewport.scrollTop).toBe(900);

    viewport.scrollTop = 100;
    viewport.dispatchEvent(new Event('scroll'));
    fixture.componentRef.setInput('packets', [
      ...Array.from({ length: 9 }, (_, index) => packet(index)),
      packet(10),
    ]);
    fixture.detectChanges();
    expect(viewport.scrollTop).toBe(100);
    expect(getComputedStyle(viewport).overflowY).toBe('auto');
    expect(viewport.tabIndex).toBe(0);
  });
});
