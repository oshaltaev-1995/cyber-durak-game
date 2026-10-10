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
import { Subscription, finalize } from 'rxjs';
import {
  BotPresentationEvent,
  CARD_ACTIONS,
  DeckCount,
  DeckProfile,
  GameCard,
  GameResponse,
  HintResponse,
  HumanActionType,
} from '../core/api/game-api.models';
import { GameApiService } from '../core/api/game-api.service';
import { AuthService } from '../core/auth/auth.service';
import { BotGameSessionStore } from '../core/game/bot-game-session.store';
import { HintPreferenceService } from '../core/hints/hint-preference.service';
import { TranslationService } from '../core/i18n/translation.service';
import { TranslationKey } from '../core/i18n/translations/ru';
import { MultiplayerOnboardingStore } from '../core/onboarding/multiplayer-onboarding.store';
import { DeckVariantsOnboardingStore } from '../core/onboarding/deck-variants-onboarding.store';
import { DeckConfigSelectorComponent } from '../core/deck/deck-config-selector';
import { cardIdentity, isDefaultDeckConfig } from '../core/deck/deck-config';
import { deriveMultiplayerPlacements } from '../pvp/multiplayer-placement';
import { ActionBarComponent } from './components/action-bar/action-bar';
import { CardMotionOverlayComponent } from './components/card-motion-overlay/card-motion-overlay';
import { GameTableComponent } from './components/game-table/game-table';
import { HandComponent } from './components/hand/hand';
import { HintPanelComponent } from './components/hint-panel/hint-panel';
import { TableSeatMapComponent } from './components/table-seat-map/table-seat-map';
import { TrumpIndicatorComponent } from './components/trump-indicator/trump-indicator';
import { TurnReminderComponent } from './components/turn-reminder/turn-reminder';
import { GameSessionState } from './game-session-state';
import { CardMotionController, MotionSnapshot, planCardMotions } from './presentation/card-motion';
import {
  HiddenTableSeat,
  RemoteTableSeatPosition,
  TableSeatPosition,
  relativeSeatPosition,
} from './presentation/table-seat.models';

const ERROR_KEYS: Readonly<Record<string, TranslationKey>> = {
  illegal_initial_attack: 'error.illegal_initial_attack',
  illegal_defense: 'error.illegal_defense',
  redundant_defense: 'error.redundant_defense',
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
    CardMotionOverlayComponent,
    DeckConfigSelectorComponent,
    GameTableComponent,
    HandComponent,
    HintPanelComponent,
    RouterLink,
    TableSeatMapComponent,
    TrumpIndicatorComponent,
    TurnReminderComponent,
  ],
  templateUrl: './game-page.html',
  styleUrls: ['./game-page.css', './game-page.multiplayer.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [CardMotionController],
})
export class GamePageComponent implements OnInit, OnDestroy {
  @ViewChild('newGameTrigger') private newGameTrigger?: ElementRef<HTMLButtonElement>;
  @ViewChild('restartCancel') private restartCancel?: ElementRef<HTMLButtonElement>;
  private readonly api = inject(GameApiService);
  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly session = inject(GameSessionState);
  private readonly storedSession = inject(BotGameSessionStore);
  protected readonly hintPreference = inject(HintPreferenceService);
  protected readonly cardMotion = inject(CardMotionController);
  protected readonly auth = inject(AuthService);
  protected readonly i18n = inject(TranslationService);
  private readonly multiplayerOnboarding = inject(MultiplayerOnboardingStore);
  private readonly deckOnboarding = inject(DeckVariantsOnboardingStore);

