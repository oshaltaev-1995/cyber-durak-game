import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import {
  AttackPacket,
  GameCard,
  TableArithmetic,
  ThrowInReasonType,
} from '../../../core/api/game-api.models';
import { PlayingCardComponent } from '../playing-card/playing-card';
import { TranslationService } from '../../../core/i18n/translation.service';
import { formatCardShort } from '../../card-presentation';

@Component({
  selector: 'app-game-table',
  imports: [PlayingCardComponent],
  templateUrl: './game-table.html',
  styleUrl: './game-table.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameTableComponent {
  protected readonly i18n = inject(TranslationService);
  readonly packets = input.required<readonly AttackPacket[]>();
  readonly arithmetic = input.required<TableArithmetic>();
  readonly activeAttackValue = input.required<number | null>();
  readonly directAnchors = input.required<readonly GameCard[]>();
  readonly final = input(false);

  protected formatExactValue(value: string | null): string {
    return value?.replace('/', ' / ') ?? '—';
  }

  protected reasonLabel(reason: ThrowInReasonType): string {
    return this.i18n.t(`reason.${reason}`);
  }

  protected cardLabel(card: GameCard): string {
    return formatCardShort(card);
  }
}
