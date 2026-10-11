import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { GameCard, SUIT_SYMBOLS } from '../../../core/api/game-api.models';
import { TranslationService } from '../../../core/i18n/translation.service';
import { cardIdentity } from '../../../core/deck/deck-config';

@Component({
  selector: 'app-playing-card',
  imports: [NgTemplateOutlet],
  templateUrl: './playing-card.html',
  styleUrl: './playing-card.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlayingCardComponent {
  protected readonly i18n = inject(TranslationService);
  readonly card = input.required<GameCard>();
  readonly selected = input(false);
  readonly continuation = input(false);
  readonly suggested = input(false);
  readonly selectable = input(false);
  readonly compact = input(false);
  readonly dense = input(false);
  readonly showValueBadge = input(true);
  readonly announceValue = input(true);
  readonly contextLabel = input<string | null>(null);
  readonly disabled = input(false);
  readonly cardSelected = output<string>();

  protected readonly suitSymbol = computed(() => {
    const suit = this.card().suit;
    return suit === null ? '' : SUIT_SYMBOLS[suit];
  });
  protected readonly isJoker = computed(
    () => this.card().joker_color !== null && this.card().joker_color !== undefined,
  );
  protected readonly colorClass = computed(() =>
    this.card().joker_color === 'red' ||
    this.card().suit === 'hearts' ||
    this.card().suit === 'diamonds'
      ? 'red'
      : 'black',
  );
  protected readonly accessibleLabel = computed(() => {
    const card = this.card();
    const label = this.announceValue()
      ? card.joker_color
        ? this.i18n.t('game.jokerAria', {
            joker: this.i18n.t(card.joker_color === 'red' ? 'deck.redJoker' : 'deck.blackJoker'),
            value: card.effective_value,
            trump: card.is_trump ? this.i18n.t('game.cardTrumpSuffix') : '',
          })
        : this.i18n.t('game.cardAria', {
            rank: card.rank,
            suit: this.suitName(card.suit),
            value: card.effective_value,
            trump: card.is_trump ? this.i18n.t('game.cardTrumpSuffix') : '',
          })
      : card.joker_color
        ? this.i18n.t(card.joker_color === 'red' ? 'deck.redJoker' : 'deck.blackJoker')
        : `${card.rank} ${this.suitName(card.suit)}`;
    const contextual = this.contextLabel() === null ? label : `${this.contextLabel()}. ${label}`;
    if (this.suggested()) return `${contextual}. ${this.i18n.t('hints.suggestedAria')}`;
    return this.continuation()
      ? `${contextual}. ${this.i18n.t('hints.continuationAria')}`
      : contextual;
  });

  protected select(): void {
    if (this.selectable() && !this.disabled()) {
      this.cardSelected.emit(cardIdentity(this.card()));
    }
  }

  private suitName(suit: GameCard['suit']): string {
    return suit === null ? '' : this.i18n.t(`suit.${suit}`);
  }
}
