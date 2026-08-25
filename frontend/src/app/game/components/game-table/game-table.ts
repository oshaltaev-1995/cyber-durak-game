import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { AttackPacket, GameCard, TableArithmetic } from '../../../core/api/game-api.models';
import { PlayingCardComponent } from '../playing-card/playing-card';

@Component({
  selector: 'app-game-table',
  imports: [PlayingCardComponent],
  templateUrl: './game-table.html',
  styleUrl: './game-table.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameTableComponent {
  readonly packets = input.required<readonly AttackPacket[]>();
  readonly arithmetic = input.required<TableArithmetic>();
  readonly activeAttackValue = input.required<number | null>();
  readonly directAnchors = input.required<readonly GameCard[]>();
}
