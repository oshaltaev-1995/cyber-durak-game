import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  ViewChild,
  inject,
  input,
  signal,
} from '@angular/core';
import { AttackPacket, GameCard, TableArithmetic } from '../../../core/api/game-api.models';
import { TranslationService } from '../../../core/i18n/translation.service';
import { formatCardShort } from '../../card-presentation';
import { GameTableComponent } from '../game-table/game-table';

export interface TableInspectionParticipant {
  readonly id: string;
  readonly name: string;
  readonly cardCount: number;
  readonly isBot: boolean;
  readonly isLocal: boolean;
  readonly roles: readonly string[];
}

@Component({
  selector: 'app-table-inspection',
  imports: [GameTableComponent],
  templateUrl: './table-inspection.html',
  styleUrl: './table-inspection.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TableInspectionComponent {
  @ViewChild('dialog') private dialog?: ElementRef<HTMLDialogElement>;
  @ViewChild('closeButton') private closeButton?: ElementRef<HTMLButtonElement>;
  @ViewChild('normalTable') private normalTable?: GameTableComponent;
  protected readonly i18n = inject(TranslationService);
  protected readonly opened = signal(false);

  readonly packets = input.required<readonly AttackPacket[]>();
  readonly arithmetic = input.required<TableArithmetic>();
  readonly activeAttackValue = input.required<number | null>();
  readonly directAnchors = input.required<readonly GameCard[]>();
  readonly final = input(false);
  readonly finalOutcome = input<'TAKE' | 'BITO' | null>(null);
  readonly observer = input(false);
  readonly followContextKey = input<string | null>(null);
  readonly participants = input.required<readonly TableInspectionParticipant[]>();
  readonly drawPileCount = input.required<number>();
  readonly discardCount = input.required<number>();
  readonly exposedTopCard = input<GameCard | null>(null);
  readonly actorCue = input<string | null>(null);
  readonly humanTurn = input(false);

  protected open(): void {
    const dialog = this.dialog?.nativeElement;
    if (dialog === undefined || this.opened()) return;
    this.opened.set(true);
    try {
      if (typeof dialog.showModal === 'function') dialog.showModal();
      else dialog.setAttribute('open', '');
    } catch {
      dialog.setAttribute('open', '');
    }
    setTimeout(() => this.closeButton?.nativeElement.focus());
  }

  protected close(): void {
    const dialog = this.dialog?.nativeElement;
    if (dialog === undefined || !this.opened()) return;
    this.opened.set(false);
    if (typeof dialog.close === 'function' && dialog.open) dialog.close();
    else {
      dialog.removeAttribute('open');
      this.restoreFocus();
    }
  }

  protected handleCancel(event: Event): void {
    event.preventDefault();
    this.close();
  }

  protected handleClosed(): void {
    this.opened.set(false);
    this.restoreFocus();
  }

  protected handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.close();
      return;
    }
    if (event.key !== 'Tab') return;
    const dialog = event.currentTarget as HTMLElement;
    const focusable = [...dialog.querySelectorAll<HTMLElement>('button:not([disabled])')];
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable.at(-1) as HTMLElement;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  protected exposedLabel(): string {
    const card = this.exposedTopCard();
    if (card === null) return this.i18n.t('game.deckEmpty');
    return formatCardShort(card, (color) =>
      this.i18n.t(color === 'red' ? 'deck.redJoker' : 'deck.blackJoker'),
    );
  }

  private restoreFocus(): void {
    queueMicrotask(() => this.normalTable?.focusExpandControl());
  }
}
