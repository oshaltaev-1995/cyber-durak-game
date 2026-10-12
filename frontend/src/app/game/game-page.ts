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
  effect,
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
  Seat,
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
import { BotSpeedControlComponent } from './components/bot-speed-control/bot-speed-control';
import { CardMotionOverlayComponent } from './components/card-motion-overlay/card-motion-overlay';
import {
  TableInspectionComponent,
  TableInspectionParticipant,
} from './components/table-inspection/table-inspection';
import { HandComponent } from './components/hand/hand';
import { HintPanelComponent } from './components/hint-panel/hint-panel';
import { TableSeatMapComponent } from './components/table-seat-map/table-seat-map';
import { TrumpIndicatorComponent } from './components/trump-indicator/trump-indicator';
import { TurnReminderComponent } from './components/turn-reminder/turn-reminder';
import { GameSessionState } from './game-session-state';
import { CardMotionController, MotionSnapshot, planCardMotions } from './presentation/card-motion';
import { BotPresentationQueue, BotPresentationSpeed } from './presentation/bot-presentation-queue';
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

function gamePresentationFrame(
  latest: GameResponse | null,
  event: BotPresentationEvent | null,
): GameResponse | null {
  const snapshot = event?.presentation_state;
  if (latest === null || snapshot === null || snapshot === undefined) return latest;
  return {
    ...latest,
    ...snapshot,
    result: snapshot.phase === 'complete' ? latest.result : null,
    human_hand: snapshot.viewer_hand,
    bot_hand_count: snapshot.hand_counts[latest.bot_seat] ?? latest.bot_hand_count,
    participants: latest.participants.map((participant) => ({
      ...participant,
      active: snapshot.active_seats.includes(participant.seat),
      finished: snapshot.finished_seats.includes(participant.seat),
      hand_count: snapshot.hand_counts[participant.seat] ?? participant.hand_count,
    })),
    required_actor:
      snapshot.required_seat === null
        ? null
        : snapshot.required_seat === latest.human_seat
          ? 'HUMAN'
          : 'BOT',
    available_actions: [],
  };
}

