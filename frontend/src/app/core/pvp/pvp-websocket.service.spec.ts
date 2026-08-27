import { TestBed } from '@angular/core/testing';
import { PvPWebSocketService } from './pvp-websocket.service';
import { PvPState } from './pvp.models';

class FakeWebSocket extends EventTarget {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  static instances: FakeWebSocket[] = [];
  readonly url: string;
  readyState = FakeWebSocket.CONNECTING;
  readonly sent: string[] = [];
  closeCode: number | undefined;

  constructor(url: string | URL) {
    super();
    this.url = String(url);
    FakeWebSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(code?: number): void {
    this.closeCode = code;
    this.readyState = FakeWebSocket.CLOSED;
  }

  open(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.dispatchEvent(new Event('open'));
  }

  message(value: unknown): void {
    this.dispatchEvent(new MessageEvent('message', { data: JSON.stringify(value) }));
  }

  drop(code = 1006): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.dispatchEvent(new CloseEvent('close', { code }));
  }
}

const state = (version: number, opponent: PvPState['opponent'] = null): PvPState =>
  ({ invite_code: 'ABC123', version, opponent }) as unknown as PvPState;

const opponent = (connected: boolean): NonNullable<PvPState['opponent']> => ({
  participant_id: 'p2',
  seat: 'two',
  display_name: 'Bob',
  connected,
  authenticated: false,
});

