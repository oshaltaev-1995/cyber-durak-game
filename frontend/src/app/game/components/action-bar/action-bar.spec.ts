import { TestBed } from '@angular/core/testing';
import { GameCard } from '../../../core/api/game-api.models';
import { ActionBarComponent } from './action-bar';

const cards = (count: number): readonly GameCard[] =>
  Array.from({ length: count }, (_, index) => ({
    id: `deck-${index < 5 ? 1 : 2}:${index}`,
    code: `${(index % 9) + 2}C`,
    rank: String((index % 9) + 2),
    suit: 'clubs',
    base_value: (index % 9) + 2,
    effective_value: (index % 9) + 2,
    is_trump: false,
  }));

describe('ActionBarComponent', () => {
  it('uses the authoritative addition cap instead of a fixed seven-card UI limit', async () => {
    const fixture = TestBed.createComponent(ActionBarComponent);
    fixture.componentRef.setInput('actions', ['INITIAL_ATTACK']);
    fixture.componentRef.setInput('selectedCards', cards(10));
    fixture.componentRef.setInput('maxAttackCardAddition', 10);
    await fixture.whenStable();

    let button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      '.actions button',
    )!;
    expect(button.disabled).toBe(false);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Выбрано: 10');

    fixture.componentRef.setInput('selectedCards', cards(11));
    fixture.detectChanges();
    button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      '.actions button',
    )!;
    expect(button.disabled).toBe(true);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('остаток лимита атаки 10');
  });
});
