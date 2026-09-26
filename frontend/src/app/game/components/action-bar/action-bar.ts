import { ChangeDetectionStrategy, Component, inject, input, output } from '@angular/core';
import { CARD_ACTIONS, GameCard, HumanActionType } from '../../../core/api/game-api.models';
import { TranslationService } from '../../../core/i18n/translation.service';
import { TranslationKey } from '../../../core/i18n/translations/ru';
import { formatCardShort } from '../../card-presentation';

@Component({
  selector: 'app-action-bar',
  templateUrl: './action-bar.html',
  styleUrl: './action-bar.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ActionBarComponent {
  readonly actions = input.required<readonly HumanActionType[]>();
  readonly selectedCards = input.required<readonly GameCard[]>();
  readonly activeAttackValue = input<number | null>(null);
  readonly attackCardLimit = input<number | null>(null);
  readonly totalAttackCardCount = input<number | null>(null);
  readonly pending = input(false);
  readonly actionSelected = output<HumanActionType>();

  protected readonly i18n = inject(TranslationService);

  protected selectedTotal(): number {
    return this.selectedCards().reduce((total, card) => total + card.effective_value, 0);
  }

  protected cardLabel(card: GameCard): string {
    return formatCardShort(card);
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

  protected selectionHint(): string | null {
    const count = this.selectedCards().length;
    if (count === 0) return null;
    const limit = this.attackCardLimit();
    const used = this.totalAttackCardCount() ?? 0;
    const remaining = limit === null ? null : Math.max(0, limit - used);
    if (
      remaining !== null &&
      count > remaining &&
      (this.actions().includes('INITIAL_ATTACK') || this.actions().includes('THROW_IN'))
    ) {
      return this.i18n.t('game.selectionTooMany', { count, limit: remaining });
    }

    const target = this.activeAttackValue();
    if (target === null) return null;
    const selected = this.selectedTotal();
    if (this.actions().includes('TRANSFER') && selected === target) {
      return this.i18n.t('game.transferMatches', { selected, target });
    }
    if (this.actions().includes('DEFEND')) {
      return this.i18n.t(selected > target ? 'game.defenseEnough' : 'game.defenseNeedsMore', {
        selected,
        target,
      });
    }
    if (this.actions().includes('TRANSFER')) {
      return this.i18n.t(selected === target ? 'game.transferMatches' : 'game.transferNeedsExact', {
        selected,
        target,
      });
    }
    return null;
  }

  protected actionLabel(action: HumanActionType): string {
    return this.i18n.t(`action.${action}` as TranslationKey);
  }
}
