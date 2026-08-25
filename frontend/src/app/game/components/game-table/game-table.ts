import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import {
  AttackPacket,
  GameCard,
  TableArithmetic,
  ThrowInReasonType,
} from '../../../core/api/game-api.models';
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
  readonly final = input(false);

  protected formatExactValue(value: string | null): string {
    return value?.replace('/', ' / ') ?? '—';
  }

  protected reasonLabel(reason: ThrowInReasonType): string {
    return {
      same_rank: 'Подкинуто по рангу',
      existing_value: 'Подкинуто по доступному значению',
      table_total: 'Подкинуто по сумме стола',
      arithmetic_mean: 'Подкинуто по среднему',
    }[reason];
  }
}
