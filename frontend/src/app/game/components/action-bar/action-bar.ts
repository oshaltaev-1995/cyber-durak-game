import { ChangeDetectionStrategy, Component, inject, input, output } from '@angular/core';
import { CARD_ACTIONS, GameCard, HumanActionType } from '../../../core/api/game-api.models';
import { TranslationService } from '../../../core/i18n/translation.service';
import { TranslationKey } from '../../../core/i18n/translations/ru';
import { formatCardShort } from '../../card-presentation';
import { cardIdentity } from '../../../core/deck/deck-config';

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
  readonly maxAttackCardAddition = input<number | null>(null);
  readonly pending = input(false);
  readonly bitoMeansPass = input(false);
  readonly actionSelected = output<HumanActionType>();

  protected readonly i18n = inject(TranslationService);
  protected readonly identity = cardIdentity;

  protected selectedTotal(): number {
    return this.selectedCards().reduce((total, card) => total + card.effective_value, 0);
  }

  protected cardLabel(card: GameCard): string {
    return formatCardShort(card, (color) =>
      this.i18n.t(color === 'red' ? 'deck.redJoker' : 'deck.blackJoker'),
    );
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
    if (this.pending() || (CARD_ACTIONS.has(action) && this.selectedCards().length === 0)) {
      return true;
    }
    if (
      (action === 'INITIAL_ATTACK' || action === 'THROW_IN') &&
      this.maxAttackCardAddition() !== null &&
      this.selectedCards().length > (this.maxAttackCardAddition() ?? 0)
    ) {
      return true;
    }
    return action === 'DEFEND' && this.defenseHasRedundantCard();
  }

  protected selectionHint(): string | null {
    const count = this.selectedCards().length;
    if (count === 0) return null;
    const maxAddition = this.maxAttackCardAddition();
    if (
      maxAddition !== null &&
      count > maxAddition &&
      (this.actions().includes('INITIAL_ATTACK') || this.actions().includes('THROW_IN'))
    ) {
      return this.i18n.t('game.selectionTooMany', { count, limit: maxAddition });
    }

    const target = this.activeAttackValue();
    if (target === null) return null;
    const selected = this.selectedTotal();
    if (this.actions().includes('TRANSFER') && selected === target) {
      return this.i18n.t('game.transferMatches', { selected, target });
    }
    if (this.actions().includes('DEFEND')) {
      if (this.defenseHasRedundantCard()) {
        return this.i18n.t('game.defenseRedundant');
      }
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

  private defenseHasRedundantCard(): boolean {
    const target = this.activeAttackValue();
    const selected = this.selectedTotal();
    return (
      target !== null &&
      selected > target &&
      this.selectedCards().some((card) => selected - card.effective_value > target)
    );
  }

  protected actionLabel(action: HumanActionType): string {
    if (action === 'BITO' && this.bitoMeansPass()) return this.i18n.t('action.PASS');
    return this.i18n.t(`action.${action}` as TranslationKey);
  }
}
