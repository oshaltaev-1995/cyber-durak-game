import { Injectable, signal } from '@angular/core';
import { HintResponse, HumanActionType } from '../api/game-api.models';
import {
  PvPConnectionNotice,
  PvPConnectionStatus,
  PvPErrorBody,
  PvPOpponentStatus,
  PvPServerMessage,
  PvPState,
} from './pvp.models';

const RECONNECT_DELAYS_MS = [500, 1_000, 2_000, 4_000, 5_000] as const;
const MAX_RECONNECT_ATTEMPTS = 8;
const HEALTH_CHECK_TIMEOUT_MS = 2_500;
const OPPONENT_RETURNED_NOTICE_MS = 2_500;
const TERMINAL_ROOM_ERRORS = new Set([
  'ROOM_NOT_FOUND',
  'ROOM_EXPIRED',
  'INVITE_EXPIRED',
  'ROOM_CLOSED',
]);

@Injectable({ providedIn: 'root' })
export class PvPWebSocketService {
  readonly state = signal<PvPState | null>(null);
  readonly status = signal<PvPConnectionStatus>('idle');
  readonly actionError = signal<PvPErrorBody | null>(null);
  readonly actionPending = signal(false);
  readonly rematchPending = signal(false);
  readonly hints = signal<HintResponse | null>(null);
  readonly hintPending = signal(false);
  readonly opponentStatus = signal<PvPOpponentStatus>('unknown');
  readonly connectionNotice = signal<PvPConnectionNotice>(null);
  readonly roomClosure = signal<'you_left' | 'opponent_left' | null>(null);
  readonly leavePending = signal(false);

  private socket: WebSocket | null = null;
  private inviteCode: string | null = null;
  private credential: string | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private healthTimer: ReturnType<typeof setTimeout> | null = null;
  private opponentNoticeTimer: ReturnType<typeof setTimeout> | null = null;
  private socketGeneration = 0;
  private reconnectAttempts = 0;
  private reconnectEnabled = false;
  private lifecycleBound = false;
  private uncertainAction = false;
  private hintRequestId = 0;

  private readonly handleOnline = (): void => this.resumeConnection();
  private readonly handleOffline = (): void => this.goOffline();
  private readonly handlePageShow = (): void => this.checkConnectionHealth();
  private readonly handleVisibility = (): void => {
    if (document.visibilityState === 'visible') this.checkConnectionHealth();
  };

  connect(inviteCode: string, credential: string, initialState: PvPState | null = null): void {
    const sameRoom = this.state()?.invite_code === inviteCode;
    this.stopSocket();
    this.inviteCode = inviteCode;
    this.credential = credential;
    this.reconnectEnabled = true;
    this.reconnectAttempts = 0;
    this.uncertainAction = false;
    this.actionPending.set(false);
    this.rematchPending.set(false);
    this.clearHints();
    this.actionError.set(null);
    this.connectionNotice.set(null);
    this.roomClosure.set(null);
    this.leavePending.set(false);
    if (!sameRoom) {
      this.state.set(null);
      this.opponentStatus.set('unknown');
    }
    if (initialState !== null) this.acceptState(initialState);
    this.bindLifecycleEvents();
    this.open(sameRoom || initialState !== null);
  }

  sendAction(action: HumanActionType, cardIds: readonly string[]): void {
    const state = this.state();
    if (
      this.status() !== 'connected' ||
      this.socket?.readyState !== WebSocket.OPEN ||
      state === null ||
      this.actionPending()
    ) {
      return;
    }
    this.actionPending.set(true);
    this.clearHints();
    this.actionError.set(null);
    this.connectionNotice.set(null);
    this.socket.send(
      JSON.stringify({ type: 'ACTION', version: state.version, action, card_ids: cardIds }),
    );
  }

  requestHints(selectedPhysicalIds: readonly string[]): void {
    const state = this.state();
    if (
      selectedPhysicalIds.length === 0 ||
      this.status() !== 'connected' ||
      this.socket?.readyState !== WebSocket.OPEN ||
      state === null ||
      state.capacity !== 2 ||
      state.required_participant_id !== state.you.participant_id ||
      this.actionPending()
    ) {
      this.clearHints();
      return;
    }
    const requestId = ++this.hintRequestId;
    this.hints.set(null);
    this.hintPending.set(true);
    this.socket.send(
      JSON.stringify({
        type: 'HINT_REQUEST',
        request_id: requestId,
        version: state.version,
        selected_physical_ids: selectedPhysicalIds,
      }),
    );
  }

