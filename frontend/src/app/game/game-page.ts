import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
  computed,
  inject,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import {
  BotPresentationEvent,
  GameCard,
  GameResponse,
  HumanActionType,
} from '../core/api/game-api.models';
import { GameApiService } from '../core/api/game-api.service';
import { AuthService } from '../core/auth/auth.service';
import { BotGameSessionStore } from '../core/game/bot-game-session.store';
import { TranslationService } from '../core/i18n/translation.service';
import { TranslationKey } from '../core/i18n/translations/ru';
import { ActionBarComponent } from './components/action-bar/action-bar';
import { GameTableComponent } from './components/game-table/game-table';
import { HandComponent } from './components/hand/hand';
import { TrumpIndicatorComponent } from './components/trump-indicator/trump-indicator';
import { TurnReminderComponent } from './components/turn-reminder/turn-reminder';
import { GameSessionState } from './game-session-state';

const ERROR_KEYS: Readonly<Record<string, TranslationKey>> = {
  illegal_initial_attack: 'error.illegal_initial_attack',
  illegal_defense: 'error.illegal_defense',
  illegal_transfer: 'error.illegal_transfer',
  illegal_throw_in: 'error.illegal_throw_in',
  attack_card_limit_exceeded: 'error.attack_card_limit_exceeded',
  card_not_owned: 'error.card_not_owned',
  not_human_turn: 'error.wrong_turn',
  game_complete: 'game.matchComplete',
};

