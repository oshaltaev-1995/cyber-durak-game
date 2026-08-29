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

const ERROR_MESSAGES: Readonly<Record<string, string>> = {
  WRONG_TURN: 'Сейчас ход соперника.',
  STALE_VERSION: 'Состояние обновилось. Повторите ход.',
  RATE_LIMITED: 'Слишком много действий. Подождите секунду.',
  GAME_COMPLETE: 'Эта партия уже завершена.',
  INVALID_CREDENTIAL: 'Не удалось восстановить место в комнате.',
  illegal_initial_attack: 'Эти карты нельзя объединить для первого хода.',
  illegal_defense: 'Недостаточно очков для покрытия текущей атаки.',
  illegal_transfer: 'Перевод должен точно совпадать со значением атаки.',
  illegal_throw_in: 'Эти карты сейчас нельзя подкинуть.',
  attack_card_limit_exceeded: 'Превышен лимит атакующих карт в этом коне.',
};

@Component({
  selector: 'app-pvp-room-page',
  imports: [
    ActionBarComponent,
    GameTableComponent,
    HandComponent,
    RouterLink,
    TrumpIndicatorComponent,
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
      await navigator.share({ title: 'Kiba — приватная игра', url: this.inviteUrl() });
    } catch {
      // Dismissed or unavailable native sharing leaves the copy fallback usable.
    }
  }

  protected canShare(): boolean {
    return navigator.share !== undefined;
  }

  protected activityTurn(
    version: number,
    requiredParticipantId: string | null,
    participantId: string | null,
  ): readonly string[] {
    if (participantId === null || requiredParticipantId !== participantId) return [];
    return [`${participantId}:${version}`];
  }

  protected connectionMessage(): string | null {
    const status = this.socket.status();
    if (status === 'connecting') return 'Подключаемся…';
    if (status === 'reconnecting') return 'Переподключение…';
    if (status === 'offline') return 'Нет соединения';
    if (status === 'disconnected') return 'Связь потеряна';
    if (status === 'error') {
      return this.socket.actionError()?.code === 'CONNECTION_REPLACED'
        ? 'Комната открыта в другой вкладке'
        : 'Не удалось подключиться';
    }
    if (this.socket.opponentStatus() === 'disconnected') {
      return 'Соперник отключился. Ждём возвращения…';
    }
    if (this.socket.opponentStatus() === 'returned') return 'Соперник вернулся';
    return null;
  }

  protected connectionNoticeText(): string | null {
    switch (this.socket.connectionNotice()) {
      case 'connection_restored':
        return 'Соединение восстановлено.';
      case 'action_recovered':
        return 'Соединение восстановлено. Показано актуальное состояние.';
      case 'state_updated':
        return 'Состояние игры обновилось.';
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
      ERROR_MESSAGES[error.domain_code ?? ''] ??
      ERROR_MESSAGES[error.code] ??
      'Ход не принят. Измените выбор и попробуйте снова.'
    );
  }

  protected resultTitle(): string {
    const state = this.state();
    if (state?.result?.outcome === 'DRAW') return 'Ничья 🤝';
    return state?.result?.winner_participant_id === state?.you.participant_id
      ? 'Вы победили! 🏆'
      : `Победил ${state?.result?.winner_display_name ?? 'соперник'}`;
  }

  protected leave(): void {
    this.leaveConfirmation.set(false);
    this.credentials.clear(this.inviteCode);
    this.socket.disconnect();
    void this.router.navigate(['/pvp']);
  }

  private getStatusText(): string {
    const state = this.state();
    if (this.socket.status() === 'connecting') return 'Подключаемся…';
    if (this.socket.status() === 'reconnecting') return 'Переподключение…';
    if (this.socket.status() === 'offline') return 'Нет соединения';
    if (this.socket.status() === 'disconnected' || this.socket.status() === 'error') {
      return 'Связь с комнатой потеряна';
    }
    if (state === null) return 'Загружаем комнату…';
    if (state.room_phase === 'WAITING_FOR_OPPONENT') return 'Ждём второго игрока…';
    if (state.game_phase === 'complete') return 'Партия завершена';
    if (state.required_participant_id !== state.you.participant_id) {
      return `${state.opponent?.display_name ?? 'Соперник'} думает…`;
    }
    if (state.available_actions.includes('INITIAL_ATTACK'))
      return 'Ваш ход — выберите карты для атаки';
    if (state.available_actions.includes('DEFEND'))
      return `Покройте больше ${state.active_attack_value ?? 0}`;
    if (state.available_actions.includes('THROW_IN')) return 'Можно подкинуть или закончить кон';
    return 'Ваш ход';
  }
}