  clearHints(): void {
    this.hintRequestId += 1;
    this.hints.set(null);
    this.hintPending.set(false);
  }

  leaveRoom(): void {
    if (
      this.status() !== 'connected' ||
      this.socket?.readyState !== WebSocket.OPEN ||
      this.state() === null ||
      this.leavePending()
    ) {
      return;
    }
    this.leavePending.set(true);
    this.actionError.set(null);
    this.socket.send(JSON.stringify({ type: 'LEAVE' }));
  }

  requestRematch(): void {
    this.sendRematch('REMATCH_REQUEST');
  }

  acceptRematch(): void {
    this.sendRematch('REMATCH_ACCEPT');
  }

  declineRematch(): void {
    this.sendRematch('REMATCH_DECLINE');
  }

  cancelRematch(): void {
    this.sendRematch('REMATCH_CANCEL');
  }

  retry(): void {
    if (
      this.inviteCode === null ||
      this.credential === null ||
      this.status() === 'expired' ||
      this.status() === 'idle'
    ) {
      return;
    }
    this.reconnectEnabled = true;
    this.reconnectAttempts = 0;
    this.cancelReconnectTimer();
    this.stopSocket();
    this.open(true);
  }

  disconnect(): void {
    this.reconnectEnabled = false;
    this.cancelReconnectTimer();
    this.clearHealthTimer();
    this.clearOpponentNoticeTimer();
    this.stopSocket(1000, 'client navigation');
    this.unbindLifecycleEvents();
    this.status.set('idle');
    this.actionPending.set(false);
    this.rematchPending.set(false);
    this.clearHints();
    this.leavePending.set(false);
    this.uncertainAction = false;
  }

  private open(reconnecting: boolean): void {
    if (!this.reconnectEnabled || this.inviteCode === null || this.credential === null) return;
    if (navigator.onLine === false) {
      this.status.set('offline');
      return;
    }
    this.cancelReconnectTimer();
    this.status.set(reconnecting || this.state() !== null ? 'reconnecting' : 'connecting');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const path = `/api/pvp/rooms/${encodeURIComponent(this.inviteCode)}/ws`;
    const generation = ++this.socketGeneration;
    const socket = new WebSocket(`${protocol}//${window.location.host}${path}`);
    this.socket = socket;
    socket.addEventListener('open', () => {
      if (!this.isCurrent(socket, generation)) return;
      socket.send(JSON.stringify({ type: 'AUTH', credential: this.credential }));
    });
    socket.addEventListener('message', (event) => {
      if (!this.isCurrent(socket, generation)) return;
      this.handleMessage(String(event.data), socket, generation);
    });
    socket.addEventListener('close', (event) => {
      if (!this.isCurrent(socket, generation)) return;
      this.socket = null;
      this.clearHealthTimer();
      if (this.actionPending()) this.uncertainAction = true;
      this.actionPending.set(false);
      this.rematchPending.set(false);
      this.leavePending.set(false);
      if (!this.reconnectEnabled) return;
      if (event.code === 4001) {
        this.reconnectEnabled = false;
        this.status.set('error');
        this.actionError.set({ code: 'CONNECTION_REPLACED', domain_code: null });
        return;
      }
      if (event.code === 4404) {
        this.stopForTerminalError({ code: 'ROOM_NOT_FOUND', domain_code: null });
        return;
      }
      if (event.code === 4401) {
        this.reconnectEnabled = false;
        this.status.set('error');
        return;
      }
      this.scheduleReconnect();
    });
  }

