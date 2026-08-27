import { Injectable, signal } from '@angular/core';
import { HumanActionType } from '../api/game-api.models';
import { PvPConnectionStatus, PvPErrorBody, PvPServerMessage, PvPState } from './pvp.models';

const RECONNECT_DELAY_MS = 800;

@Injectable({ providedIn: 'root' })
export class PvPWebSocketService {
  readonly state = signal<PvPState | null>(null);
  readonly status = signal<PvPConnectionStatus>('idle');
  readonly actionError = signal<PvPErrorBody | null>(null);
  readonly actionPending = signal(false);
  readonly opponentDisconnected = signal(false);

  private socket: WebSocket | null = null;
  private inviteCode: string | null = null;
  private credential: string | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalClose = false;

  connect(inviteCode: string, credential: string, initialState: PvPState | null = null): void {
    this.disconnect();
    this.inviteCode = inviteCode;
    this.credential = credential;
    this.intentionalClose = false;
    if (initialState !== null) this.acceptState(initialState);
    this.open(false);
  }

  sendAction(action: HumanActionType, cards: readonly string[]): void {
    const state = this.state();
    if (this.socket?.readyState !== WebSocket.OPEN || state === null || this.actionPending())
      return;
    this.actionPending.set(true);
    this.actionError.set(null);
    this.socket.send(JSON.stringify({ type: 'ACTION', version: state.version, action, cards }));
  }

  disconnect(): void {
    this.intentionalClose = true;
    if (this.reconnectTimer !== null) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.socket?.close(1000, 'client navigation');
    this.socket = null;
    this.status.set('idle');
    this.actionPending.set(false);
  }

  private open(reconnecting: boolean): void {
    if (this.inviteCode === null || this.credential === null) return;
    this.status.set(reconnecting ? 'reconnecting' : 'connecting');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const path = `/api/pvp/rooms/${encodeURIComponent(this.inviteCode)}/ws`;
    const socket = new WebSocket(`${protocol}//${window.location.host}${path}`);
    this.socket = socket;
    socket.addEventListener('open', () => {
      this.status.set('connected');
      socket.send(JSON.stringify({ type: 'AUTH', credential: this.credential }));
    });
    socket.addEventListener('message', (event) => this.handleMessage(String(event.data)));
    socket.addEventListener('error', () => this.status.set('disconnected'));
    socket.addEventListener('close', () => {
      if (this.socket !== socket) return;
      this.socket = null;
      this.actionPending.set(false);
      if (this.intentionalClose) return;
      this.status.set('reconnecting');
      this.reconnectTimer = setTimeout(() => this.open(true), RECONNECT_DELAY_MS);
    });
  }

  private handleMessage(raw: string): void {
    let message: PvPServerMessage;
    try {
      message = JSON.parse(raw) as PvPServerMessage;
    } catch {
      this.actionError.set({ code: 'INVALID_MESSAGE', domain_code: null });
      return;
    }
    switch (message.type) {
      case 'STATE':
      case 'GAME_COMPLETE':
        this.acceptState(message.state);
        this.actionPending.set(false);
        return;
      case 'ACTION_REJECTED':
      case 'ERROR':
        this.actionError.set(message.error);
        this.actionPending.set(false);
        return;
      case 'OPPONENT_DISCONNECTED':
        this.opponentDisconnected.set(true);
        return;
      case 'OPPONENT_CONNECTED':
        this.opponentDisconnected.set(false);
        return;
      case 'PONG':
        return;
    }
  }

  private acceptState(state: PvPState): void {
    const current = this.state();
    if (
      current !== null &&
      state.invite_code === current.invite_code &&
      state.version < current.version
    ) {
      return;
    }
    this.state.set(state);
    this.actionError.set(null);
    this.opponentDisconnected.set(state.opponent !== null && !state.opponent.connected);
  }
}