describe('PvPWebSocketService', () => {
  let service: PvPWebSocketService;
  let originalOnline: PropertyDescriptor | undefined;

  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
    originalOnline = Object.getOwnPropertyDescriptor(navigator, 'onLine');
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true });
    TestBed.configureTestingModule({});
    service = TestBed.inject(PvPWebSocketService);
  });

  afterEach(() => {
    service.disconnect();
    if (originalOnline === undefined) Reflect.deleteProperty(navigator, 'onLine');
    else Object.defineProperty(navigator, 'onLine', originalOnline);
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  function authenticate(socket: FakeWebSocket, current = state(1)): void {
    socket.open();
    socket.message({ type: 'STATE', state: current });
  }

  it('uses current origin, authenticates first, and sends one versioned action', () => {
    service.connect('ABC123', 'secret', state(4));
    const socket = FakeWebSocket.instances[0];
    expect(socket.url).toContain('/api/pvp/rooms/ABC123/ws');
    expect(socket.url).not.toContain('secret');
    authenticate(socket, state(4));
    expect(JSON.parse(socket.sent[0])).toEqual({ type: 'AUTH', credential: 'secret' });

    service.sendAction('DEFEND', ['QS']);
    service.sendAction('DEFEND', ['KS']);
    expect(JSON.parse(socket.sent[1])).toEqual({
      type: 'ACTION',
      version: 4,
      action: 'DEFEND',
      cards: ['QS'],
    });
    expect(socket.sent).toHaveLength(2);
    expect(service.actionPending()).toBe(true);
  });

  it('ignores older state, safely accepts equal state, and applies newer state', () => {
    service.connect('ABC123', 'secret', state(3));
    const socket = FakeWebSocket.instances[0];
    authenticate(socket, state(3));
    socket.message({ type: 'STATE', state: state(2) });
    expect(service.state()?.version).toBe(3);
    socket.message({ type: 'STATE', state: state(3, opponent(false)) });
    expect(service.state()?.version).toBe(3);
    expect(service.opponentStatus()).toBe('disconnected');
    socket.message({ type: 'STATE', state: state(5, opponent(true)) });
    expect(service.state()?.version).toBe(5);
  });

  it('uses bounded exponential reconnect delays and allows manual retry', () => {
    vi.useFakeTimers();
    service.connect('ABC123', 'secret');
    FakeWebSocket.instances[0].drop();
    expect(service.status()).toBe('reconnecting');
    vi.advanceTimersByTime(499);
    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(2);
    FakeWebSocket.instances[1].drop();
    vi.advanceTimersByTime(999);
    expect(FakeWebSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(3);

    for (let attempt = 2; attempt < 8; attempt += 1) {
      FakeWebSocket.instances.at(-1)?.drop();
      vi.advanceTimersByTime(attempt === 2 ? 2_000 : attempt === 3 ? 4_000 : 5_000);
    }
    FakeWebSocket.instances.at(-1)?.drop();
    expect(service.status()).toBe('disconnected');
    const beforeRetry = FakeWebSocket.instances.length;
    service.retry();
    expect(FakeWebSocket.instances).toHaveLength(beforeRetry + 1);
  });

  it('does not reconnect after intentional disconnect', () => {
    vi.useFakeTimers();
    service.connect('ABC123', 'secret');
    const socket = FakeWebSocket.instances[0];
    service.disconnect();
    socket.drop();
    vi.runAllTimers();
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(service.status()).toBe('idle');
  });

  it('ignores handlers from a replaced local socket generation', () => {
    service.connect('ABC123', 'secret', state(2));
    const oldSocket = FakeWebSocket.instances[0];
    service.connect('ABC123', 'secret', state(2));
    const currentSocket = FakeWebSocket.instances[1];
    oldSocket.message({ type: 'STATE', state: state(99) });
    oldSocket.drop();
    expect(service.state()?.version).toBe(2);
    expect(service.status()).toBe('reconnecting');
    authenticate(currentSocket, state(3));
    expect(service.state()?.version).toBe(3);
    expect(service.status()).toBe('connected');
  });

  it('recovers an uncertain pending action from authoritative reconnect state without resending', () => {
    vi.useFakeTimers();
    service.connect('ABC123', 'secret');
    const first = FakeWebSocket.instances[0];
    authenticate(first, state(4));
    service.sendAction('DEFEND', ['QS']);
    expect(service.actionPending()).toBe(true);
    first.drop();
    expect(service.actionPending()).toBe(false);
    vi.advanceTimersByTime(500);
    const replacement = FakeWebSocket.instances[1];
    authenticate(replacement, state(5));

    expect(service.state()?.version).toBe(5);
    expect(service.connectionNotice()).toBe('action_recovered');
    expect(replacement.sent.map((value) => JSON.parse(value).type)).toEqual(['AUTH']);
  });

  it('handles stale rejection and the following latest authoritative state', () => {
    service.connect('ABC123', 'secret');
    const socket = FakeWebSocket.instances[0];
    authenticate(socket, state(4));
    service.sendAction('DEFEND', ['QS']);
    socket.message({
      type: 'ACTION_REJECTED',
      error: { code: 'STALE_VERSION', domain_code: null },
    });
    socket.message({ type: 'STATE', state: state(5) });
    expect(service.state()?.version).toBe(5);
    expect(service.actionPending()).toBe(false);
    expect(service.connectionNotice()).toBe('state_updated');
    expect(service.actionError()?.code).toBe('STALE_VERSION');
  });

  it('uses offline and online lifecycle events to reconnect through a new socket', () => {
    service.connect('ABC123', 'secret');
    authenticate(FakeWebSocket.instances[0], state(1));
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false });
    window.dispatchEvent(new Event('offline'));
    expect(service.status()).toBe('offline');
    const offlineCount = FakeWebSocket.instances.length;

    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true });
    window.dispatchEvent(new Event('online'));
    expect(FakeWebSocket.instances).toHaveLength(offlineCount + 1);
    authenticate(FakeWebSocket.instances.at(-1)!, state(1));
    expect(service.status()).toBe('connected');
    expect(service.connectionNotice()).toBe('connection_restored');
  });

  it('health-checks on pageshow and reconnects when the socket does not answer', () => {
    vi.useFakeTimers();
    service.connect('ABC123', 'secret');
    const socket = FakeWebSocket.instances[0];
    authenticate(socket, state(1));
    window.dispatchEvent(new PageTransitionEvent('pageshow'));
    expect(JSON.parse(socket.sent.at(-1)!)).toEqual({ type: 'PING' });
    vi.advanceTimersByTime(2_500);
    expect(service.status()).toBe('reconnecting');
    vi.advanceTimersByTime(500);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it('health-checks only when a backgrounded document becomes visible again', () => {
    service.connect('ABC123', 'secret');
    const socket = FakeWebSocket.instances[0];
    authenticate(socket, state(1));
    const originalVisibility = Object.getOwnPropertyDescriptor(document, 'visibilityState');
    try {
      Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
      document.dispatchEvent(new Event('visibilitychange'));
      expect(socket.sent.map((value) => JSON.parse(value).type)).toEqual(['AUTH']);

      Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
      document.dispatchEvent(new Event('visibilitychange'));
      expect(JSON.parse(socket.sent.at(-1)!)).toEqual({ type: 'PING' });
      socket.message({ type: 'PONG', version: 1 });
      expect(service.status()).toBe('connected');
    } finally {
      if (originalVisibility === undefined) {
        Reflect.deleteProperty(document, 'visibilityState');
      } else {
        Object.defineProperty(document, 'visibilityState', originalVisibility);
      }
    }
  });

  it('shows opponent disconnect and temporary returned status without changing room version', () => {
    vi.useFakeTimers();
    service.connect('ABC123', 'secret');
    const socket = FakeWebSocket.instances[0];
    authenticate(socket, state(7, opponent(true)));
    socket.message({ type: 'OPPONENT_DISCONNECTED', version: 7 });
    expect(service.opponentStatus()).toBe('disconnected');
    socket.message({ type: 'OPPONENT_CONNECTED', version: 7 });
    expect(service.opponentStatus()).toBe('returned');
    socket.message({ type: 'STATE', state: state(7, opponent(true)) });
    expect(service.opponentStatus()).toBe('returned');
    expect(service.state()?.version).toBe(7);
    vi.advanceTimersByTime(2_500);
    expect(service.opponentStatus()).toBe('connected');
  });

  it('stops reconnecting on expired room, invalid credential, or replacement close', () => {
    vi.useFakeTimers();
    service.connect('ABC123', 'secret');
    const expired = FakeWebSocket.instances[0];
    expired.open();
    expired.message({
      type: 'ERROR',
      error: { code: 'INVITE_EXPIRED', domain_code: null },
    });
    expect(service.status()).toBe('expired');
    vi.runAllTimers();
    expect(FakeWebSocket.instances).toHaveLength(1);

    service.connect('ABC123', 'secret');
    const invalid = FakeWebSocket.instances[1];
    invalid.open();
    invalid.message({
      type: 'ERROR',
      error: { code: 'INVALID_CREDENTIAL', domain_code: null },
    });
    expect(service.status()).toBe('error');

    service.connect('ABC123', 'secret');
    FakeWebSocket.instances[2].drop(4001);
    expect(service.status()).toBe('error');
    expect(service.actionError()?.code).toBe('CONNECTION_REPLACED');
  });
});
