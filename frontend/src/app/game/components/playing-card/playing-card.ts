import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { GameCard, SUIT_SYMBOLS } from '../../../core/api/game-api.models';

@Component({
  selector: 'app-playing-card',
  imports: [NgTemplateOutlet],
  templateUrl: './playing-card.html',
  styleUrl: './playing-card.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlayingCardComponent {
  readonly card = input.required<GameCard>();
  readonly selected = input(false);
  readonly selectable = input(false);
  readonly compact = input(false);
  readonly disabled = input(false);
  readonly cardSelected = output<string>();

  protected readonly suitSymbol = computed(() => SUIT_SYMBOLS[this.card().suit]);
  protected readonly colorClass = computed(() =>
    this.card().suit === 'hearts' || this.card().suit === 'diamonds' ? 'red' : 'black',
  );
  protected readonly accessibleLabel = computed(() => {
    const card = this.card();
    const trump = card.is_trump ? ', козырь' : '';
    return `${card.rank} ${this.suitName(card.suit)}, значение ${card.effective_value}${trump}`;
  });

  protected select(): void {
    if (this.selectable() && !this.disabled()) {
      this.cardSelected.emit(this.card().code);
    }
  }

  private suitName(suit: GameCard['suit']): string {
    return {
      clubs: 'треф',
      diamonds: 'бубен',
      hearts: 'червей',
      spades: 'пик',
    }[suit];
  }
}
