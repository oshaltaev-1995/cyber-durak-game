import {
  AfterViewChecked,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  ViewChild,
  inject,
  input,
  output,
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
  host: { '[class.final]': 'final()', '[class.expanded]': 'expanded()' },
})
export class GameTableComponent implements AfterViewChecked {
  @ViewChild('scrollViewport') private scrollViewport?: ElementRef<HTMLElement>;
  @ViewChild('expandControl') private expandControl?: ElementRef<HTMLButtonElement>;
  protected readonly i18n = inject(TranslationService);
  readonly packets = input.required<readonly AttackPacket[]>();
  readonly arithmetic = input.required<TableArithmetic>();
  readonly activeAttackValue = input.required<number | null>();
  readonly directAnchors = input.required<readonly GameCard[]>();
  readonly final = input(false);
  readonly finalOutcome = input<'TAKE' | 'BITO' | null>(null);
  readonly observer = input(false);
  readonly followContextKey = input<string | null>(null);
  readonly expanded = input(false);
  readonly showExpandControl = input(false);
  readonly expandRequested = output<void>();
  protected readonly identity = cardIdentity;
  private followLatest = true;
  private renderedSignature = '';
  private renderedPacketAnchor = '';
  private renderedFollowContext: string | null = null;
  private programmaticScrollTop: number | null = null;

  ngAfterViewChecked(): void {
    const packets = this.packets();
    const signature = packets
      .map((packet) =>
        [...packet.attack_cards, ...packet.defense_cards].map(cardIdentity).join(','),
      )
      .join('|');
    const activeIndex = packets.findIndex((packet) => !packet.closed);
    const packetAnchor = `${packets.length}:${activeIndex}`;
    const followContext = this.followContextKey();
    const packetAnchorChanged = packetAnchor !== this.renderedPacketAnchor;
    const followContextChanged =
      followContext !== null && followContext !== this.renderedFollowContext;
    if (signature === this.renderedSignature && !packetAnchorChanged && !followContextChanged)
      return;
    this.renderedSignature = signature;
    this.renderedPacketAnchor = packetAnchor;
    this.renderedFollowContext = followContext;
    const viewport = this.scrollViewport?.nativeElement;
    if (viewport !== undefined && this.final()) {
      viewport.style.removeProperty('--live-follow-space');
      return;
    }
    if (
      viewport !== undefined &&
      this.followLatest &&
      packets.length > 0 &&
      (packetAnchorChanged || followContextChanged)
    ) {
      this.positionCurrentPacket(viewport);
    }
  }

  protected trackScroll(): void {
    const viewport = this.scrollViewport?.nativeElement;
    if (viewport === undefined) return;
    if (
      this.programmaticScrollTop !== null &&
      Math.abs(viewport.scrollTop - this.programmaticScrollTop) < 1
    ) {
      this.programmaticScrollTop = null;
      return;
    }
    this.programmaticScrollTop = null;
    this.followLatest = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 48;
  }

  focusExpandControl(): void {
    this.expandControl?.nativeElement.focus();
  }

  private positionCurrentPacket(viewport: HTMLElement): void {
    const target =
      viewport.querySelector<HTMLElement>('.packet.active') ??
      viewport.querySelector<HTMLElement>('.packet:last-child');
    if (target === null) return;
    const heading = viewport.querySelector<HTMLElement>('.table-heading');
    viewport.style.removeProperty('--live-follow-space');
    const targetContentTop =
      target.getBoundingClientRect().top -
      viewport.getBoundingClientRect().top +
      viewport.scrollTop;
    const top = Math.max(0, targetContentTop - (heading?.getBoundingClientRect().height ?? 0) - 8);
    const missingScrollRange = top - (viewport.scrollHeight - viewport.clientHeight);
    if (missingScrollRange > 0) {
      viewport.style.setProperty('--live-follow-space', `${Math.ceil(missingScrollRange)}px`);
    }
    this.programmaticScrollTop = top;
    viewport.scrollTop = top;
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
