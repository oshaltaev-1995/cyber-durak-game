import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { GameCard, SUIT_SYMBOLS } from '../../../core/api/game-api.models';
import { CardMotion } from '../../presentation/card-motion';

@Component({
  selector: 'app-card-motion-overlay',
  templateUrl: './card-motion-overlay.html',
  styleUrl: './card-motion-overlay.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CardMotionOverlayComponent {
  readonly motions = input.required<readonly CardMotion[]>();
  protected readonly suitSymbols = SUIT_SYMBOLS;
  protected cardSymbol(card: GameCard): string {
    return card.joker_color ? '★' : card.suit === null ? '' : SUIT_SYMBOLS[card.suit];
  }
}
