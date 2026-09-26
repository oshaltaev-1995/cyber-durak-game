import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { SUIT_SYMBOLS } from '../../../core/api/game-api.models';
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
}
