import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { GameCard } from '../../../core/api/game-api.models';
import { PlayingCardComponent } from '../playing-card/playing-card';

@Component({
  selector: 'app-hand',
  imports: [PlayingCardComponent],
  templateUrl: './hand.html',
  styleUrl: './hand.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HandComponent {
  readonly cards = input.required<readonly GameCard[]>();
  readonly selectedCodes = input.required<ReadonlySet<string>>();
  readonly disabled = input(false);
  readonly cardSelected = output<string>();
}
