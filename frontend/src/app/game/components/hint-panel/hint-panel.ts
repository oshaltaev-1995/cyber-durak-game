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

  protected cardExpression(cardIds: readonly string[]): string {
    const cardsByCode = new Map(this.cards().map((card) => [card.code, card]));
    const cards = cardIds.map((code) => cardsByCode.get(code));
    if (cards.some((card) => card === undefined)) {
      return this.i18n.t('hints.combinationUnavailable');
    }
    return cards.map((card) => formatCardShort(card as GameCard)).join(' + ');
  }
}
