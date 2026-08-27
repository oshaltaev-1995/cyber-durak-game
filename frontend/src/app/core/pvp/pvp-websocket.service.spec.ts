import { TestBed } from '@angular/core/testing';
import { PvPWebSocketService } from './pvp-websocket.service';
import { PvPState } from './pvp.models';

class FakeWebSocket extends EventTarget {
  static readonly OPEN = 1;
  static instances: FakeWebSocket[] = [];
  readonly url: string;
  readyState = FakeWebSocket.OPEN;
  readonly sent: string[] = [];

  constructor(url: string | URL) {
    super();
    this.url = String(url);
    FakeWebSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }
  close(): void {
    this.readyState = 3;
  }
  open(): void {
    this.dispatchEvent(new Event('open'));
  }
  message(value: unknown): void {
    this.dispatchEvent(new MessageEvent('message', { data: JSON.stringify(value) }));
  }
  drop(): void {
    this.dispatchEvent(new CloseEvent('close'));
  }
}

const state = (version: number): PvPState =>
  ({ invite_code: 'ABC123', version, opponent: null }) as unknown as PvPState;

describe('PvPWebSocketService', () => {
  let service: PvPWebSocketService;

  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
    TestBed.configureTestingModule({});
    service = TestBed.inject(PvPWebSocketService);
  });

  afterEach(() => {
    service.disconnect();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('uses the current origin, authenticates first, and sends a versioned action', () => {
    service.connect('ABC123', 'secret', state(4));
    const socket = FakeWebSocket.instances[0];
    expect(socket.url).toContain('/api/pvp/rooms/ABC123/ws');
    expect(socket.url).not.toContain('secret');
    socket.open();
    expect(JSON.parse(socket.sent[0])).toEqual({ type: 'AUTH', credential: 'secret' });

    service.sendAction('DEFEND', ['QS']);
    expect(JSON.parse(socket.sent[1])).toEqual({
      type: 'ACTION',
      version: 4,
      action: 'DEFEND',
      cards: ['QS'],
    });
  });

  it('ignores older states and accepts authoritative newer state', () => {
    service.connect('ABC123', 'secret', state(3));
    const socket = FakeWebSocket.instances[0];
    socket.message({ type: 'STATE', state: state(2) });
    expect(service.state()?.version).toBe(3);
    socket.message({ type: 'STATE', state: state(5) });
    expect(service.state()?.version).toBe(5);
  });

  it('keeps state on rejection and reports opponent connectivity', () => {
    service.connect('ABC123', 'secret', state(1));
    const socket = FakeWebSocket.instances[0];
    socket.message({
      type: 'ACTION_REJECTED',
      error: { code: 'ILLEGAL_ACTION', domain_code: 'illegal_defense' },
    });
    expect(service.state()?.version).toBe(1);
    expect(service.actionError()?.domain_code).toBe('illegal_defense');
    socket.message({ type: 'OPPONENT_DISCONNECTED', version: 1 });
    expect(service.opponentDisconnected()).toBe(true);
    socket.message({ type: 'OPPONENT_CONNECTED', version: 1 });
    expect(service.opponentDisconnected()).toBe(false);
  });

  it('reconnects with the same ephemeral credential after an unexpected close', () => {
    vi.useFakeTimers();
    service.connect('ABC123', 'secret');
    FakeWebSocket.instances[0].drop();
    expect(service.status()).toBe('reconnecting');
    vi.advanceTimersByTime(800);
    expect(FakeWebSocket.instances).toHaveLength(2);
    FakeWebSocket.instances[1].open();
    expect(JSON.parse(FakeWebSocket.instances[1].sent[0])).toEqual({
      type: 'AUTH',
      credential: 'secret',
    });
  });
});