@Component({
  selector: 'app-game-page',
  imports: [
    ActionBarComponent,
    GameTableComponent,
    HandComponent,
    RouterLink,
    TrumpIndicatorComponent,
    TurnReminderComponent,
  ],
  templateUrl: './game-page.html',
  styleUrl: './game-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GamePageComponent implements OnInit, OnDestroy {
  @ViewChild('newGameTrigger') private newGameTrigger?: ElementRef<HTMLButtonElement>;
  @ViewChild('restartCancel') private restartCancel?: ElementRef<HTMLButtonElement>;
  private readonly api = inject(GameApiService);
  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly session = inject(GameSessionState);
  private readonly storedSession = inject(BotGameSessionStore);
  protected readonly auth = inject(AuthService);
  protected readonly i18n = inject(TranslationService);

  protected readonly game = this.session.game;
  protected readonly pending = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly restartConfirmation = signal(false);
  protected readonly botPresentation = signal<BotPresentationEvent | null>(null);
  protected readonly selectedCodes = signal<ReadonlySet<string>>(new Set());
  protected readonly recoveryState = signal<'idle' | 'loading' | 'unavailable' | 'failed'>('idle');
  protected readonly selectedCards = computed<readonly GameCard[]>(() => {
    const selected = this.selectedCodes();
    return this.game()?.human_hand.filter((card) => selected.has(card.code)) ?? [];
  });
  protected readonly statusText = computed(() => this.getStatusText());
  private presentationTimer: ReturnType<typeof setTimeout> | null = null;
  private pendingAuthoritativeGame: GameResponse | null = null;

  ngOnInit(): void {
    const currentGame = this.game();
    if (currentGame !== null) {
      this.storedSession.save(currentGame.game_id);
      return;
    }
    const gameId = this.storedSession.get();
    if (gameId !== null) {
      this.restoreGame(gameId);
      return;
    }
    this.startNewGame();
  }

  ngOnDestroy(): void {
    if (this.pendingAuthoritativeGame !== null) {
      this.game.set(this.pendingAuthoritativeGame);
      this.selectedCodes.set(new Set());
      this.pendingAuthoritativeGame = null;
    }
    this.cancelPresentation();
  }

  protected requestNewGame(): void {
    if (!this.pending()) {
      this.restartConfirmation.set(true);
      this.changeDetector.detectChanges();
      this.restartCancel?.nativeElement.focus();
    }
  }

  protected cancelNewGame(): void {
    this.restartConfirmation.set(false);
    this.changeDetector.detectChanges();
    this.newGameTrigger?.nativeElement.focus();
  }

  protected handleRestartKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.cancelNewGame();
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

  protected startNewGame(): void {
    if (this.pending()) {
      return;
    }
    this.cancelPresentation();
    this.restartConfirmation.set(false);
    this.recoveryState.set('idle');
    this.pending.set(true);
    this.errorMessage.set(null);
    this.api
      .createGame()
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (game) => {
          this.storedSession.save(game.game_id);
          this.game.set(game);
          this.selectedCodes.set(new Set());
          this.showBriefBotStatus(game.recent_events.at(-1) ?? null);
        },
        error: (error: unknown) => this.errorMessage.set(this.messageForError(error)),
      });
  }

  protected retryInitialLoad(): void {
    if (this.pending()) return;
    if (this.recoveryState() === 'failed') {
      const gameId = this.storedSession.get();
      if (gameId !== null) {
        this.restoreGame(gameId);
        return;
      }
    }
    this.startNewGame();
  }

  protected welcomeTitle(): string {
    if (this.pending()) {
      return this.i18n.t(this.recoveryState() === 'loading' ? 'game.restoring' : 'game.dealing');
    }
    if (this.recoveryState() === 'unavailable') {
      return this.i18n.t('game.previousUnavailableTitle');
    }
    if (this.recoveryState() === 'failed') {
      return this.i18n.t('game.restoreFailed');
    }
    return this.i18n.t('game.startFailed');
  }

  protected welcomeDescription(): string {
    if (this.pending()) {
      return this.i18n.t(
        this.recoveryState() === 'loading' ? 'game.restorePreparing' : 'game.preparingDeck',
      );
    }
    if (this.recoveryState() === 'unavailable') {
      return this.i18n.t('game.previousUnavailable');
    }
    if (this.recoveryState() === 'failed') {
      return this.i18n.t('game.restoreRetry');
    }
    return this.i18n.t('game.tryAgain');
  }

  protected welcomeActionLabel(): string {
    return this.i18n.t(this.recoveryState() === 'unavailable' ? 'game.start' : 'common.retry');
  }

  protected toggleCard(code: string): void {
    if (this.pending()) {
      return;
    }
    this.selectedCodes.update((current) => {
      const updated = new Set(current);
      if (updated.has(code)) {
        updated.delete(code);
      } else {
        updated.add(code);
      }
      return updated;
    });
    this.errorMessage.set(null);
  }

  protected submitAction(action: HumanActionType): void {
    const game = this.game();
    if (game === null || this.pending() || !game.available_actions.includes(action)) {
      return;
    }
    this.pending.set(true);
    this.errorMessage.set(null);
    this.api
      .submitAction(
        game.game_id,
        action,
        this.selectedCards().map((card) => card.code),
      )
      .subscribe({
        next: (updatedGame) => this.presentUpdatedGame(updatedGame),
        error: (error: unknown) => {
          this.pending.set(false);
          this.errorMessage.set(this.messageForError(error));
        },
      });
  }

  protected localDecisionContext(game: GameResponse): string | null {
    if (this.pending() || game.phase === 'complete' || game.required_actor !== 'HUMAN') return null;
    return [
      game.game_id,
      game.bout_phase ?? 'ready',
      game.packets.length,
      game.table_cards.length,
      game.active_packet?.attack_cards.map((card) => card.code).join(',') ?? 'none',
      game.active_packet?.defense_cards.map((card) => card.code).join(',') ?? 'none',
      game.available_actions.join('-'),
    ].join(':');
  }

  protected lastBoutText(game: GameResponse): string | null {
    const summary = game.last_bout_summary;
    if (summary === null) return null;
    const localActor = summary.actor_seat === game.human_seat;
    if (summary.outcome === 'TAKE') {
      return this.i18n.t(localActor ? 'game.youTook' : 'game.botTook', {
        count: summary.table_card_count,
        cards: this.i18n.cardCount(summary.table_card_count),
      });
    }
    return this.i18n.t(localActor ? 'game.youDefended' : 'game.botDefended');
  }

  protected resultTitle(game: GameResponse): string {
    if (game.result?.outcome === 'DRAW') {
      return this.i18n.t('game.draw');
    }
    return game.result?.winner === 'HUMAN' ? this.i18n.t('game.win') : this.i18n.t('game.botWin');
  }

  private getStatusText(): string {
    const event = this.botPresentation();
    if (event !== null) {
      return this.botEventText(event);
    }
    if (this.pending()) {
      return this.i18n.t('game.botThinking');
    }
    const game = this.game();
    if (game === null) {
      return this.i18n.t('game.newMatchWaiting');
    }
    if (game.phase === 'complete') {
      return this.i18n.t('game.matchComplete');
    }
    if (game.available_actions.includes('INITIAL_ATTACK')) {
      return this.i18n.t('game.attackPrompt');
    }
    if (game.available_actions.includes('DEFEND')) {
      return game.active_attack_value === null
        ? this.i18n.t('game.respondPrompt')
        : this.i18n.t('game.defendAgainst', { value: game.active_attack_value });
    }
    if (game.available_actions.includes('THROW_IN')) {
      return this.i18n.t('game.mayThrow');
    }
    return game.required_actor === 'BOT'
      ? this.i18n.t('game.botMoves')
      : this.i18n.t('game.yourTurn');
  }

  private presentUpdatedGame(updatedGame: GameResponse): void {
    const event = updatedGame.recent_events.at(-1) ?? null;
    if (event?.type === 'BOT_TAKE' && this.game() !== null) {
      this.pendingAuthoritativeGame = updatedGame;
      this.botPresentation.set(event);
      this.presentationTimer = setTimeout(() => {
        this.presentationTimer = null;
        this.pendingAuthoritativeGame = null;
        this.game.set(updatedGame);
        this.selectedCodes.set(new Set());
        this.botPresentation.set(null);
        this.pending.set(false);
      }, 650);
      return;
    }
    this.game.set(updatedGame);
    this.selectedCodes.set(new Set());
    this.pending.set(false);
    this.showBriefBotStatus(event);
  }

  private restoreGame(gameId: string): void {
    if (this.pending()) return;
    this.recoveryState.set('loading');
    this.pending.set(true);
    this.errorMessage.set(null);
    this.api
      .getGame(gameId)
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (game) => {
          this.storedSession.save(game.game_id);
          this.game.set(game);
          this.selectedCodes.set(new Set());
          this.recoveryState.set('idle');
        },
        error: (error: unknown) => {
          if (this.isMissingGame(error)) {
            this.storedSession.clear();
            this.recoveryState.set('unavailable');
            return;
          }
          this.recoveryState.set('failed');
        },
      });
  }

  private isMissingGame(error: unknown): boolean {
    if (!(error instanceof HttpErrorResponse) || error.status !== 404) return false;
    const body = error.error as { detail?: { code?: string } } | null;
    return body?.detail?.code === 'game_not_found';
  }

  private showBriefBotStatus(event: BotPresentationEvent | null): void {
    if (event === null) return;
    this.cancelPresentation();
    this.botPresentation.set(event);
    this.presentationTimer = setTimeout(() => {
      this.presentationTimer = null;
      this.botPresentation.set(null);
    }, 700);
  }

  private cancelPresentation(): void {
    if (this.presentationTimer !== null) {
      clearTimeout(this.presentationTimer);
      this.presentationTimer = null;
    }
    this.botPresentation.set(null);
  }

  private botEventText(event: BotPresentationEvent): string {
    switch (event.type) {
      case 'BOT_INITIAL_ATTACK':
        return this.i18n.t('game.botMoves');
      case 'BOT_DEFEND':
        return this.i18n.t('game.botDefends');
      case 'BOT_TRANSFER':
        return this.i18n.t('game.botTransfers');
      case 'BOT_THROW_IN':
        return this.i18n.t('game.botThrows');
      case 'BOT_TAKE':
        return event.card_count > 0
          ? this.i18n.t('game.botTakes', {
              count: event.card_count,
              cards: this.i18n.cardCount(event.card_count),
            })
          : this.i18n.t('game.botTakesCards');
      case 'BOT_BITO':
        return this.i18n.t('game.endBout');
    }
  }

  private messageForError(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const body = error.error as { detail?: { code?: string } } | null;
      const code = body?.detail?.code;
      if (code !== undefined && ERROR_KEYS[code] !== undefined) {
        return this.i18n.t(ERROR_KEYS[code]);
      }
      if (error.status === 0) {
        return this.i18n.t('game.serverUnavailable');
      }
    }
    return this.i18n.t('game.moveRejected');
  }
}
