import { ComponentFixture, TestBed } from '@angular/core/testing';
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
  const setBaseInputs = (fixture: ComponentFixture<GameTableComponent>) => {
    fixture.componentRef.setInput('arithmetic', {
      total_effective_value: 48,
      physical_card_count: 8,
      arithmetic_mean: '6',
    });
    fixture.componentRef.setInput('activeAttackValue', 6);
    fixture.componentRef.setInput('directAnchors', []);
  };

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
    expect(getComputedStyle(viewport).scrollbarGutter).toBe('stable');
    expect(getComputedStyle(viewport).getPropertyValue('--scrollbar-safe-zone')).toBe('0.85rem');
    expect(viewport.tabIndex).toBe(0);
  });

  it('uses the full packet row for a normal five-card attack and four-card defense', async () => {
    const fixture = TestBed.createComponent(GameTableComponent);
    const attackCards = Array.from({ length: 5 }, (_, index) => ({
      ...card,
      id: `attack-${index}`,
      code: `${index + 6}C`,
    }));
    const defenseCards = Array.from({ length: 4 }, (_, index) => ({
      ...card,
      id: `defense-${index}`,
      code: `${index + 7}H`,
    }));
    fixture.componentRef.setInput('packets', [
      {
        attack_cards: attackCards,
        attack_value: 50,
        defense_cards: defenseCards,
        defense_value: 57,
        closed: true,
        throw_in_reasons: [],
      },
    ]);
    setBaseInputs(fixture);
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelectorAll('.packet')).toHaveLength(1);
    expect(element.querySelectorAll('.attack-side app-playing-card')).toHaveLength(5);
    expect(element.querySelectorAll('.defense-side app-playing-card')).toHaveLength(4);
    for (const strip of element.querySelectorAll<HTMLElement>('.packet-cards')) {
      expect(getComputedStyle(strip).overflowX).not.toBe('auto');
    }
  });

  it.each([
    [5, 0, false, false],
    [7, 5, false, false],
    [5, 4, true, false],
    [5, 4, false, true],
  ] as const)(
    'renders packet fixture attack=%i defense=%i duplicate=%s joker=%s without nested scrolling',
    async (attackCount, defenseCount, duplicateFace, includeJoker) => {
      const fixture = TestBed.createComponent(GameTableComponent);
      const fixtureCard = (index: number, group: 'attack' | 'defense'): GameCard => ({
        ...card,
        id: `${group}-${index}`,
        code: duplicateFace && index === 1 ? '6C' : `${index + 6}${group === 'attack' ? 'C' : 'H'}`,
        ...(includeJoker && index === 0
          ? {
              code: 'RJ',
              rank: 'JOKER' as const,
              suit: null,
              joker_color: 'red' as const,
              base_value: 25,
              effective_value: 50,
              is_trump: true,
            }
          : {}),
      });
      const attackCards = Array.from({ length: attackCount }, (_, index) =>
        fixtureCard(index, 'attack'),
      );
      const defenseCards = Array.from({ length: defenseCount }, (_, index) =>
        fixtureCard(index, 'defense'),
      );
      fixture.componentRef.setInput('packets', [
        {
          attack_cards: attackCards,
          attack_value: 50,
          defense_cards: defenseCards,
          defense_value: defenseCount === 0 ? null : 57,
          closed: defenseCount > 0,
          throw_in_reasons: [],
        },
      ]);
      setBaseInputs(fixture);
      await fixture.whenStable();

      const element = fixture.nativeElement as HTMLElement;
      expect(element.querySelectorAll('.attack-side app-playing-card')).toHaveLength(attackCount);
      expect(element.querySelectorAll('.defense-side app-playing-card')).toHaveLength(defenseCount);
      for (const strip of element.querySelectorAll<HTMLElement>('.packet-cards')) {
        expect(getComputedStyle(strip).overflowX).not.toBe('auto');
        expect(getComputedStyle(strip).flexWrap).toBe('wrap');
      }
    },
  );

  it('renders a terminal TAKE packet as resolved rather than active or awaiting', async () => {
    const fixture = TestBed.createComponent(GameTableComponent);
    fixture.componentRef.setInput('packets', [packet(6)]);
    fixture.componentRef.setInput('final', true);
    fixture.componentRef.setInput('finalOutcome', 'TAKE');
    setBaseInputs(fixture);
    await fixture.whenStable();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Забран');
    expect(text).not.toContain('Активен');
    expect(text).not.toContain('Ожидает ответа');
    expect(fixture.nativeElement.classList).toContain('final');
  });

  it('renders terminal successful defense as covered with an auto-height table', async () => {
    const fixture = TestBed.createComponent(GameTableComponent);
    fixture.componentRef.setInput('packets', [
      {
        ...packet(6),
        defense_cards: [{ ...card, id: 'defense-7H', code: '7H' }],
        defense_value: 7,
        closed: true,
      },
    ]);
    fixture.componentRef.setInput('final', true);
    fixture.componentRef.setInput('finalOutcome', 'BITO');
    setBaseInputs(fixture);
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Покрыт');
    expect(element.textContent).not.toContain('Активен');
    expect(element.textContent).not.toContain('Ожидает ответа');
    expect(getComputedStyle(element.querySelector('.table') as HTMLElement).height).toBe('auto');
  });

  it('keeps a long terminal bout vertically bounded and every packet resolved', async () => {
    const fixture = TestBed.createComponent(GameTableComponent);
    fixture.componentRef.setInput(
      'packets',
      Array.from({ length: 12 }, (_, index) => ({ ...packet(index + 6), closed: true })),
    );
    fixture.componentRef.setInput('final', true);
    fixture.componentRef.setInput('finalOutcome', 'BITO');
    setBaseInputs(fixture);
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelectorAll('.packet')).toHaveLength(12);
    expect(element.querySelector('.packet.active')).toBeNull();
    expect(element.textContent).not.toContain('Ожидает ответа');
    expect(getComputedStyle(element.querySelector('.table') as HTMLElement).maxHeight).toBe(
      '32rem',
    );
  });
});