  protected readonly game = this.session.game;
  protected readonly pending = signal(false);
  private readonly errorKey = signal<TranslationKey | null>(null);
  protected readonly errorMessage = computed(() => {
    const key = this.errorKey();
    return key === null ? null : this.i18n.t(key);
  });
  protected readonly restartConfirmation = signal(false);
  protected readonly botPresentation = signal<BotPresentationEvent | null>(null);
  protected readonly multiplayerEnabled = signal(false);
  protected readonly deckVariantsEnabled = signal(false);
  protected readonly showSetup = signal(false);
  protected readonly selectedPlayers = signal<2 | 3 | 4>(2);
  protected readonly selectedDeckProfile = signal<DeckProfile>('classic');
  protected readonly selectedDeckCount = signal<DeckCount>(1);
  protected readonly playerCounts = [2, 3, 4] as const;
  protected readonly onboardingVisible = signal(false);
  protected readonly deckOnboardingVisible = signal(false);
  protected readonly selectedIds = signal<ReadonlySet<string>>(new Set());
  protected readonly hints = signal<HintResponse | null>(null);
  protected readonly hintsLoading = signal(false);
  protected readonly suggestedIds = computed<ReadonlySet<string>>(
    () => new Set(this.hints()?.suggested_physical_ids ?? this.hints()?.suggested_card_ids ?? []),
  );
  protected readonly recoveryState = signal<'idle' | 'loading' | 'unavailable' | 'failed'>('idle');
  protected readonly selectedCards = computed<readonly GameCard[]>(() => {
    const selected = this.selectedIds();
    return this.game()?.human_hand.filter((card) => selected.has(cardIdentity(card))) ?? [];
  });
  protected readonly statusText = computed(() => this.getStatusText());
  protected readonly isMultiplayer = computed(() => (this.game()?.total_players ?? 2) > 2);
  protected readonly localParticipant = computed(() =>
    this.game()?.participants.find((participant) => participant.seat === this.game()?.human_seat),
  );
  protected readonly localFinishedWatching = computed(
    () => this.game()?.phase !== 'complete' && this.localParticipant()?.finished === true,
  );
  protected readonly opponentSeats = computed<readonly HiddenTableSeat[]>(() => {
    const game = this.game();
    if (game === null) return [];
    const participants = game.participants.length
      ? game.participants
      : [
          {
            participant_id: 'bot',
            seat: game.bot_seat,
            display_name: this.i18n.t('game.bot'),
            is_bot: true,
            active: true,
            finished: false,
            hand_count: game.bot_hand_count,
          },
        ];
    const seatOrder = participants.map((participant) => participant.seat);
    return participants
      .filter((participant) => participant.seat !== game.human_seat)
      .map((participant) => ({
        id: participant.participant_id,
        seat: participant.seat,
        position: relativeSeatPosition(
          seatOrder,
          game.human_seat,
          participant.seat,
        ) as RemoteTableSeatPosition,
        displayName: participant.display_name,
        cardCount: participant.hand_count,
        badge: participant.is_bot ? '🤖' : '',
        isBot: participant.is_bot,
        active: participant.active,
        finished: participant.finished,
        currentAttacker: game.attacker === participant.seat,
        leadAttacker: game.lead_attacker === participant.seat,
        defender: game.defender === participant.seat,
        required: game.required_seat === participant.seat,
      }));
  });
  protected readonly placements = computed(() => {
    const game = this.game();
    if (game === null) return [];
    return deriveMultiplayerPlacements(game.finish_groups).map((placement) => ({
      ...placement,
      participant: game.participants.find((participant) => participant.seat === placement.seat),
    }));
  });
  private presentationTimer: ReturnType<typeof setTimeout> | null = null;
  private presentationQueue: BotPresentationEvent[] = [];
  private submittedAction: HumanActionType | null = null;
  private submittedCards: readonly GameCard[] = [];
  private hintSubscription: Subscription | null = null;
  private hintRequestGeneration = 0;

  ngOnInit(): void {
    const currentGame = this.game();
    if (currentGame !== null) {
      this.storedSession.save(currentGame.game_id);
      this.loadCapabilities(false);
      return;
    }
    const gameId = this.storedSession.get();
    if (gameId !== null) {
      this.loadCapabilities(false);
      this.restoreGame(gameId);
      return;
    }
    this.loadCapabilities(true);
  }

