import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { GameCard, SUIT_SYMBOLS, TrumpState } from '../../../core/api/game-api.models';
import { PlayingCardComponent } from '../playing-card/playing-card';
import { TranslationService } from '../../../core/i18n/translation.service';

@Component({
  selector: 'app-trump-indicator',
  imports: [PlayingCardComponent],
  templateUrl: './trump-indicator.html',
  styleUrl: './trump-indicator.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrumpIndicatorComponent {
  protected readonly i18n = inject(TranslationService);
  readonly trump = input.required<TrumpState>();
  readonly exposedCard = input.required<GameCard | null>();
  readonly drawPileCount = input.required<number>();

  protected readonly explanation = computed(() => {
    const trump = this.trump();
    const source = this.exposedCard();
    if (!trump.active || source === null) {
      return this.i18n.t('game.noTrump');
    }
    if (source.joker_color === 'red') return this.i18n.t('game.trumpRedJokerPattern');
    if (source.joker_color === 'black') return this.i18n.t('game.trumpBlackJokerPattern');
    if (trump.trump_suit === null || trump.trump_rank === null) return this.i18n.t('game.noTrump');
    return this.i18n.t('game.trumpPattern', {
      suit: SUIT_SYMBOLS[trump.trump_suit],
      rank: trump.trump_rank,
    });
  });
}
