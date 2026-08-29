import { ChangeDetectionStrategy, Component, inject, input, output } from '@angular/core';
import {
  CARD_ACTIONS,
  GameCard,
  HumanActionType,
  SUIT_SYMBOLS,
} from '../../../core/api/game-api.models';
import { TranslationService } from '../../../core/i18n/translation.service';
import { TranslationKey } from '../../../core/i18n/translations/ru';

@Component({
  selector: 'app-action-bar',
  templateUrl: './action-bar.html',
  styleUrl: './action-bar.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ActionBarComponent {
  readonly actions = input.required<readonly HumanActionType[]>();
  readonly selectedCards = input.required<readonly GameCard[]>();
  readonly pending = input(false);
  readonly actionSelected = output<HumanActionType>();

  protected readonly i18n = inject(TranslationService);

  protected selectedTotal(): number {
    return this.selectedCards().reduce((total, card) => total + card.effective_value, 0);
  }

  protected cardLabel(card: GameCard): string {
    return `${card.rank}${SUIT_SYMBOLS[card.suit]}`;
  }

  protected selectionValuesExpression(): string {
    const cards = this.selectedCards();
    if (cards.length === 0) {
      return this.i18n.t('game.selectCards');
    }
    const values = cards.map((card) => card.effective_value).join(' + ');
    return `${values} = ${this.selectedTotal()}`;
  }

  protected selectionAriaLabel(): string {
    const cards = this.selectedCards();
    if (cards.length === 0) {
      return this.i18n.t('game.noCardsSelected');
    }
    return this.i18n.t('game.selectionAria', {
      count: cards.length,
      cards: cards.map((card) => this.cardLabel(card)).join(', '),
      total: this.selectedTotal(),
    });
  }

  protected actionDisabled(action: HumanActionType): boolean {
    return this.pending() || (CARD_ACTIONS.has(action) && this.selectedCards().length === 0);
  }

  protected actionLabel(action: HumanActionType): string {
    return this.i18n.t(`action.${action}` as TranslationKey);
  }
}
