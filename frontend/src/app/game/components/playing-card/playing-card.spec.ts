import { TestBed } from '@angular/core/testing';
import { GameCard } from '../../../core/api/game-api.models';
import { PlayingCardComponent } from './playing-card';

const heart: GameCard = {
  code: '9H',
  rank: '9',
  suit: 'hearts',
  base_value: 9,
  effective_value: 18,
  is_trump: true,
};

describe('PlayingCardComponent', () => {
  it('renders rank, suit, trump value, and accessible state', async () => {
    const fixture = TestBed.createComponent(PlayingCardComponent);
    fixture.componentRef.setInput('card', heart);
    fixture.componentRef.setInput('selectable', true);
    fixture.componentRef.setInput('selected', true);
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    const button = element.querySelector('button') as HTMLButtonElement;
    expect(element.textContent).toContain('9');
    expect(element.textContent).toContain('♥');
    expect(element.textContent).toContain('18');
    expect(element.textContent).toContain('Козырь');
    expect(element.querySelector('.red')).not.toBeNull();
    expect(button.classList).toContain('selected');
    expect(button.getAttribute('aria-pressed')).toBe('true');
    expect(button.getAttribute('aria-label')).toContain('значение 18, козырь');
  });

  it('uses black styling for clubs and emits its stable card code when selected', async () => {
    const fixture = TestBed.createComponent(PlayingCardComponent);
    const card = { ...heart, code: '6C', rank: '6', suit: 'clubs' as const, is_trump: false };
    fixture.componentRef.setInput('card', card);
    fixture.componentRef.setInput('selectable', true);
    const emitted = vi.spyOn(fixture.componentInstance.cardSelected, 'emit');
    await fixture.whenStable();

    expect((fixture.nativeElement as HTMLElement).querySelector('.black')).not.toBeNull();
    (fixture.nativeElement as HTMLElement).querySelector('button')?.click();
    expect(emitted).toHaveBeenCalledWith('6C');
  });
});
