import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { CARD_ACTIONS, GameCard, HumanActionType } from '../core/api/game-api.models';
import { PvPCredentialStore } from '../core/pvp/pvp-credential.store';
import { PvPWebSocketService } from '../core/pvp/pvp-websocket.service';
import { HintPreferenceService } from '../core/hints/hint-preference.service';
import { ActionBarComponent } from '../game/components/action-bar/action-bar';
import { CardMotionOverlayComponent } from '../game/components/card-motion-overlay/card-motion-overlay';
import { GameTableComponent } from '../game/components/game-table/game-table';
import { HandComponent } from '../game/components/hand/hand';
import { HintPanelComponent } from '../game/components/hint-panel/hint-panel';
import { TableSeatMapComponent } from '../game/components/table-seat-map/table-seat-map';
import { TrumpIndicatorComponent } from '../game/components/trump-indicator/trump-indicator';
import { TurnReminderComponent } from '../game/components/turn-reminder/turn-reminder';
import { TranslationService } from '../core/i18n/translation.service';
import { TranslationKey } from '../core/i18n/translations/ru';
import {
  CardMotionController,
  MotionSnapshot,
  planCardMotions,
} from '../game/presentation/card-motion';
import { HiddenTableSeat } from '../game/presentation/table-seat.models';
import { PvPState } from '../core/pvp/pvp.models';

const ERROR_KEYS: Readonly<Record<string, TranslationKey>> = {
  WRONG_TURN: 'error.wrong_turn',
  STALE_VERSION: 'pvp.stale',
  RATE_LIMITED: 'pvp.rateLimited',
  GAME_COMPLETE: 'pvp.gameCompleteError',
  REMATCH_NOT_AVAILABLE: 'pvp.rematchUnavailable',
  INVALID_CREDENTIAL: 'pvp.invalidCredential',
  illegal_initial_attack: 'error.illegal_initial_attack',
  illegal_defense: 'error.illegal_defense',
  redundant_defense: 'error.redundant_defense',
  illegal_transfer: 'error.illegal_transfer',
  illegal_throw_in: 'error.illegal_throw_in',
  attack_card_limit_exceeded: 'error.attack_card_limit_exceeded',
};

