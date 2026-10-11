import {
  AfterViewChecked,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  ViewChild,
  inject,
  input,
} from '@angular/core';
import {
  AttackPacket,
  GameCard,
  TableArithmetic,
  ThrowInReasonType,
} from '../../../core/api/game-api.models';
import { PlayingCardComponent } from '../playing-card/playing-card';
import { TranslationService } from '../../../core/i18n/translation.service';
import { formatCardShort } from '../../card-presentation';
import { cardIdentity } from '../../../core/deck/deck-config';

@Component({
  selector: 'app-game-table',
  imports: [PlayingCardComponent],
  templateUrl: './game-table.html',
  styleUrl: './game-table.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[class.final]': 'final()' },
})
export class GameTableComponent implements AfterViewChecked {
  @ViewChild('scrollViewport') private scrollViewport?: ElementRef<HTMLElement>;
  protected readonly i18n = inject(TranslationService);
  readonly packets = input.required<readonly AttackPacket[]>();
  readonly arithmetic = input.required<TableArithmetic>();
  readonly activeAttackValue = input.required<number | null>();
  readonly directAnchors = input.required<readonly GameCard[]>();
  readonly final = input(false);
  readonly finalOutcome = input<'TAKE' | 'BITO' | null>(null);
  protected readonly identity = cardIdentity;
  private followLatest = true;
  private renderedSignature = '';

  ngAfterViewChecked(): void {
    const signature = this.packets()
      .map((packet) =>
        [...packet.attack_cards, ...packet.defense_cards].map(cardIdentity).join(','),
      )
      .join('|');
    if (signature === this.renderedSignature) return;
    this.renderedSignature = signature;
    const viewport = this.scrollViewport?.nativeElement;
    if (viewport !== undefined && this.followLatest) viewport.scrollTop = viewport.scrollHeight;
  }

  protected trackScroll(): void {
    const viewport = this.scrollViewport?.nativeElement;
    if (viewport === undefined) return;
    this.followLatest = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 48;
  }

  protected formatExactValue(value: string | null): string {
    return value?.replace('/', ' / ') ?? '—';
  }

  protected reasonLabel(reason: ThrowInReasonType): string {
    return this.i18n.t(`reason.${reason}`);
  }

  protected cardLabel(card: GameCard): string {
    return formatCardShort(card, (color) =>
      this.i18n.t(color === 'red' ? 'deck.redJoker' : 'deck.blackJoker'),
    );
  }
}
