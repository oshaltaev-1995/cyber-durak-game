import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { GameCard, SUIT_SYMBOLS } from '../../../core/api/game-api.models';
import { TranslationService } from '../../../core/i18n/translation.service';

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
    return this.i18n.t('game.cardAria', {
      rank: card.rank,
      suit: this.suitName(card.suit),
      value: card.effective_value,
      trump: card.is_trump ? this.i18n.t('game.cardTrumpSuffix') : '',
    });
  });

  protected select(): void {
    if (this.selectable() && !this.disabled()) {
      this.cardSelected.emit(this.card().code);
    }
  }

  private suitName(suit: GameCard['suit']): string {
    return this.i18n.t(`suit.${suit}`);
  }
}