  ngOnDestroy(): void {
    this.clearHints();
    this.cardMotion.clear();
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

  protected startNewGame(totalPlayers: 2 | 3 | 4 = this.selectedPlayers()): void {
    if (this.pending()) {
      return;
    }
    this.cancelPresentation();
    this.clearHints();
    this.cardMotion.clear();
    this.restartConfirmation.set(false);
    this.showSetup.set(false);
    this.recoveryState.set('idle');
    this.pending.set(true);
    this.errorKey.set(null);
    const request = this.deckVariantsEnabled()
      ? this.api.createGame(totalPlayers, {
          deck_profile: this.selectedDeckProfile(),
          deck_count: this.selectedDeckCount(),
        })
      : this.api.createGame(totalPlayers);
    request.pipe(finalize(() => this.pending.set(false))).subscribe({
      next: (game) => {
        this.storedSession.save(game.game_id);
        this.game.set(game);
        this.selectedPlayers.set(game.total_players);
        this.selectedDeckProfile.set(game.deck_profile);
        this.selectedDeckCount.set(game.deck_count);
        this.selectedIds.set(new Set());
        this.presentInitialBotAction(game);
        this.queueBotStatuses(game.recent_events);
        if (!isDefaultDeckConfig(game) && !this.deckOnboarding.hasSeen()) {
          this.deckOnboardingVisible.set(true);
        } else if (game.total_players > 2 && !this.multiplayerOnboarding.hasSeen()) {
          this.onboardingVisible.set(true);
        }
      },
      error: (error: unknown) => {
        this.showSetup.set(this.multiplayerEnabled() || this.deckVariantsEnabled());
        this.errorKey.set(this.messageKeyForError(error));
      },
    });
  }

  protected selectPlayerCount(count: 2 | 3 | 4): void {
    this.selectedPlayers.set(count);
    this.errorKey.set(null);
  }

  protected selectDeckProfile(profile: DeckProfile): void {
    this.selectedDeckProfile.set(profile);
    this.errorKey.set(null);
  }

  protected selectDeckCount(count: DeckCount): void {
    this.selectedDeckCount.set(count);
    this.errorKey.set(null);
  }

  protected playAgain(): void {
    const game = this.game();
    if (game === null || this.pending()) return;
    this.cancelPresentation();
    this.cardMotion.clear();
    this.pending.set(true);
    this.errorKey.set(null);
    this.api
      .restartGame(game.game_id)
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (restarted) => {
          this.storedSession.save(restarted.game_id);
          this.game.set(restarted);
          this.selectedPlayers.set(restarted.total_players);
          this.selectedDeckProfile.set(restarted.deck_profile);
          this.selectedDeckCount.set(restarted.deck_count);
          this.selectedIds.set(new Set());
          this.presentInitialBotAction(restarted);
          this.queueBotStatuses(restarted.recent_events);
        },
        error: (error: unknown) => this.errorKey.set(this.messageKeyForError(error)),
      });
  }

  protected changePlayers(): void {
    if (this.pending()) return;
    this.cancelPresentation();
    this.clearHints();
    this.cardMotion.clear();
    this.restartConfirmation.set(false);
    this.onboardingVisible.set(false);
    this.deckOnboardingVisible.set(false);
    this.storedSession.clear();
    this.game.set(null);
    if (this.multiplayerEnabled() || this.deckVariantsEnabled()) this.showSetup.set(true);
    else this.startNewGame(2);
  }

  protected confirmNewGame(): void {
    if (this.isMultiplayer()) this.changePlayers();
    else this.startNewGame(this.game()?.total_players ?? 2);
  }

  protected dismissOnboarding(): void {
    this.multiplayerOnboarding.markSeen();
    this.onboardingVisible.set(false);
  }

  protected dismissDeckOnboarding(): void {
    this.deckOnboarding.markSeen();
    this.deckOnboardingVisible.set(false);
  }

  protected placeLabel(rank: number): string {
    const safeRank = Math.min(4, Math.max(1, rank)) as 1 | 2 | 3 | 4;
    return this.i18n.t(`pvp.place${safeRank}`);
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
    if (this.showSetup()) return;
    this.startNewGame(this.selectedPlayers());
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

  protected toggleCard(id: string): void {
    if (this.pending()) {
      return;
    }
    this.selectedIds.update((current) => {
      const updated = new Set(current);
      if (updated.has(id)) {
        updated.delete(id);
      } else {
        updated.add(id);
      }
      return updated;
    });
    this.errorKey.set(null);
    this.refreshHints();
  }

  protected setHintsEnabled(enabled: boolean): void {
    this.hintPreference.setEnabled(enabled);
    if (enabled) this.refreshHints();
    else this.clearHints();
  }

  protected submitAction(action: HumanActionType): void {
    const game = this.game();
    if (game === null || this.pending() || !game.available_actions.includes(action)) {
      return;
    }
    this.submittedAction = action;
    this.clearHints();
    this.submittedCards = CARD_ACTIONS.has(action) ? [...this.selectedCards()] : [];
    this.pending.set(true);
    this.errorKey.set(null);
    this.api.submitAction(game.game_id, action, this.selectedCards().map(cardIdentity)).subscribe({
      next: (updatedGame) => this.presentUpdatedGame(updatedGame),
      error: (error: unknown) => {
        this.submittedAction = null;
        this.submittedCards = [];
        this.pending.set(false);
        this.errorKey.set(this.messageKeyForError(error));
      },
    });
  }

  protected localDecisionContext(game: GameResponse): string | null {
    if (
      this.pending() ||
      this.restartConfirmation() ||
      game.phase === 'complete' ||
      game.required_actor !== 'HUMAN'
    )
      return null;
    return [
      game.game_id,
      game.bout_phase ?? 'ready',
      game.packets.length,
      game.table_cards.length,
      game.active_packet?.attack_cards.map(cardIdentity).join(',') ?? 'none',
      game.active_packet?.defense_cards.map(cardIdentity).join(',') ?? 'none',
      game.available_actions.join('-'),
    ].join(':');
  }

  protected lastBoutText(game: GameResponse): string | null {
    const summary = game.last_bout_summary;
    if (summary === null) return null;
    const localActor = summary.actor_seat === game.human_seat;
    const actorName =
      game.total_players > 2
        ? game.participants.find((participant) => participant.seat === summary.actor_seat)
            ?.display_name
        : undefined;
    if (summary.outcome === 'TAKE') {
      return this.i18n.t(
        localActor || actorName === undefined
          ? localActor
            ? 'game.youTook'
            : 'game.botTook'
          : 'game.opponentTook',
        {
          count: summary.table_card_count,
          cards: this.i18n.takeCardCount(summary.table_card_count),
          name: actorName ?? '',
        },
      );
    }
    return this.i18n.t(
      localActor || actorName === undefined
        ? localActor
          ? 'game.youDefended'
          : 'game.botDefended'
        : 'game.opponentDefended',
      { name: actorName ?? '' },
    );
  }

  protected resultTitle(game: GameResponse): string {
    if (game.total_players > 2) return this.i18n.t('pvp.matchFinished');
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
      return this.i18n.t(this.isMultiplayer() ? 'game.botsThinking' : 'game.botThinking');
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
      return this.i18n.t(game.total_players > 2 ? 'game.mayThrowOrPass' : 'game.mayThrow');
    }
    return game.required_actor === 'BOT'
      ? this.i18n.t('game.botNamedThinking', {
          name: this.participantName(game.required_seat, game),
        })
      : this.i18n.t('game.yourTurn');
  }

  private presentUpdatedGame(updatedGame: GameResponse): void {
    const previous = this.game();
    if (previous !== null) {
      this.cardMotion.play(
        planCardMotions(this.motionSnapshot(previous), this.motionSnapshot(updatedGame), {
          localAction: this.submittedAction ?? undefined,
          localCards: this.submittedCards,
          remoteCardCount: this.remotePlayedCount(updatedGame.recent_events),
          remotePlayedCards: this.newPublicRemoteCards(previous, updatedGame),
          remoteFrom: this.remoteActionSource(updatedGame.recent_events, updatedGame),
          remotePlays: this.remotePlayBatches(
            updatedGame.recent_events,
            this.newPublicRemoteCards(previous, updatedGame),
            updatedGame,
          ),
          resolvedTo: this.resolutionDestination(previous, updatedGame),
        }),
      );
    }
    this.game.set(updatedGame);
    this.selectedIds.set(new Set());
    this.clearHints();
    this.submittedAction = null;
    this.submittedCards = [];
    this.pending.set(false);
    this.queueBotStatuses(updatedGame.recent_events);
  }

  private restoreGame(gameId: string): void {
    if (this.pending()) return;
    this.recoveryState.set('loading');
    this.clearHints();
    this.pending.set(true);
    this.errorKey.set(null);
    this.api
      .getGame(gameId)
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (game) => {
          this.cardMotion.clear();
          this.storedSession.save(game.game_id);
          this.game.set(game);
          this.selectedPlayers.set(game.total_players);
          this.selectedDeckProfile.set(game.deck_profile);
          this.selectedDeckCount.set(game.deck_count);
          this.selectedIds.set(new Set());
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

  private refreshHints(): void {
    this.clearHints();
    const game = this.game();
    const selected = this.selectedCards().map(cardIdentity);
    if (
      !this.hintPreference.enabled() ||
      selected.length === 0 ||
      game === null ||
      game.total_players > 2 ||
      game.phase === 'complete' ||
      game.required_actor !== 'HUMAN' ||
      this.pending() ||
      this.restartConfirmation() ||
      !game.available_actions.some((action) => CARD_ACTIONS.has(action))
    ) {
      return;
    }
    const generation = this.hintRequestGeneration;
    const selectionKey = selected.join(',');
    this.hintsLoading.set(true);
    this.hintSubscription = this.api.getHints(game.game_id, selected).subscribe({
      next: (hints) => {
        if (!this.isCurrentHintRequest(generation, game.game_id, selectionKey)) return;
        this.hints.set(hints);
        this.hintsLoading.set(false);
      },
      error: () => {
        if (generation !== this.hintRequestGeneration) return;
        this.hints.set(null);
        this.hintsLoading.set(false);
      },
    });
  }

  private clearHints(): void {
    this.hintRequestGeneration += 1;
    this.hintSubscription?.unsubscribe();
    this.hintSubscription = null;
    this.hints.set(null);
    this.hintsLoading.set(false);
  }

  private isCurrentHintRequest(generation: number, gameId: string, selectionKey: string): boolean {
    return (
      generation === this.hintRequestGeneration &&
      this.hintPreference.enabled() &&
      this.game()?.game_id === gameId &&
      this.selectedCards().map(cardIdentity).join(',') === selectionKey
    );
  }

  private queueBotStatuses(events: readonly BotPresentationEvent[]): void {
    if (events.length === 0) return;
    this.cancelPresentation();
    this.presentationQueue = [...events].slice(-6);
    this.showNextBotStatus();
  }

  private showNextBotStatus(): void {
    const event = this.presentationQueue.shift() ?? null;
    if (event === null) {
      this.botPresentation.set(null);
      return;
    }
    this.botPresentation.set(event);
    this.presentationTimer = setTimeout(() => {
      this.presentationTimer = null;
      this.showNextBotStatus();
    }, 520);
  }

  private cancelPresentation(): void {
    if (this.presentationTimer !== null) {
      clearTimeout(this.presentationTimer);
      this.presentationTimer = null;
    }
    this.presentationQueue = [];
    this.botPresentation.set(null);
  }

  private motionSnapshot(game: GameResponse): MotionSnapshot {
    return {
      localHand: game.human_hand,
      remoteHands: Object.fromEntries(
        this.opponentSeatsFor(game).map((seat) => [seat.position, seat.cardCount]),
      ),
      drawPileCount: game.draw_pile_count,
      discardCount: game.discard_count,
      tableCards: game.table_cards,
    };
  }

  private presentInitialBotAction(game: GameResponse): void {
    const remoteCardCount = this.remotePlayedCount(game.recent_events);
    if (remoteCardCount === 0) return;
    const current = this.motionSnapshot(game);
    this.cardMotion.play(
      planCardMotions(
        {
          ...current,
          remoteHands: {
            ...current.remoteHands,
            [this.remoteActionSource(game.recent_events, game) ?? 'top']:
              (current.remoteHands[this.remoteActionSource(game.recent_events, game) ?? 'top'] ??
                0) + remoteCardCount,
          },
          tableCards: [],
        },
        current,
        {
          remoteCardCount,
          remotePlayedCards: game.table_cards.slice(0, remoteCardCount),
          remoteFrom: this.remoteActionSource(game.recent_events, game),
          remotePlays: this.remotePlayBatches(
            game.recent_events,
            game.table_cards.slice(0, remoteCardCount),
            game,
          ),
        },
      ),
    );
  }

  private remotePlayedCount(events: readonly BotPresentationEvent[]): number {
    return events
      .filter((event) =>
        ['BOT_INITIAL_ATTACK', 'BOT_DEFEND', 'BOT_TRANSFER', 'BOT_THROW_IN'].includes(event.type),
      )
      .reduce((total, event) => total + event.card_count, 0);
  }

  private newPublicRemoteCards(previous: GameResponse, next: GameResponse): readonly GameCard[] {
    const existing = new Set(previous.table_cards.map(cardIdentity));
    const submitted = new Set(this.submittedCards.map(cardIdentity));
    return next.table_cards.filter(
      (card) => !existing.has(cardIdentity(card)) && !submitted.has(cardIdentity(card)),
    );
  }

  private resolutionDestination(
    previous: GameResponse,
    game: GameResponse,
  ): TableSeatPosition | 'discard' | undefined {
    const summary = game.last_bout_summary;
    if (summary === null) return undefined;
    const nextTableCodes = new Set(game.table_cards.map(cardIdentity));
    if (
      previous.table_cards.length === 0 ||
      previous.table_cards.every((card) => nextTableCodes.has(cardIdentity(card)))
    )
      return undefined;
    if (summary.outcome === 'BITO') return 'discard';
    if (summary.actor_seat === game.human_seat) return 'bottom';
    return this.positionForSeat(summary.actor_seat, game) ?? 'top';
  }

  private botEventText(event: BotPresentationEvent): string {
    const game = this.game();
    const name = this.participantName(event.actor_seat ?? null, game);
    if ((game?.total_players ?? 2) > 2) {
      const key: Record<BotPresentationEvent['type'], TranslationKey> = {
        BOT_INITIAL_ATTACK: 'game.botNamedAttacks',
        BOT_DEFEND: 'game.botNamedDefends',
        BOT_TRANSFER: 'game.botNamedTransfers',
        BOT_THROW_IN: 'game.botNamedThrows',
        BOT_TAKE: 'game.botNamedTakes',
        BOT_BITO: 'game.botNamedPasses',
      };
      return this.i18n.t(key[event.type], {
        name,
        count: event.card_count,
        cards:
          event.type === 'BOT_TAKE'
            ? this.i18n.takeCardCount(event.card_count)
            : this.i18n.cardCount(event.card_count),
      });
    }
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
              cards: this.i18n.takeCardCount(event.card_count),
            })
          : this.i18n.t('game.botTakesCards');
      case 'BOT_BITO':
        return this.i18n.t('game.endBout');
    }
  }

  private messageKeyForError(error: unknown): TranslationKey {
    if (error instanceof HttpErrorResponse) {
      const body = error.error as { detail?: { code?: string } } | null;
      const code = body?.detail?.code;
      if (code === 'FEATURE_NOT_AVAILABLE') return 'game.featureUnavailable';
      if (code !== undefined && ERROR_KEYS[code] !== undefined) {
        return ERROR_KEYS[code];
      }
      if (error.status === 0) {
        return 'game.serverUnavailable';
      }
    }
    return 'game.moveRejected';
  }

  private loadCapabilities(freshEntry: boolean): void {
    this.api.getCapabilities().subscribe({
      next: (capabilities) => {
        this.multiplayerEnabled.set(capabilities.multiplayer_3_4_enabled);
        this.deckVariantsEnabled.set(capabilities.deck_variants_enabled ?? false);
        if (!freshEntry) return;
        if (capabilities.multiplayer_3_4_enabled || capabilities.deck_variants_enabled)
          this.showSetup.set(true);
        else this.startNewGame(2);
      },
      error: () => {
        this.multiplayerEnabled.set(false);
        this.deckVariantsEnabled.set(false);
        if (freshEntry) this.startNewGame(2);
      },
    });
  }

  private participantName(seat: GameResponse['required_seat'], game: GameResponse | null): string {
    return (
      game?.participants.find((participant) => participant.seat === seat)?.display_name ??
      this.i18n.t('game.bot')
    );
  }

  private opponentSeatsFor(game: GameResponse): readonly HiddenTableSeat[] {
    const participants = game.participants;
    const seatOrder = participants.map((participant) => participant.seat);
    return participants
      .filter((participant) => participant.seat !== game.human_seat)
      .map((participant) => ({
        id: participant.participant_id,
        seat: participant.seat,
        position: relativeSeatPosition(
          seatOrder,
          game.human_seat,
          participant.seat,
        ) as RemoteTableSeatPosition,
        displayName: participant.display_name,
        cardCount: participant.hand_count,
        badge: '🤖',
      }));
  }

  private positionForSeat(
    seat: GameResponse['human_seat'],
    game: GameResponse,
  ): RemoteTableSeatPosition | null {
    return (
      this.opponentSeatsFor(game).find((participant) => participant.seat === seat)?.position ?? null
    );
  }

  private remoteActionSource(
    events: readonly BotPresentationEvent[],
    game: GameResponse,
  ): RemoteTableSeatPosition | undefined {
    const event = [...events]
      .reverse()
      .find((candidate) =>
        ['BOT_INITIAL_ATTACK', 'BOT_DEFEND', 'BOT_TRANSFER', 'BOT_THROW_IN'].includes(
          candidate.type,
        ),
      );
    return event?.actor_seat
      ? (this.positionForSeat(event.actor_seat, game) ?? undefined)
      : undefined;
  }

  private remotePlayBatches(
    events: readonly BotPresentationEvent[],
    cards: readonly GameCard[],
    game: GameResponse,
  ): readonly {
    readonly from: RemoteTableSeatPosition;
    readonly count: number;
    readonly cards: readonly GameCard[];
  }[] {
    let cardIndex = 0;
    return events
      .filter((event) =>
        ['BOT_INITIAL_ATTACK', 'BOT_DEFEND', 'BOT_TRANSFER', 'BOT_THROW_IN'].includes(event.type),
      )
      .map((event) => {
        const batch = {
          from: (event.actor_seat ? this.positionForSeat(event.actor_seat, game) : null) ?? 'top',
          count: event.card_count,
          cards: cards.slice(cardIndex, cardIndex + event.card_count),
        };
        cardIndex += event.card_count;
        return batch;
      });
  }
}