@Component({
  selector: 'app-game-page',
  imports: [
    ActionBarComponent,
    BotSpeedControlComponent,
    CardMotionOverlayComponent,
    DeckConfigSelectorComponent,
    TableInspectionComponent,
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
  providers: [CardMotionController, BotPresentationQueue],
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
  protected readonly presentation = inject(BotPresentationQueue);
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
  protected readonly botPresentation = this.presentation.current;
  private readonly presentationBaseline = signal<GameResponse | null>(null);
  protected readonly visibleGame = computed<GameResponse | null>(() => {
    const latest = this.game();
    if (!this.presentation.locked()) return latest;
    const revealed = this.presentation.revealed();
    if (revealed === null) return this.presentationBaseline() ?? latest;
    return gamePresentationFrame(latest, revealed);
  });
  protected readonly interactionLocked = computed(
    () => this.pending() || this.presentation.locked(),
  );
  protected readonly multiplayerEnabled = signal(false);
  protected readonly deckVariantsEnabled = signal(false);
  protected readonly capabilityState = signal<'loading' | 'ready'>('loading');
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
  protected readonly continuationIds = computed<ReadonlySet<string>>(
    () =>
      new Set(this.hints()?.continuation_physical_ids ?? this.hints()?.continuation_card_ids ?? []),
  );
  protected readonly recoveryState = signal<'idle' | 'loading' | 'unavailable' | 'failed'>('idle');
  protected readonly selectedCards = computed<readonly GameCard[]>(() => {
    const selected = this.selectedIds();
    return this.game()?.human_hand.filter((card) => selected.has(cardIdentity(card))) ?? [];
  });
  protected readonly statusText = computed(() => this.getStatusText());
  protected readonly isMultiplayer = computed(() => (this.game()?.total_players ?? 2) > 2);
  protected readonly localParticipant = computed(() =>
    this.visibleGame()?.participants.find(
      (participant) => participant.seat === this.visibleGame()?.human_seat,
    ),
  );
  protected readonly localFinishedWatching = computed(
    () => this.game()?.phase !== 'complete' && this.localParticipant()?.finished === true,
  );
  protected readonly opponentSeats = computed<readonly HiddenTableSeat[]>(() => {
    const game = this.visibleGame();
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
        presenting:
          (this.botPresentation()?.actor_seat ?? game.bot_seat) === participant.seat &&
          this.botPresentation() !== null,
      }));
  });
  protected readonly inspectionParticipants = computed<readonly TableInspectionParticipant[]>(
    () => {
      const game = this.visibleGame();
      if (game === null) return [];
      return game.participants.map((participant) => ({
        id: participant.participant_id,
        name: participant.display_name,
        cardCount:
          participant.seat === game.human_seat ? game.human_hand.length : participant.hand_count,
        isBot: participant.is_bot,
        isLocal: participant.seat === game.human_seat,
        roles: this.participantRoleLabels(game, participant.seat, participant.finished),
      }));
    },
  );
  protected readonly hasTopOpponent = computed(() =>
    this.opponentSeats().some((seat) => seat.position === 'top'),
  );
  protected readonly hasSideOpponents = computed(() =>
    this.opponentSeats().some((seat) => seat.position === 'left' || seat.position === 'right'),
  );
  protected readonly placements = computed(() => {
    const game = this.game();
    if (game === null) return [];
    return deriveMultiplayerPlacements(game.finish_groups).map((placement) => ({
      ...placement,
      participant: game.participants.find((participant) => participant.seat === placement.seat),
    }));
  });
  protected readonly nextTransferDefenderHandCount = computed(() => {
    const game = this.game();
    if (game === null || !game.transfer_open || game.defender === null) return null;
    const target = this.nextActiveSeat(game.active_seats, game.defender);
    return game.participants.find((participant) => participant.seat === target)?.hand_count ?? null;
  });
  private submittedAction: HumanActionType | null = null;
  private submittedCards: readonly GameCard[] = [];
  private hintSubscription: Subscription | null = null;
  private hintRequestGeneration = 0;
  private lastHintDecisionKey: string | null = null;
  private deferredStartPlayers: 2 | 3 | 4 | null = null;

  constructor() {
    effect(() => {
      this.hintPreference.enabled();
      this.game();
      this.presentation.locked();
      this.pending();
      this.restartConfirmation();
      this.selectedIds();
      this.refreshHints();
    });
  }

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
    if (this.storedSession.setupRequested()) {
      this.showSetup.set(true);
      this.loadCapabilities(false);
      return;
    }
    this.loadCapabilities(true);
  }

  ngOnDestroy(): void {
    this.clearHints();
    this.cardMotion.clear();
    this.presentation.clear();
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
    if (this.interactionLocked()) {
      return;
    }
    if (
      !isDefaultDeckConfig({
        deck_profile: this.selectedDeckProfile(),
        deck_count: this.selectedDeckCount(),
      }) &&
      !this.deckOnboarding.hasSeen()
    ) {
      this.deferredStartPlayers = totalPlayers;
      this.deckOnboardingVisible.set(true);
      return;
    }
    if (totalPlayers > 2 && !this.multiplayerOnboarding.hasSeen()) {
      this.deferredStartPlayers = totalPlayers;
      this.onboardingVisible.set(true);
      return;
    }
    this.createNewGame(totalPlayers);
  }

  private createNewGame(totalPlayers: 2 | 3 | 4): void {
    this.presentation.clear();
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
    request
      .pipe(
        finalize(() => {
          this.pending.set(false);
          if (!this.presentation.locked()) this.refreshHints();
        }),
      )
      .subscribe({
        next: (game) => {
          this.storedSession.save(game.game_id);
          this.game.set(game);
          this.selectedPlayers.set(game.total_players);
          this.selectedDeckProfile.set(game.deck_profile);
          this.selectedDeckCount.set(game.deck_count);
          this.selectedIds.set(new Set());
          this.queueBotStatuses(game.recent_events, null);
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

  protected setPresentationSpeed(speed: BotPresentationSpeed): void {
    this.presentation.setSpeed(speed);
  }

  protected playAgain(): void {
    const game = this.game();
    if (game === null || this.interactionLocked()) return;
    this.presentation.clear();
    this.cardMotion.clear();
    this.pending.set(true);
    this.errorKey.set(null);
    this.api
      .restartGame(game.game_id)
      .pipe(
        finalize(() => {
          this.pending.set(false);
          if (!this.presentation.locked()) this.refreshHints();
        }),
      )
      .subscribe({
        next: (restarted) => {
          this.storedSession.save(restarted.game_id);
          this.game.set(restarted);
          this.selectedPlayers.set(restarted.total_players);
          this.selectedDeckProfile.set(restarted.deck_profile);
          this.selectedDeckCount.set(restarted.deck_count);
          this.selectedIds.set(new Set());
          this.queueBotStatuses(restarted.recent_events, null);
        },
        error: (error: unknown) => this.errorKey.set(this.messageKeyForError(error)),
      });
  }

  protected changePlayers(): void {
    if (this.interactionLocked()) return;
    this.presentation.clear();
    this.clearHints();
    this.cardMotion.clear();
    this.restartConfirmation.set(false);
    this.onboardingVisible.set(false);
    this.deckOnboardingVisible.set(false);
    this.storedSession.requestSetup();
    this.game.set(null);
    this.showSetup.set(true);
  }

  protected confirmNewGame(): void {
    this.changePlayers();
  }

  protected dismissOnboarding(): void {
    this.multiplayerOnboarding.markSeen();
    this.onboardingVisible.set(false);
    this.resumeDeferredStart();
  }

  protected dismissDeckOnboarding(): void {
    this.deckOnboarding.markSeen();
    this.deckOnboardingVisible.set(false);
    this.resumeDeferredStart();
  }

  protected openMultiplayerGuide(): void {
    this.multiplayerOnboarding.markSeen();
    this.onboardingVisible.set(false);
    this.deferredStartPlayers = null;
  }

  protected openDeckGuide(): void {
    this.deckOnboarding.markSeen();
    this.deckOnboardingVisible.set(false);
    this.deferredStartPlayers = null;
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
    if (this.capabilityState() === 'loading' && this.recoveryState() === 'idle') {
      return this.i18n.t('game.loadingOptions');
    }
    if (this.interactionLocked()) {
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
    if (this.capabilityState() === 'loading' && this.recoveryState() === 'idle') {
      return this.i18n.t('game.loadingOptionsDescription');
    }
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
    if (this.interactionLocked()) {
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
    else {
      this.lastHintDecisionKey = null;
      this.clearHints();
    }
  }

  protected submitAction(action: HumanActionType): void {
    const game = this.game();
    if (game === null || this.interactionLocked() || !game.available_actions.includes(action)) {
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
      this.interactionLocked() ||
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

  private participantRoleLabels(
    game: GameResponse,
    seat: Seat,
    finished: boolean,
  ): readonly string[] {
    const labels: string[] = [];
    if (game.phase !== 'complete') {
      if (game.defender === seat) labels.push(this.i18n.t('pvp.defender'));
      if (game.attacker === seat) labels.push(this.i18n.t('pvp.currentAttacker'));
      if (game.lead_attacker === seat && game.attacker !== seat) {
        labels.push(this.i18n.t('pvp.leadAttacker'));
      }
      if (game.required_seat === seat) labels.push(this.i18n.t('pvp.currentTurn'));
    }
    if (finished) labels.push(this.i18n.t('pvp.finishedPlayer'));
    return labels;
  }

  private presentUpdatedGame(updatedGame: GameResponse): void {
    const previous = this.game();
    const localAction = this.submittedAction;
    const localCards = this.submittedCards;
    const synchronizedEvents =
      updatedGame.recent_events.length > 0 &&
      updatedGame.recent_events.every(
        (event) => event.presentation_state !== null && event.presentation_state !== undefined,
      );
    if (previous !== null && !synchronizedEvents && updatedGame.recent_events.length === 0) {
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
    this.queueBotStatuses(updatedGame.recent_events, previous, localAction, localCards);
  }

  private restoreGame(gameId: string): void {
    if (this.pending()) return;
    this.recoveryState.set('loading');
    this.clearHints();
    this.pending.set(true);
    this.errorKey.set(null);
    this.api
      .getGame(gameId)
      .pipe(
        finalize(() => {
          this.pending.set(false);
          this.refreshHints();
        }),
      )
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
    const game = this.game();
    const selected = this.selectedCards().map(cardIdentity);
    if (
      !this.hintPreference.enabled() ||
      game === null ||
      game.phase === 'complete' ||
      game.required_actor !== 'HUMAN' ||
      this.interactionLocked() ||
      this.restartConfirmation() ||
      !game.available_actions.some(
        (action) => CARD_ACTIONS.has(action) || action === 'TAKE' || action === 'BITO',
      )
    ) {
      if (!this.presentation.locked()) this.lastHintDecisionKey = null;
      this.clearHints();
      return;
    }
    const decisionKey = [
      game.game_id,
      game.required_seat ?? 'none',
      game.bout_phase ?? 'ready',
      game.packets.length,
      game.table_cards.map(cardIdentity).join(','),
      game.available_actions.join('-'),
      game.human_hand.map(cardIdentity).join(','),
      game.draw_pile_count,
      game.discard_count,
      selected.join(','),
    ].join(':');
    if (decisionKey === this.lastHintDecisionKey) return;
    this.lastHintDecisionKey = decisionKey;
    this.clearHints();
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

  private queueBotStatuses(
    events: readonly BotPresentationEvent[],
    baseline: GameResponse | null = this.game(),
    localAction: HumanActionType | null = null,
    localCards: readonly GameCard[] = [],
  ): void {
    const first = events[0];
    const latest = this.game();
    const initialBaseline =
      baseline ??
      (latest !== null && first?.type === 'BOT_INITIAL_ATTACK'
        ? {
            ...latest,
            table_cards: [],
            packets: [],
            active_packet: null,
            direct_anchor_cards: [],
            active_attack_value: null,
            total_attack_card_count: 0,
            table_arithmetic: {
              total_effective_value: 0,
              physical_card_count: 0,
              arithmetic_mean: null,
            },
          }
        : latest);
    let previousFrame = initialBaseline;
    if (events.length > 0) this.presentationBaseline.set(initialBaseline);
    this.presentation.play(
      events,
      () => {
        this.presentationBaseline.set(null);
        this.refreshHints();
      },
      (event, index) => {
        const nextFrame = gamePresentationFrame(this.game(), event);
        if (nextFrame === null) return;
        const cardAction = [
          'BOT_INITIAL_ATTACK',
          'BOT_DEFEND',
          'BOT_TRANSFER',
          'BOT_THROW_IN',
        ].includes(event.type);
        const previousSnapshot = previousFrame ?? nextFrame;
        this.cardMotion.play(
          planCardMotions(this.motionSnapshot(previousSnapshot), this.motionSnapshot(nextFrame), {
            localAction: index === 0 ? (localAction ?? undefined) : undefined,
            localCards: index === 0 ? localCards : [],
            remotePlays: cardAction
              ? [
                  {
                    from:
                      event.actor_seat === null || event.actor_seat === undefined
                        ? 'top'
                        : (this.positionForSeat(event.actor_seat, nextFrame) ?? 'top'),
                    count: event.card_count,
                    cards: event.cards ?? [],
                  },
                ]
              : [],
            resolvedTo: cardAction
              ? undefined
              : this.resolutionDestination(previousSnapshot, nextFrame),
          }),
        );
        previousFrame = nextFrame;
      },
    );
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
        return this.i18n.t('game.botNamedBito', { name });
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
    this.capabilityState.set('loading');
    this.api.getCapabilities().subscribe({
      next: (capabilities) => {
        this.multiplayerEnabled.set(capabilities.multiplayer_3_4_enabled);
        this.deckVariantsEnabled.set(capabilities.deck_variants_enabled ?? false);
        this.capabilityState.set('ready');
        if (!freshEntry) return;
        if (capabilities.multiplayer_3_4_enabled || capabilities.deck_variants_enabled)
          this.showSetup.set(true);
        else this.startNewGame(2);
      },
      error: () => {
        this.multiplayerEnabled.set(false);
        this.deckVariantsEnabled.set(false);
        this.capabilityState.set('ready');
        if (freshEntry) this.startNewGame(2);
      },
    });
  }

  private resumeDeferredStart(): void {
    const totalPlayers = this.deferredStartPlayers;
    if (totalPlayers === null) return;
    this.deferredStartPlayers = null;
    this.startNewGame(totalPlayers);
  }

  private participantName(seat: GameResponse['required_seat'], game: GameResponse | null): string {
    return (
      game?.participants.find((participant) => participant.seat === seat)?.display_name ??
      this.i18n.t('game.bot')
    );
  }

  private nextActiveSeat(activeSeats: readonly Seat[], seat: Seat): Seat | null {
    if (activeSeats.length < 2) return null;
    const index = activeSeats.indexOf(seat);
    return index < 0 ? null : (activeSeats[(index + 1) % activeSeats.length] ?? null);
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
          cards:
            (event.cards?.length ?? 0) > 0
              ? (event.cards ?? [])
              : cards.slice(cardIndex, cardIndex + event.card_count),
        };
        cardIndex += event.card_count;
        return batch;
      });
  }
}