  private handleMessage(raw: string, socket: WebSocket, generation: number): void {
    let message: PvPServerMessage;
    try {
      message = JSON.parse(raw) as PvPServerMessage;
    } catch {
      this.actionError.set({ code: 'INVALID_MESSAGE', domain_code: null });
      return;
    }
    switch (message.type) {
      case 'STATE':
      case 'GAME_COMPLETE': {
        const wasRecovering = this.status() !== 'connected' && this.state() !== null;
        if (!this.acceptState(message.state)) return;
        this.clearHealthTimer();
        this.reconnectAttempts = 0;
        this.status.set('connected');
        this.actionPending.set(false);
        this.rematchPending.set(false);
        this.leavePending.set(false);
        if (this.uncertainAction) {
          this.connectionNotice.set('action_recovered');
          this.uncertainAction = false;
        } else if (wasRecovering && this.connectionNotice() !== 'state_updated') {
          this.connectionNotice.set('connection_restored');
        }
        return;
      }
      case 'ACTION_REJECTED':
        this.actionError.set(message.error);
        this.actionPending.set(false);
        if (message.error.code === 'STALE_VERSION') {
          this.connectionNotice.set('state_updated');
        }
        return;
      case 'REMATCH_REJECTED':
        this.actionError.set(message.error);
        this.rematchPending.set(false);
        if (message.error.code === 'STALE_VERSION') {
          this.connectionNotice.set('state_updated');
        }
        return;
      case 'HINTS': {
        const state = this.state();
        if (
          message.request_id !== this.hintRequestId ||
          state === null ||
          message.version !== state.version
        ) {
          return;
        }
        this.hints.set(message.hints);
        this.hintPending.set(false);
        return;
      }
      case 'HINTS_REJECTED':
        if (message.request_id === undefined || message.request_id === this.hintRequestId) {
          this.hints.set(null);
          this.hintPending.set(false);
        }
        return;
      case 'ERROR':
        this.actionPending.set(false);
        this.rematchPending.set(false);
        this.leavePending.set(false);
        if (TERMINAL_ROOM_ERRORS.has(message.error.code)) {
          this.stopForTerminalError(message.error);
        } else if (message.error.code === 'INVALID_CREDENTIAL') {
          this.reconnectEnabled = false;
          this.status.set('error');
          this.actionError.set(message.error);
          this.stopSocket(4401, 'authorization failed');
        } else {
          this.actionError.set(message.error);
        }
        return;
      case 'ROOM_CLOSED': {
        const localParticipantId = message.state.you.participant_id;
        this.state.set(message.state);
        this.roomClosure.set(
          message.left_participant_id === localParticipantId ? 'you_left' : 'opponent_left',
        );
        this.reconnectEnabled = false;
        this.cancelReconnectTimer();
        this.clearHealthTimer();
        this.clearOpponentNoticeTimer();
        this.actionPending.set(false);
        this.rematchPending.set(false);
        this.leavePending.set(false);
        this.opponentStatus.set('unknown');
        this.status.set('idle');
        this.stopSocket(1000, 'room intentionally closed');
        this.unbindLifecycleEvents();
        return;
      }
      case 'OPPONENT_DISCONNECTED':
        if (this.isCurrentVersion(message.version)) {
          this.applyParticipantConnection(message.participant_id, false);
          if (this.state()?.capacity === 2) this.setOpponentDisconnected();
        }
        return;
      case 'OPPONENT_CONNECTED':
        if (this.isCurrentVersion(message.version)) {
          this.applyParticipantConnection(message.participant_id, true);
          if (this.state()?.capacity === 2) this.setOpponentConnected();
        }
        return;
      case 'PARTICIPANT_LEFT':
        if (this.isCurrentVersion(message.version))
          this.applyParticipantLeft(message.participant_id);
        return;
      case 'PONG':
        if (!this.isCurrent(socket, generation)) return;
        this.clearHealthTimer();
        return;
    }
  }

  private acceptState(state: PvPState): boolean {
    const current = this.state();
    if (
      current !== null &&
      state.invite_code === current.invite_code &&
      state.version < current.version
    ) {
      return false;
    }
    this.clearHints();
    this.state.set(state);
    if (this.actionError()?.code !== 'STALE_VERSION') this.actionError.set(null);
    if (state.capacity !== 2 || state.opponent === null) {
      this.opponentStatus.set('unknown');
    } else if (state.opponent.connected) {
      if (this.opponentStatus() !== 'returned') this.setOpponentConnected();
    } else {
      this.setOpponentDisconnected();
    }
    return true;
  }

  private sendRematch(
    type: 'REMATCH_REQUEST' | 'REMATCH_ACCEPT' | 'REMATCH_DECLINE' | 'REMATCH_CANCEL',
  ): void {
    const state = this.state();
    if (
      this.status() !== 'connected' ||
      this.socket?.readyState !== WebSocket.OPEN ||
      state?.room_phase !== 'COMPLETE' ||
      state.match_id === null ||
      this.rematchPending()
    ) {
      return;
    }
    this.rematchPending.set(true);
    this.actionError.set(null);
    this.socket.send(JSON.stringify({ type, version: state.version, match_id: state.match_id }));
  }