@Component({
  selector: 'app-pvp-room-page',
  imports: [
    ActionBarComponent,
    CardMotionOverlayComponent,
    GameTableComponent,
    HandComponent,
    HintPanelComponent,
    RouterLink,
    TableSeatMapComponent,
    TrumpIndicatorComponent,
    TurnReminderComponent,
  ],
  templateUrl: './pvp-room-page.html',
  styleUrls: ['../game/game-page.css', './pvp-room-page.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [CardMotionController],
})
export class PvPRoomPageComponent implements OnInit, OnDestroy {
  @ViewChild('leaveTrigger') private leaveTrigger?: ElementRef<HTMLButtonElement>;
  @ViewChild('leaveCancel') private leaveCancel?: ElementRef<HTMLButtonElement>;
  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly credentials = inject(PvPCredentialStore);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  protected readonly socket = inject(PvPWebSocketService);
  protected readonly hintPreference = inject(HintPreferenceService);
  protected readonly i18n = inject(TranslationService);
  protected readonly cardMotion = inject(CardMotionController);
  protected readonly selectedCodes = signal<ReadonlySet<string>>(new Set());
  protected readonly copyStatus = signal<'idle' | 'copied' | 'failed'>('idle');
  protected readonly leaveConfirmation = signal(false);
  protected readonly startingRematch = signal(false);
  protected readonly state = this.socket.state;
  protected readonly selectedCards = computed<readonly GameCard[]>(() => {
    const selected = this.selectedCodes();
    return this.state()?.hand.filter((card) => selected.has(card.code)) ?? [];
  });
  protected readonly suggestedCodes = computed<ReadonlySet<string>>(
    () => new Set(this.socket.hints()?.suggested_card_ids ?? []),
  );
  protected readonly inviteUrl = computed(
    () => `${window.location.origin}/join/${this.inviteCode}`,
  );
  protected readonly statusText = computed(() => this.getStatusText());
  protected readonly gameplayPaused = computed(() => {
    const state = this.state();
    return (
      state?.room_phase === 'CLOSED' ||
      this.startingRematch() ||
      this.socket.roomClosure() !== null ||
      this.socket.status() !== 'connected' ||
      this.socket.opponentStatus() === 'disconnected' ||
      state?.opponent?.connected === false
    );
  });
  protected readonly opponentSeats = computed<readonly HiddenTableSeat[]>(() => {
    const state = this.state();
    if (state?.opponent === null || state?.opponent === undefined) return [];
    return [
      {
        id: state.opponent.participant_id,
        position: 'top',
        displayName: state.opponent.display_name,
        cardCount: state.opponent_hand_count ?? 0,
        badge: 'P2',
      },
    ];
  });
  protected inviteCode = '';
  private lastVersion = -1;
  private previousState: PvPState | null = null;
  private submittedAction: HumanActionType | null = null;
  private submittedCards: readonly GameCard[] = [];
  private rematchTransitionTimer: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    effect(() => {
      const current = this.state();
      if (current !== null) {
        if (current.version > this.lastVersion && this.lastVersion >= 0) {
          const startsRematch =
            this.previousState?.game_phase === 'complete' &&
            current.room_phase === 'GAME_ACTIVE' &&
            current.match_id !== this.previousState.match_id;
          if (startsRematch) this.presentRematchStart();
          else if (this.previousState !== null) this.presentTransition(this.previousState, current);
          this.selectedCodes.set(new Set());
        } else {
          const ownedCodes = new Set(current.hand.map((card) => card.code));
          this.selectedCodes.update(
            (selected) => new Set([...selected].filter((code) => ownedCodes.has(code))),
          );
        }
        this.lastVersion = Math.max(this.lastVersion, current.version);
        this.previousState = current;
      }
    });
    effect(() => {
      const errorCode = this.socket.actionError()?.code;
      if (errorCode !== undefined) {
        this.submittedAction = null;
        this.submittedCards = [];
      }
      if (this.inviteCode !== '' && errorCode === 'INVALID_CREDENTIAL') {
        this.credentials.clear(this.inviteCode);
        this.socket.disconnect();
        void this.router.navigate(['/join', this.inviteCode]);
      }
    });
    effect(() => {
      if (this.inviteCode !== '' && this.socket.status() === 'expired') {
        this.credentials.clear(this.inviteCode);
      }
    });
    effect(() => {
      const closure = this.socket.roomClosure();
      if (closure === null || this.inviteCode === '') return;
      this.credentials.clear(this.inviteCode);
      if (closure === 'you_left') void this.router.navigate(['/pvp']);
    });
  }

  ngOnInit(): void {
    this.inviteCode = this.route.snapshot.paramMap.get('inviteCode') ?? '';
    const credential = this.credentials.get(this.inviteCode);
    if (credential === null) {
      void this.router.navigate(['/join', this.inviteCode]);
      return;
    }
    this.socket.connect(this.inviteCode, credential.reconnect_token);
  }

  ngOnDestroy(): void {
    if (this.rematchTransitionTimer !== null) clearTimeout(this.rematchTransitionTimer);
    this.cardMotion.clear();
    this.socket.disconnect();
  }

  protected toggleCard(code: string): void {
    if (this.socket.actionPending() || this.gameplayPaused()) return;
    this.selectedCodes.update((current) => {
      const next = new Set(current);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
    this.socket.actionError.set(null);
    this.refreshHints();
  }

  protected setHintsEnabled(enabled: boolean): void {
    this.hintPreference.setEnabled(enabled);
    if (enabled) this.refreshHints();
    else this.socket.clearHints();
  }

  protected submitAction(action: HumanActionType): void {
    const state = this.state();
    if (state === null || this.gameplayPaused() || !state.available_actions.includes(action))
      return;
    const cards =
      action === 'INITIAL_ATTACK' ||
      action === 'DEFEND' ||
      action === 'TRANSFER' ||
      action === 'THROW_IN'
        ? this.selectedCards().map((card) => card.code)
        : [];
    this.submittedAction = action;
    this.submittedCards = CARD_ACTIONS.has(action) ? this.selectedCards() : [];
    this.socket.sendAction(action, cards);
  }

  private refreshHints(): void {
    if (!this.hintPreference.enabled() || this.gameplayPaused()) {
      this.socket.clearHints();
      return;
    }
    this.socket.requestHints(this.selectedCards().map((card) => card.code));
  }

  protected async copyInvite(): Promise<void> {
    try {
      if (navigator.clipboard === undefined) throw new Error('clipboard unavailable');
      await navigator.clipboard.writeText(this.inviteUrl());
      this.copyStatus.set('copied');
    } catch {
      this.copyStatus.set('failed');
    }
  }

  protected async shareInvite(): Promise<void> {
    if (navigator.share === undefined) return;
    try {
      await navigator.share({ title: this.i18n.t('pvp.shareTitle'), url: this.inviteUrl() });
    } catch {
      // Dismissed or unavailable native sharing leaves the copy fallback usable.
    }
  }

  protected canShare(): boolean {
    return navigator.share !== undefined;
  }

  protected requestLeave(): void {
    if (this.socket.leavePending()) return;
    this.leaveConfirmation.set(true);
    this.changeDetector.detectChanges();
    this.leaveCancel?.nativeElement.focus();
  }

  protected cancelLeave(): void {
    this.leaveConfirmation.set(false);
    this.changeDetector.detectChanges();
    this.leaveTrigger?.nativeElement.focus();
  }

  protected handleLeaveKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.cancelLeave();
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

  protected localDecisionContext(): string | null {
    const state = this.state();
    if (
      state === null ||
      state.game_phase === 'complete' ||
      state.required_participant_id !== state.you.participant_id ||
      this.socket.actionPending() ||
      this.gameplayPaused() ||
      this.leaveConfirmation()
    ) {
      return null;
    }
    return `${state.you.participant_id}:${state.version}`;
  }

  protected lastBoutText(): string | null {
    const state = this.state();
    const summary = state?.last_bout_summary;
    if (state === null || summary === null || summary === undefined) return null;
    const localActor = summary.actor_seat === state.you.seat;
    if (summary.outcome === 'TAKE') {
      if (localActor) {
        return this.i18n.t('game.youTook', {
          count: summary.table_card_count,
          cards: this.i18n.cardCount(summary.table_card_count),
        });
      }
      return this.i18n.t('game.opponentTook', {
        name: state.opponent?.display_name ?? this.i18n.t('pvp.opponent'),
        count: summary.table_card_count,
        cards: this.i18n.cardCount(summary.table_card_count),
      });
    }
    return localActor
      ? this.i18n.t('game.youDefended')
      : this.i18n.t('game.opponentDefended', {
          name: state.opponent?.display_name ?? this.i18n.t('pvp.opponent'),
        });
  }

  protected connectionMessage(): string | null {
    const status = this.socket.status();
    if (status === 'connecting') return this.i18n.t('pvp.connecting');
    if (status === 'reconnecting') return this.i18n.t('pvp.reconnecting');
    if (status === 'offline') return this.i18n.t('pvp.offline');
    if (status === 'disconnected') return this.i18n.t('pvp.disconnected');
    if (status === 'error') {
      return this.socket.actionError()?.code === 'CONNECTION_REPLACED'
        ? this.i18n.t('pvp.roomOtherTab')
        : this.i18n.t('pvp.connectFailed');
    }
    if (this.socket.opponentStatus() === 'disconnected') {
      return this.i18n.t('pvp.opponentDisconnected');
    }
    if (this.socket.opponentStatus() === 'returned') return this.i18n.t('pvp.opponentReturned');
    return null;
  }

  protected connectionNoticeText(): string | null {
    switch (this.socket.connectionNotice()) {
      case 'connection_restored':
        return this.i18n.t('pvp.restored');
      case 'action_recovered':
        return this.i18n.t('pvp.restoredCurrent');
      case 'state_updated':
        return this.i18n.t('pvp.stateUpdated');
      default:
        return null;
    }
  }

  protected canRetryConnection(): boolean {
    return this.socket.status() === 'disconnected' || this.socket.status() === 'error';
  }

  protected errorText(): string | null {
    const error = this.socket.actionError();
    if (error === null) return null;
    return (
      (ERROR_KEYS[error.domain_code ?? ''] && this.i18n.t(ERROR_KEYS[error.domain_code ?? ''])) ??
      (ERROR_KEYS[error.code] && this.i18n.t(ERROR_KEYS[error.code])) ??
      this.i18n.t('game.moveRejected')
    );
  }

  protected resultTitle(): string {
    const state = this.state();
    if (state?.result?.outcome === 'DRAW') return this.i18n.t('game.draw');
    return state?.result?.winner_participant_id === state?.you.participant_id
      ? this.i18n.t('game.win')
      : this.i18n.t('pvp.winner', {
          name: state?.result?.winner_display_name ?? this.i18n.t('pvp.opponent'),
        });
  }

  protected requestRematch(): void {
    this.socket.requestRematch();
  }

  protected acceptRematch(): void {
    this.socket.acceptRematch();
  }

  protected declineRematch(): void {
    this.socket.declineRematch();
  }

  protected cancelRematch(): void {
    this.socket.cancelRematch();
  }

  protected leave(): void {
    this.leaveConfirmation.set(false);
    this.socket.leaveRoom();
  }

  private presentRematchStart(): void {
    this.cardMotion.clear();
    this.submittedAction = null;
    this.submittedCards = [];
    if (this.rematchTransitionTimer !== null) clearTimeout(this.rematchTransitionTimer);
    this.startingRematch.set(true);
    this.rematchTransitionTimer = setTimeout(() => {
      this.rematchTransitionTimer = null;
      this.startingRematch.set(false);
    }, 650);
  }

  private getStatusText(): string {
    const state = this.state();
    if (this.socket.status() === 'connecting') return this.i18n.t('pvp.connecting');
    if (this.socket.status() === 'reconnecting') return this.i18n.t('pvp.reconnecting');
    if (this.socket.status() === 'offline') return this.i18n.t('pvp.offline');
    if (this.socket.status() === 'disconnected' || this.socket.status() === 'error') {
      return this.i18n.t('pvp.connectionLost');
    }
    if (this.gameplayPaused()) return this.i18n.t('pvp.opponentDisconnected');
    if (state === null) return this.i18n.t('pvp.loadingRoom');
    if (state.room_phase === 'WAITING_FOR_OPPONENT') return this.i18n.t('pvp.waiting');
    if (state.game_phase === 'complete') return this.i18n.t('pvp.complete');
    if (state.required_participant_id !== state.you.participant_id) {
      return this.i18n.t('pvp.opponentThinking', {
        name: state.opponent?.display_name ?? this.i18n.t('pvp.opponent'),
      });
    }
    if (state.available_actions.includes('INITIAL_ATTACK')) return this.i18n.t('pvp.attackPrompt');
    if (state.available_actions.includes('DEFEND'))
      return this.i18n.t('game.defendAgainst', { value: state.active_attack_value ?? 0 });
    if (state.available_actions.includes('THROW_IN')) return this.i18n.t('game.mayThrow');
    return this.i18n.t('game.yourTurn');
  }

  private presentTransition(previous: PvPState, next: PvPState): void {
    const previousCodes = new Set(previous.table_cards.map((card) => card.code));
    const submitted = new Set(this.submittedCards.map((card) => card.code));
    const remoteCards = next.table_cards.filter(
      (card) => !previousCodes.has(card.code) && !submitted.has(card.code),
    );
    this.cardMotion.play(
      planCardMotions(this.motionSnapshot(previous), this.motionSnapshot(next), {
        localAction: this.submittedAction ?? undefined,
        localCards: this.submittedCards,
        remoteCardCount: remoteCards.length,
        remotePlayedCards: remoteCards,
        resolvedTo: this.resolutionDestination(previous, next),
        refillOrder:
          previous.bout_starting_attacker === previous.you.seat ? 'local-first' : 'opponent-first',
      }),
    );
    this.submittedAction = null;
    this.submittedCards = [];
  }

  private motionSnapshot(state: PvPState): MotionSnapshot {
    return {
      localHand: state.hand,
      opponentHandCount: state.opponent_hand_count ?? 0,
      drawPileCount: state.draw_pile_count,
      discardCount: state.discard_count,
      tableCards: state.table_cards,
    };
  }

  private resolutionDestination(
    previous: PvPState,
    state: PvPState,
  ): 'local' | 'opponent' | 'discard' | undefined {
    const summary = state.last_bout_summary;
    if (summary === null) return undefined;
    const nextTableCodes = new Set(state.table_cards.map((card) => card.code));
    if (
      previous.table_cards.length === 0 ||
      previous.table_cards.every((card) => nextTableCodes.has(card.code))
    )
      return undefined;
    if (summary.outcome === 'BITO') return 'discard';
    return summary.actor_seat === state.you.seat ? 'local' : 'opponent';
  }
}
