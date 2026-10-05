import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GameCard, HintCombination } from '../../../core/api/game-api.models';
import { TranslationService } from '../../../core/i18n/translation.service';
import { HintPanelComponent } from './hint-panel';

const card = (code: string, rank: string, suit: GameCard['suit'], value: number): GameCard => ({
  code,
  rank,
  suit,
  base_value: value,
  effective_value: value,
  is_trump: false,
});

const cards = [
  card('6S', '6', 'spades', 6),
  card('7H', '7', 'hearts', 7),
  card('10C', '10', 'clubs', 10),
  card('JD', 'J', 'diamonds', 12),
  card('QS', 'Q', 'spades', 15),
  card('KC', 'K', 'clubs', 18),
];

const combinations: readonly HintCombination[] = [
  {
    action: 'INITIAL_ATTACK',
    card_ids: ['6S', '7H'],
    added_card_ids: ['7H'],
    reason: 'arithmetic_equality',
    selected_value: 13,
    target_value: null,
  },
  {
    action: 'DEFEND',
    card_ids: ['10C', 'JD'],
    added_card_ids: ['JD'],
    reason: 'defense_total',
    selected_value: 22,
    target_value: 18,
  },
  {
    action: 'TRANSFER',
    card_ids: ['QS'],
    added_card_ids: [],
    reason: 'transfer_exact',
    selected_value: 15,
    target_value: 15,
  },
  {
    action: 'THROW_IN',
    card_ids: ['JD', 'KC'],
    added_card_ids: ['KC'],
    reason: 'latest_defense_ranks',
    selected_value: 30,
    target_value: null,
  },
];

describe('HintPanelComponent', () => {
  let fixture: ComponentFixture<HintPanelComponent>;
  let i18n: TranslationService;

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({ imports: [HintPanelComponent] }).compileComponents();
    fixture = TestBed.createComponent(HintPanelComponent);
    i18n = TestBed.inject(TranslationService);
    fixture.componentRef.setInput('enabled', true);
    fixture.componentRef.setInput('cards', cards);
    fixture.componentRef.setInput('combinations', combinations);
  });

  for (const locale of ['en', 'ru'] as const) {
    it(`uses Unicode card notation for every hint action in ${locale}`, () => {
      i18n.setLocale(locale);
      fixture.detectChanges();
      const panel = (fixture.nativeElement as HTMLElement).querySelector('.hint-panel')!;
      const text = panel.textContent ?? '';

      expect(text).toContain('6♠ + 7♥');
      expect(text).toContain('10♣ + J♦');
      expect(text).toContain('Q♠');
      expect(text).toContain('J♦ + K♣');
      expect(text).not.toMatch(/(?:10|[6-9JQKA])[CDHS](?![a-z])/);
      expect(panel.outerHTML).not.toMatch(/(?:aria-label|title)="[^"]*(?:10|[6-9JQKA])[CDHS]/);
    });
  }

  it('uses a safe generic label when a structured hand card is unavailable', () => {
    fixture.componentRef.setInput(
      'cards',
      cards.filter((value) => value.code !== 'KC'),
    );
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).querySelector('.hint-panel')?.textContent;

    expect(text).toContain('Legal combination');
    expect(text).not.toContain('KC');
  });
});
