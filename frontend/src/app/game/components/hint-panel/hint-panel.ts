import { ChangeDetectionStrategy, Component, inject, input, output } from '@angular/core';
import {
  GameCard,
  HintCombination,
  HintReasonType,
  HumanActionType,
} from '../../../core/api/game-api.models';
import { TranslationService } from '../../../core/i18n/translation.service';
import { TranslationKey } from '../../../core/i18n/translations/ru';
import { formatCardShort } from '../../card-presentation';
import { cardIdentity } from '../../../core/deck/deck-config';

@Component({
  selector: 'app-hint-panel',
  templateUrl: './hint-panel.html',
  styleUrl: './hint-panel.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HintPanelComponent {
  protected readonly i18n = inject(TranslationService);
  readonly enabled = input.required<boolean>();
  readonly loading = input(false);
  readonly cards = input<readonly GameCard[]>([]);
  readonly combinations = input<readonly HintCombination[]>([]);
  readonly enabledChange = output<boolean>();

  protected reason(reason: HintReasonType): string {
    return this.i18n.t(`hints.reason.${reason}` as TranslationKey);
  }

  protected action(action: HumanActionType): string {
    return this.i18n.t(`action.${action}` as TranslationKey);
  }

  protected equation(hint: HintCombination): string {
    return hint.target_value === null
      ? `Σ ${hint.selected_value}`
      : `Σ ${hint.selected_value} → ${hint.target_value}`;
  }

  protected hintIds(hint: HintCombination): readonly string[] {
    return hint.physical_card_ids ?? hint.card_ids;
  }

  protected cardExpression(cardIds: readonly string[]): string {
    const cardsById = new Map(this.cards().map((card) => [cardIdentity(card), card]));
    const cards = cardIds.map((id) => cardsById.get(id));
    if (cards.some((card) => card === undefined)) {
      return this.i18n.t('hints.combinationUnavailable');
    }
    return cards
      .map((card) =>
        formatCardShort(card as GameCard, (color) =>
          this.i18n.t(color === 'red' ? 'deck.redJoker' : 'deck.blackJoker'),
        ),
      )
      .join(' + ');
  }
}
