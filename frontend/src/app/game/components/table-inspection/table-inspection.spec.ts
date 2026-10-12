import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AttackPacket, GameCard } from '../../../core/api/game-api.models';
import { TableInspectionComponent } from './table-inspection';

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

const packet: AttackPacket = {
  attack_cards: [card],
  attack_value: 6,
  defense_cards: [],
  defense_value: null,
  closed: false,
  throw_in_reasons: [],
};

describe('TableInspectionComponent', () => {
  let fixture: ComponentFixture<TableInspectionComponent>;

  beforeEach(async () => {
    fixture = TestBed.createComponent(TableInspectionComponent);
    fixture.componentRef.setInput('packets', [packet]);
    fixture.componentRef.setInput('arithmetic', {
      total_effective_value: 6,
      physical_card_count: 1,
      arithmetic_mean: '6',
    });
    fixture.componentRef.setInput('activeAttackValue', 6);
    fixture.componentRef.setInput('directAnchors', [card]);
    fixture.componentRef.setInput('participants', [
      {
        id: 'local',
        name: 'Олег',
        cardCount: 7,
        isBot: false,
        isLocal: true,
        roles: ['Защитник'],
      },
      {
        id: 'bot',
        name: 'Milo',
        cardCount: 5,
        isBot: true,
        isLocal: false,
        roles: ['Текущий атакующий'],
      },
    ]);
    fixture.componentRef.setInput('drawPileCount', 20);
    fixture.componentRef.setInput('discardCount', 4);
    fixture.componentRef.setInput('exposedTopCard', card);
    fixture.componentRef.setInput('actorCue', 'Milo атакует…');
    fixture.componentRef.setInput('humanTurn', true);
    await fixture.whenStable();
  });

  it('opens a live expanded table with participant/context HUD and no duplicate action UI', async () => {
    const element = fixture.nativeElement as HTMLElement;
    const trigger = element.querySelector<HTMLButtonElement>('.expand-table')!;
    trigger.click();
    fixture.detectChanges();
    await fixture.whenStable();

    const dialog = element.querySelector('dialog')!;
    expect(dialog.hasAttribute('open')).toBe(true);
    expect(dialog.textContent).toContain('Стол крупным планом');
    expect(dialog.textContent).toContain('Олег');
    expect(dialog.textContent).toContain('Milo');
    expect(dialog.textContent).toContain('Колода 20');
    expect(dialog.textContent).toContain('Бито 4');
    expect(dialog.textContent).toContain('Milo атакует');
    expect(dialog.textContent).toContain('Ваш ход — сверните стол');
    expect(dialog.querySelector('app-action-bar')).toBeNull();
    expect(dialog.querySelector('.expanded-table .table')?.getAttribute('tabindex')).toBe('0');

    fixture.componentRef.setInput('discardCount', 5);
    fixture.detectChanges();
    expect(dialog.textContent).toContain('Бито 5');
  });

  it('closes on Escape and returns focus to the entry control', async () => {
    const element = fixture.nativeElement as HTMLElement;
    const trigger = element.querySelector<HTMLButtonElement>('.expand-table')!;
    trigger.click();
    fixture.detectChanges();
    await fixture.whenStable();

    const dialog = element.querySelector('dialog')!;
    dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    fixture.detectChanges();
    await fixture.whenStable();

    expect(dialog.hasAttribute('open')).toBe(false);
    expect(document.activeElement).toBe(trigger);
  });
});
