import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  OnInit,
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
import { TranslationService } from '../core/i18n/translation.service';
import { TranslationKey } from '../core/i18n/translations/ru';
import { ActionBarComponent } from './components/action-bar/action-bar';
import { GameTableComponent } from './components/game-table/game-table';
import { HandComponent } from './components/hand/hand';
import { TrumpIndicatorComponent } from './components/trump-indicator/trump-indicator';
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
  ],
  templateUrl: './game-page.html',
  styleUrl: './game-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GamePageComponent implements OnInit, OnDestroy {
  private readonly api = inject(GameApiService);
  private readonly session = inject(GameSessionState);
  protected readonly auth = inject(AuthService);
  protected readonly i18n = inject(TranslationService);

  protected readonly game = this.session.game;
  protected readonly pending = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly restartConfirmation = signal(false);
  protected readonly botPresentation = signal<BotPresentationEvent | null>(null);
  protected readonly selectedCodes = signal<ReadonlySet<string>>(new Set());
  protected readonly selectedCards = computed<readonly GameCard[]>(() => {
    const selected = this.selectedCodes();
    return this.game()?.human_hand.filter((card) => selected.has(card.code)) ?? [];
  });
  protected readonly statusText = computed(() => this.getStatusText());
  private presentationTimer: ReturnType<typeof setTimeout> | null = null;
  private pendingAuthoritativeGame: GameResponse | null = null;

  ngOnInit(): void {
    if (this.game() === null) {
      this.startNewGame();
    }
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
    }
  }

  protected cancelNewGame(): void {
    this.restartConfirmation.set(false);
  }

  protected startNewGame(): void {
    if (this.pending()) {
      return;
    }
    this.cancelPresentation();
    this.restartConfirmation.set(false);
    this.pending.set(true);
    this.errorMessage.set(null);
    this.api
      .createGame()
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (game) => {
          this.game.set(game);
          this.selectedCodes.set(new Set());
          this.showBriefBotStatus(game.recent_events.at(-1) ?? null);
        },
        error: (error: unknown) => this.errorMessage.set(this.messageForError(error)),
      });
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

  protected activityTurn(game: GameResponse, actor: 'HUMAN' | 'BOT'): readonly string[] {
    if (this.pending() || game.phase === 'complete' || game.required_actor !== actor) return [];
    return [
      [
        game.game_id,
        actor,
        game.bout_phase ?? 'ready',
        game.packets.length,
        game.table_cards.length,
        game.available_actions.join('-'),
      ].join(':'),
    ];
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