  private scheduleReconnect(): void {
    if (!this.reconnectEnabled) return;
    if (navigator.onLine === false) {
      this.status.set('offline');
      return;
    }
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      this.status.set('disconnected');
      return;
    }
    const delay =
      RECONNECT_DELAYS_MS[Math.min(this.reconnectAttempts, RECONNECT_DELAYS_MS.length - 1)];
    this.reconnectAttempts += 1;
    this.status.set('reconnecting');
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.open(true);
    }, delay);
  }

  private resumeConnection(): void {
    if (!this.reconnectEnabled) return;
    this.cancelReconnectTimer();
    this.stopSocket();
    this.open(true);
  }

  private goOffline(): void {
    if (!this.reconnectEnabled) return;
    if (this.actionPending()) this.uncertainAction = true;
    this.actionPending.set(false);
    this.rematchPending.set(false);
    this.cancelReconnectTimer();
    this.stopSocket();
    this.status.set('offline');
  }

  private checkConnectionHealth(): void {
    if (!this.reconnectEnabled) return;
    if (navigator.onLine === false) {
      this.goOffline();
      return;
    }
    if (this.socket?.readyState !== WebSocket.OPEN) {
      this.resumeConnection();
      return;
    }
    this.socket.send(JSON.stringify({ type: 'PING' }));
    this.clearHealthTimer();
    const socket = this.socket;
    const generation = this.socketGeneration;
    this.healthTimer = setTimeout(() => {
      if (!this.isCurrent(socket, generation)) return;
      this.stopSocket();
      this.scheduleReconnect();
    }, HEALTH_CHECK_TIMEOUT_MS);
  }

  private stopForTerminalError(error: PvPErrorBody): void {
    this.reconnectEnabled = false;
    this.cancelReconnectTimer();
    this.clearHealthTimer();
    this.actionError.set(error);
    this.status.set('expired');
    this.stopSocket(4404, 'room unavailable');
  }

  private stopSocket(code?: number, reason?: string): void {
    const socket = this.socket;
    this.socket = null;
    this.socketGeneration += 1;
    if (socket !== null && socket.readyState < WebSocket.CLOSING) socket.close(code, reason);
  }

  private isCurrent(socket: WebSocket, generation: number): boolean {
    return this.socket === socket && this.socketGeneration === generation;
  }

  private isCurrentVersion(version: number): boolean {
    const current = this.state();
    return current === null || version >= current.version;
  }

  private applyParticipantConnection(participantId: string, connected: boolean): void {
    const state = this.state();
    if (
      state === null ||
      !state.players.some((player) => player.participant_id === participantId)
    ) {
      return;
    }
    const players = state.players.map((player) =>
      player.participant_id === participantId ? { ...player, connected } : player,
    );
    const opponent =
      state.opponent?.participant_id === participantId
        ? { ...state.opponent, connected }
        : state.opponent;
    this.state.set({ ...state, players, opponent });
  }

  private applyParticipantLeft(participantId: string): void {
    const state = this.state();
    if (state === null || state.room_phase !== 'WAITING_FOR_OPPONENT') return;
    const players = state.players.filter((player) => player.participant_id !== participantId);
    this.state.set({ ...state, players, joined_count: players.length });
  }

  private setOpponentDisconnected(): void {
    this.clearOpponentNoticeTimer();
    this.opponentStatus.set('disconnected');
  }

  private setOpponentConnected(): void {
    const returned = this.opponentStatus() === 'disconnected';
    this.clearOpponentNoticeTimer();
    this.opponentStatus.set(returned ? 'returned' : 'connected');
    if (returned) {
      this.opponentNoticeTimer = setTimeout(() => {
        if (this.opponentStatus() === 'returned') this.opponentStatus.set('connected');
      }, OPPONENT_RETURNED_NOTICE_MS);
    }
  }

  private bindLifecycleEvents(): void {
    if (this.lifecycleBound) return;
    window.addEventListener('online', this.handleOnline);
    window.addEventListener('offline', this.handleOffline);
    window.addEventListener('pageshow', this.handlePageShow);
    document.addEventListener('visibilitychange', this.handleVisibility);
    this.lifecycleBound = true;
  }

  private unbindLifecycleEvents(): void {
    if (!this.lifecycleBound) return;
    window.removeEventListener('online', this.handleOnline);
    window.removeEventListener('offline', this.handleOffline);
    window.removeEventListener('pageshow', this.handlePageShow);
    document.removeEventListener('visibilitychange', this.handleVisibility);
    this.lifecycleBound = false;
  }

  private cancelReconnectTimer(): void {
    if (this.reconnectTimer !== null) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
  }

  private clearHealthTimer(): void {
    if (this.healthTimer !== null) clearTimeout(this.healthTimer);
    this.healthTimer = null;
  }

  private clearOpponentNoticeTimer(): void {
    if (this.opponentNoticeTimer !== null) clearTimeout(this.opponentNoticeTimer);
    this.opponentNoticeTimer = null;
  }
}
