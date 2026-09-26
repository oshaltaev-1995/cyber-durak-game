import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  OnInit,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { GameCard, HumanActionType } from '../core/api/game-api.models';
import { PvPCredentialStore } from '../core/pvp/pvp-credential.store';
import { PvPWebSocketService } from '../core/pvp/pvp-websocket.service';
import { ActionBarComponent } from '../game/components/action-bar/action-bar';
import { GameTableComponent } from '../game/components/game-table/game-table';
import { HandComponent } from '../game/components/hand/hand';
import { TrumpIndicatorComponent } from '../game/components/trump-indicator/trump-indicator';
import { TurnReminderComponent } from '../game/components/turn-reminder/turn-reminder';
import { TranslationService } from '../core/i18n/translation.service';
import { TranslationKey } from '../core/i18n/translations/ru';

const ERROR_KEYS: Readonly<Record<string, TranslationKey>> = {
  WRONG_TURN: 'error.wrong_turn',
  STALE_VERSION: 'pvp.stale',
  RATE_LIMITED: 'pvp.rateLimited',
  GAME_COMPLETE: 'pvp.gameCompleteError',
  INVALID_CREDENTIAL: 'pvp.invalidCredential',
  illegal_initial_attack: 'error.illegal_initial_attack',
  illegal_defense: 'error.illegal_defense',
  illegal_transfer: 'error.illegal_transfer',
  illegal_throw_in: 'error.illegal_throw_in',
  attack_card_limit_exceeded: 'error.attack_card_limit_exceeded',
};

@Component({
  selector: 'app-pvp-room-page',
  imports: [
    ActionBarComponent,
    GameTableComponent,
    HandComponent,
    RouterLink,
    TrumpIndicatorComponent,
    TurnReminderComponent,
  ],
  templateUrl: './pvp-room-page.html',
  styleUrls: ['../game/game-page.css', './pvp-room-page.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PvPRoomPageComponent implements OnInit, OnDestroy {
  private readonly credentials = inject(PvPCredentialStore);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  protected readonly socket = inject(PvPWebSocketService);
  protected readonly i18n = inject(TranslationService);
  protected readonly selectedCodes = signal<ReadonlySet<string>>(new Set());
  protected readonly copyStatus = signal<'idle' | 'copied' | 'failed'>('idle');
  protected readonly leaveConfirmation = signal(false);
  protected readonly state = this.socket.state;
  protected readonly selectedCards = computed<readonly GameCard[]>(() => {
    const selected = this.selectedCodes();
    return this.state()?.hand.filter((card) => selected.has(card.code)) ?? [];
  });
  protected readonly inviteUrl = computed(
    () => `${window.location.origin}/join/${this.inviteCode}`,
  );
  protected readonly statusText = computed(() => this.getStatusText());
  protected inviteCode = '';
  private lastVersion = -1;

  constructor() {
    effect(() => {
      const current = this.state();
      if (current !== null) {
        if (current.version > this.lastVersion && this.lastVersion >= 0) {
          this.selectedCodes.set(new Set());
        } else {
          const ownedCodes = new Set(current.hand.map((card) => card.code));
          this.selectedCodes.update(
            (selected) => new Set([...selected].filter((code) => ownedCodes.has(code))),
          );
        }
        this.lastVersion = Math.max(this.lastVersion, current.version);
      }
    });
    effect(() => {
      const errorCode = this.socket.actionError()?.code;
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
    this.socket.disconnect();
  }

  protected toggleCard(code: string): void {
    if (this.socket.actionPending()) return;
    this.selectedCodes.update((current) => {
      const next = new Set(current);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
    this.socket.actionError.set(null);
  }

  protected submitAction(action: HumanActionType): void {
    const state = this.state();
    if (state === null || !state.available_actions.includes(action)) return;
    const cards =
      action === 'INITIAL_ATTACK' ||
      action === 'DEFEND' ||
      action === 'TRANSFER' ||
      action === 'THROW_IN'
        ? this.selectedCards().map((card) => card.code)
        : [];
    this.socket.sendAction(action, cards);
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

  protected localDecisionContext(): string | null {
    const state = this.state();
    if (
      state === null ||
      state.game_phase === 'complete' ||
      state.required_participant_id !== state.you.participant_id ||
      this.socket.actionPending() ||
      this.socket.status() !== 'connected'
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

  protected leave(): void {
    this.leaveConfirmation.set(false);
    this.credentials.clear(this.inviteCode);
    this.socket.disconnect();
    void this.router.navigate(['/pvp']);
  }

  private getStatusText(): string {
    const state = this.state();
    if (this.socket.status() === 'connecting') return this.i18n.t('pvp.connecting');
    if (this.socket.status() === 'reconnecting') return this.i18n.t('pvp.reconnecting');
    if (this.socket.status() === 'offline') return this.i18n.t('pvp.offline');
    if (this.socket.status() === 'disconnected' || this.socket.status() === 'error') {
      return this.i18n.t('pvp.connectionLost');
    }
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
}
