import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { GameCard, SUIT_SYMBOLS, TrumpState } from '../../../core/api/game-api.models';
import { PlayingCardComponent } from '../playing-card/playing-card';

@Component({
  selector: 'app-trump-indicator',
  imports: [PlayingCardComponent],
  templateUrl: './trump-indicator.html',
  styleUrl: './trump-indicator.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrumpIndicatorComponent {
  readonly trump = input.required<TrumpState>();
  readonly exposedCard = input.required<GameCard | null>();
  readonly drawPileCount = input.required<number>();

  protected readonly explanation = computed(() => {
    const trump = this.trump();
    if (!trump.active || trump.trump_suit === null || trump.trump_rank === null) {
      return 'Козырей нет';
    }
    return `${SUIT_SYMBOLS[trump.trump_suit]} и все ${trump.trump_rank}`;
  });
}
