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

  it('uses black styling for clubs and emits its stable physical ID when selected', async () => {
    const fixture = TestBed.createComponent(PlayingCardComponent);
    const card = {
      ...heart,
      id: 'deck-1:6C',
      code: '6C',
      rank: '6',
      suit: 'clubs' as const,
      is_trump: false,
    };
    fixture.componentRef.setInput('card', card);
    fixture.componentRef.setInput('selectable', true);
    const emitted = vi.spyOn(fixture.componentInstance.cardSelected, 'emit');
    await fixture.whenStable();

    expect((fixture.nativeElement as HTMLElement).querySelector('.black')).not.toBeNull();
    (fixture.nativeElement as HTMLElement).querySelector('button')?.click();
    expect(emitted).toHaveBeenCalledWith('deck-1:6C');
  });

  it.each([
    ['red', 'Красный Джокер', 'red'],
    ['black', 'Чёрный Джокер', 'black'],
  ] as const)(
    'renders an accessible %s Joker without exposing its machine code',
    async (color, name, css) => {
      const fixture = TestBed.createComponent(PlayingCardComponent);
      fixture.componentRef.setInput('card', {
        id: `deck-1:joker:${color}`,
        code: color === 'red' ? 'RJ' : 'BJ',
        rank: 'Joker',
        suit: null,
        joker_color: color,
        base_value: 25,
        effective_value: color === 'red' ? 50 : 25,
        is_trump: color === 'red',
      } satisfies GameCard);
      await fixture.whenStable();

      const element = fixture.nativeElement as HTMLElement;
      const face = element.querySelector('.playing-card')!;
      expect(face.getAttribute('aria-label')).toContain(name);
      expect(face.getAttribute('aria-label')).not.toContain(color === 'red' ? 'RJ' : 'BJ');
      expect(element.querySelector(`.${css}`)).not.toBeNull();
      expect(element.textContent).toContain(color === 'red' ? '50' : '25');
    },
  );

  it('marks a suggestion with visible text and an accessible explanation', async () => {
    const fixture = TestBed.createComponent(PlayingCardComponent);
    fixture.componentRef.setInput('card', heart);
    fixture.componentRef.setInput('selectable', true);
    fixture.componentRef.setInput('suggested', true);
    await fixture.whenStable();

    const button = (fixture.nativeElement as HTMLElement).querySelector('button')!;
    expect(button.classList).toContain('suggested');
    expect(button.textContent).toContain('Подходит');
    expect(button.getAttribute('aria-label')).toContain('Подходит к текущей комбинации');
  });

  it.each([
    ['2C', '2', 'clubs', '2', 'треф'],
    ['5H', '5', 'hearts', '5', 'червей'],
  ] as const)(
    'renders Extended suited card %s accessibly',
    async (code, rank, suit, value, name) => {
      const fixture = TestBed.createComponent(PlayingCardComponent);
      fixture.componentRef.setInput('card', {
        id: `deck-1:${code}`,
        code,
        rank,
        suit,
        base_value: Number(value),
        effective_value: Number(value),
        is_trump: false,
      } satisfies GameCard);
      await fixture.whenStable();

      const element = fixture.nativeElement as HTMLElement;
      expect(element.textContent).toContain(rank);
      expect(element.querySelector('.playing-card')?.getAttribute('aria-label')).toContain(name);
    },
  );

  it('keeps disabled Joker selection inert while exposing hint and trump states', async () => {
    const fixture = TestBed.createComponent(PlayingCardComponent);
    fixture.componentRef.setInput('card', {
      id: 'deck-1:joker:red',
      code: 'RJ',
      rank: 'Joker',
      suit: null,
      joker_color: 'red',
      base_value: 25,
      effective_value: 50,
      is_trump: true,
    } satisfies GameCard);
    fixture.componentRef.setInput('selectable', true);
    fixture.componentRef.setInput('disabled', true);
    fixture.componentRef.setInput('suggested', true);
    const emitted = vi.spyOn(fixture.componentInstance.cardSelected, 'emit');
    await fixture.whenStable();

    const button = (fixture.nativeElement as HTMLElement).querySelector('button')!;
    button.click();
    expect(button.disabled).toBe(true);
    expect(button.classList).toContain('suggested');
    expect(button.getAttribute('aria-label')).toContain('козырь');
    expect(emitted).not.toHaveBeenCalled();
  });
});
