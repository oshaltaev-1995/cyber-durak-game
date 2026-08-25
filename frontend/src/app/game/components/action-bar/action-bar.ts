import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import {
  ACTION_LABELS,
  CARD_ACTIONS,
  GameCard,
  HumanActionType,
} from '../../../core/api/game-api.models';

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

  protected readonly labels = ACTION_LABELS;

  protected selectedTotal(): number {
    return this.selectedCards().reduce((total, card) => total + card.effective_value, 0);
  }

  protected selectionExpression(): string {
    const cards = this.selectedCards();
    if (cards.length === 0) {
      return 'Выберите одну или несколько карт';
    }
    const codes = cards.map((card) => card.code).join(' + ');
    const values = cards.map((card) => card.effective_value).join(' + ');
    return `${codes} · ${values} = ${this.selectedTotal()}`;
  }

  protected actionDisabled(action: HumanActionType): boolean {
    return this.pending() || (CARD_ACTIONS.has(action) && this.selectedCards().length === 0);
  }
}
