import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter, Router } from '@angular/router';
import { GameCard, Seat } from '../core/api/game-api.models';
import { TranslationService } from '../core/i18n/translation.service';
import { PvPCredentialStore } from '../core/pvp/pvp-credential.store';
import { PvPWebSocketService } from '../core/pvp/pvp-websocket.service';
import {
  PvPConnectionNotice,
  PvPConnectionStatus,
  PvPErrorBody,
  PvPOpponentStatus,
  PvPRoomClosure,
  PvPState,
} from '../core/pvp/pvp.models';
import { PvPRoomPageComponent } from './pvp-room-page';

const card: GameCard = {
  code: '6C',
  rank: '6',
  suit: 'clubs',
  base_value: 6,
  effective_value: 6,
  is_trump: false,
};

const makeState = (overrides: Partial<PvPState> = {}): PvPState => ({
  invite_code: 'ABC123',
  match_id: 'match-one',
  room_phase: 'GAME_ACTIVE',
  version: 1,
  capacity: 2,
  joined_count: 2,
  seat_order: ['one', 'two'],
  players: [
    {
      participant_id: 'p1',
      seat: 'one',
      display_name: 'Alice with a long name',
      connected: true,
      authenticated: false,
      is_self: true,
      hand_count: 1,
      active: true,
      finished: false,
    },
    {
      participant_id: 'p2',
      seat: 'two',
      display_name: 'Bob',
      connected: true,
      authenticated: false,
      is_self: false,
      hand_count: 7,
      active: true,
      finished: false,
    },
  ],
  active_seats: ['one', 'two'],
  finished_seats: [],
  finish_groups: [],
  rematch_status: 'NONE',
  you: {
    participant_id: 'p1',
    seat: 'one',
    display_name: 'Alice with a long name',
    connected: true,
    authenticated: false,
  },
  opponent: {
    participant_id: 'p2',
    seat: 'two',
    display_name: 'Bob',
    connected: true,
    authenticated: false,
  },
  game_phase: 'bout_active',
  result: null,
  result_saved: false,
  progression_award: null,
  last_bout_summary: null,
  hand: [card],
  opponent_hand_count: 7,
  draw_pile_count: 22,
  exposed_top_card: card,
  trump: { active: true, source_card: card, trump_rank: '6', trump_suit: 'clubs' },
  discard_count: 0,
  table_cards: [],
  table_arithmetic: { total_effective_value: 0, physical_card_count: 0, arithmetic_mean: null },
  bout_starting_attacker: 'one',
  attacker: 'one',
  lead_attacker: 'one',
  defender: 'two',
  bout_phase: 'waiting_for_initial_attack',
  packets: [],
  active_packet: null,
  direct_anchor_cards: [],
  active_attack_value: null,
  attack_card_limit: 7,
  max_attack_card_addition: 7,
  total_attack_card_count: 0,
  transfer_open: true,
  required_participant_id: 'p1',
  required_seat: 'one',
  available_actions: ['INITIAL_ATTACK'],
  ...overrides,
});

const makeMultiplayerState = (
  capacity: 3 | 4,
  viewerSeat: Seat = 'one',
  overrides: Partial<PvPState> = {},
): PvPState => {
  const seatOrder = (['one', 'two', 'three', 'four'] as const).slice(0, capacity);
  const players = seatOrder.map((seat, index) => ({
    participant_id: `p${index + 1}`,
    seat,
    display_name: ['Alice', 'Bob', 'Cara', 'Dmitri'][index],
    connected: true,
    authenticated: false,
    is_self: seat === viewerSeat,
    hand_count: seat === viewerSeat ? 2 : index + 5,
    active: true,
    finished: false,
  }));
  const viewer = players.find((player) => player.seat === viewerSeat)!;
  return makeState({
    capacity,
    joined_count: capacity,
    seat_order: seatOrder,
    players,
    active_seats: seatOrder,
    you: {
      participant_id: viewer.participant_id,
      seat: viewer.seat,
      display_name: viewer.display_name,
      connected: viewer.connected,
      authenticated: viewer.authenticated,
    },
    opponent: null,
    opponent_hand_count: null,
    hand: [card, { ...card, code: '7D', rank: '7', suit: 'diamonds' }],
    attacker: 'one',
    lead_attacker: 'one',
    defender: 'two',
    required_participant_id: 'p1',
    required_seat: 'one',
    ...overrides,
  });
};

describe('PvPRoomPageComponent', () => {
  let fixture: ComponentFixture<PvPRoomPageComponent>;
  const credentials = { get: vi.fn(), clear: vi.fn() };
  const socket = {
    state: signal<PvPState | null>(makeState()),
    status: signal<PvPConnectionStatus>('connected'),
    actionError: signal<PvPErrorBody | null>(null),
    actionPending: signal(false),
    rematchPending: signal(false),
    hints: signal(null),
    hintPending: signal(false),
    opponentStatus: signal<PvPOpponentStatus>('connected'),
    connectionNotice: signal<PvPConnectionNotice>(null),
    roomClosure: signal<PvPRoomClosure>(null),
    leavePending: signal(false),
    connect: vi.fn(),
    disconnect: vi.fn(),
    sendAction: vi.fn(),
    requestHints: vi.fn(),
    clearHints: vi.fn(),
    retry: vi.fn(),
    leaveRoom: vi.fn(),
    requestRematch: vi.fn(),
    acceptRematch: vi.fn(),
    declineRematch: vi.fn(),
    cancelRematch: vi.fn(),
  };

  beforeEach(async () => {
    localStorage.removeItem('kiba.hintsEnabled');
    socket.state.set(makeState());
    socket.status.set('connected');
    socket.actionError.set(null);
    socket.actionPending.set(false);
    socket.rematchPending.set(false);
    socket.hints.set(null);
    socket.hintPending.set(false);
    socket.opponentStatus.set('connected');
    socket.connectionNotice.set(null);
    socket.roomClosure.set(null);
    socket.leavePending.set(false);
    socket.connect.mockReset();
    socket.sendAction.mockReset();
    socket.requestHints.mockReset();
    socket.clearHints.mockReset();
    socket.disconnect.mockReset();
    socket.retry.mockReset();
    socket.leaveRoom.mockReset();
    socket.requestRematch.mockReset();
    socket.acceptRematch.mockReset();
    socket.declineRematch.mockReset();
    socket.cancelRematch.mockReset();
    credentials.get.mockReset().mockReturnValue({ reconnect_token: 'secret' });
    credentials.clear.mockReset();
    await TestBed.configureTestingModule({
      imports: [PvPRoomPageComponent],
      providers: [
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ inviteCode: 'ABC123' }) } },
        },
        { provide: PvPCredentialStore, useValue: credentials },
        { provide: PvPWebSocketService, useValue: socket },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(PvPRoomPageComponent);
    fixture.detectChanges();
  });

  it('renders only the local hand and the opponent count/name', () => {
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelectorAll('app-hand .playing-card')).toHaveLength(1);
    expect(element.querySelector('.opponent-zone .seat-name')?.textContent).toBe('Bob');
    expect(element.querySelector('.opponent-zone .seat-count')?.textContent).toContain('7 карт');
    expect(element.querySelectorAll('.opponent-zone .hidden-card')).toHaveLength(7);
    expect(element.textContent).not.toContain('opponent_hand');
    expect(element.textContent).not.toContain('draw_pile');
  });

  it.each([
    [3, 'three', ['Alice', 'Bob']],
    [4, 'four', ['Alice', 'Bob', 'Cara']],
  ] as const)(
    'renders a capacity-%s room relative to every viewer without exposing remote cards',
    (capacity, viewerSeat, expectedNames) => {
      socket.state.set(makeMultiplayerState(capacity, viewerSeat));
      fixture.detectChanges();

      const element = fixture.nativeElement as HTMLElement;
      const names = [...element.querySelectorAll('.opponent-zone .seat-name')].map((node) =>
        node.textContent?.trim(),
      );
      expect(names).toEqual(expectedNames);
      expect(element.querySelectorAll('.opponent-zone app-table-seat')).toHaveLength(capacity - 1);
      expect(element.querySelector('.position-left .seat-name')?.textContent).toContain('Alice');
      expect(element.querySelector('.position-top .seat-name')?.textContent).toContain('Bob');
      expect(element.querySelector('.local-player-name')?.textContent).toContain(
        viewerSeat === 'three' ? 'Cara' : 'Dmitri',
      );
      expect(element.querySelector('app-hint-panel')).toBeNull();
      expect(element.innerHTML).not.toContain('reconnect_token');
    },
  );

  it('uses the authoritative BITO action as a multiplayer attacker phase Pass', () => {
    socket.state.set(makeMultiplayerState(4, 'one', { available_actions: ['BITO'] }));
    fixture.detectChanges();

    const pass = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Пас',
    ) as HTMLButtonElement;
    expect(pass).toBeDefined();
    pass.click();
    expect(socket.sendAction).toHaveBeenCalledWith('BITO', []);
  });

  it('keeps stable seats while transfer changes defender and attacker roles', () => {
    socket.state.set(makeMultiplayerState(4));
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('.position-left .seat-name')?.textContent).toContain('Bob');
    expect(element.querySelector('.position-left .seat-roles')?.textContent).toContain('Защитник');

    socket.state.set(
      makeMultiplayerState(4, 'one', {
        version: 2,
        attacker: 'two',
        lead_attacker: 'two',
        defender: 'three',
        required_participant_id: 'p3',
        required_seat: 'three',
        available_actions: [],
      }),
    );
    fixture.detectChanges();

    expect(element.querySelector('.position-left .seat-name')?.textContent).toContain('Bob');
    expect(element.querySelector('.position-top .seat-name')?.textContent).toContain('Cara');
    expect(element.querySelector('.position-top .seat-roles')?.textContent).toContain('Защитник');
  });

  it('does not reactivate a closed attacker phase after a later attacker changes the table', () => {
    const closed = makeMultiplayerState(4, 'one', {
      attacker: 'three',
      required_participant_id: 'p3',
      required_seat: 'three',
      available_actions: [],
    });
    socket.state.set(closed);
    fixture.detectChanges();
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('app-action-bar button'),
    ).toBeNull();

    socket.state.set({
      ...closed,
      version: 2,
      table_cards: [card],
      total_attack_card_count: 1,
    });
    fixture.detectChanges();

    expect(
      (fixture.nativeElement as HTMLElement).querySelector('app-action-bar button'),
    ).toBeNull();
    expect((fixture.nativeElement as HTMLElement).querySelector('app-game-table')).not.toBeNull();
  });

  it('renders multiple disconnected participants independently and pauses local controls', () => {
    const state = makeMultiplayerState(4);
    socket.state.set({
      ...state,
      players: state.players.map((player) =>
        player.seat === 'two' || player.seat === 'four' ? { ...player, connected: false } : player,
      ),
      available_actions: ['INITIAL_ATTACK'],
    });
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelectorAll('.opponent-zone .is-disconnected')).toHaveLength(2);
    expect(element.textContent).toContain('Один из игроков отключился');
    expect(element.querySelector<HTMLButtonElement>('app-action-bar button')?.disabled).toBe(true);
  });

  it('keeps finished players seated through 4→3→2 active reduction', () => {
    const state = makeMultiplayerState(4);
    socket.state.set({
      ...state,
      version: 2,
      active_seats: ['three', 'four'],
      finished_seats: ['one', 'two'],
      finish_groups: [['one'], ['two']],
      players: state.players.map((player) =>
        player.seat === 'one' || player.seat === 'two'
          ? { ...player, active: false, finished: true, hand_count: 0 }
          : player,
      ),
      available_actions: [],
      required_participant_id: 'p3',
      required_seat: 'three',
    });
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelectorAll('.opponent-zone app-table-seat')).toHaveLength(3);
    expect(element.querySelector('.position-left')?.classList).toContain('is-finished');
    expect(element.querySelector('.local-player-row')?.classList).toContain('is-finished');
    expect(element.querySelector('.local-player-name')?.textContent).toContain('Alice');
    expect(element.textContent).toContain('Вы финишировали — партия продолжается');
    expect(element.querySelector('app-action-bar button')).toBeNull();
  });

  it('renders multiplayer competition placements, no fake loser, and rematch', () => {
    socket.state.set(
      makeMultiplayerState(4, 'one', {
        room_phase: 'COMPLETE',
        game_phase: 'complete',
        finish_groups: [['one', 'two'], ['three'], ['four']],
        active_seats: [],
        finished_seats: ['one', 'two', 'three', 'four'],
        available_actions: [],
        required_participant_id: null,
        required_seat: null,
      }),
    );
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('.finish-groups')?.textContent).toContain('1-е место');
    expect(element.querySelectorAll('.finish-groups li')[0].textContent).toContain('Alice');
    expect(element.querySelectorAll('.finish-groups li')[1].textContent).toContain('Bob');
    expect(element.querySelector('.finish-groups')?.textContent).toContain('3-е место');
    expect(element.querySelector('.finish-groups')?.textContent).toContain('4-е место');
    expect(element.querySelector('.finish-groups')?.textContent).toContain('Cara');
    expect(element.querySelector('.finish-groups')?.textContent).toContain('Dmitri');
    expect(element.querySelector('.rematch-button')).not.toBeNull();
    expect(element.textContent).not.toContain('проиграл');
    expect(element.textContent).toContain('Матчи на 3–4 игроков пока не влияют');
    expect(element.querySelector('app-hint-panel')).toBeNull();
  });

  it('shows multiplayer unanimous rematch progress and participant responses', () => {
    socket.state.set(
      makeMultiplayerState(4, 'one', {
        room_phase: 'COMPLETE',
        game_phase: 'complete',
        finish_groups: [['one'], ['two', 'three'], ['four']],
        active_seats: [],
        finished_seats: ['one', 'two', 'three', 'four'],
        available_actions: [],
        required_participant_id: null,
        required_seat: null,
        rematch_status: 'WAITING',
        rematch_ready_count: 2,
        rematch_total_count: 4,
        rematch_requester_participant_id: 'p1',
        rematch_ready_participant_ids: ['p1', 'p3'],
      }),
    );
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Готовы: 2 / 4');
    expect(element.textContent).toContain('Ждём согласия всех игроков');
    expect(element.querySelector('.rematch-participants')?.textContent).toContain('Alice');
    expect(element.querySelector('.rematch-participants')?.textContent).toContain('готов');
    expect(element.querySelector('.rematch-participants')?.textContent).toContain('Bob');
    expect(element.querySelector('.rematch-participants')?.textContent).toContain('ожидает');
    element.querySelector<HTMLButtonElement>('.rematch-button')?.click();
    expect(socket.cancelRematch).toHaveBeenCalledOnce();
  });

  it('renders a pre-start multiplayer room and releases a departed participant slot', () => {
    const waiting = makeMultiplayerState(4, 'one', {
      room_phase: 'WAITING_FOR_OPPONENT',
      game_phase: null,
      joined_count: 2,
      players: makeMultiplayerState(4).players.slice(0, 2),
      available_actions: [],
      required_participant_id: null,
      required_seat: null,
    });
    socket.state.set(waiting);
    fixture.detectChanges();
    let element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('2 / 4 игроков');
    expect(element.textContent).toContain('Ждём ещё игроков: 2');
    expect(element.textContent).toContain('Матчи на 3–4 игроков пока не влияют');
    expect(element.querySelectorAll('.waiting-participants li')).toHaveLength(2);

    socket.state.set({ ...waiting, version: 2, joined_count: 1, players: [waiting.players[0]] });
    fixture.detectChanges();
    element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('1 / 4 игроков');
    expect(element.querySelectorAll('.waiting-participants li')).toHaveLength(1);
  });

  it('does not start a full client room until the backend phase becomes active', () => {
    const waiting = makeMultiplayerState(3, 'one', {
      room_phase: 'WAITING_FOR_OPPONENT',
      game_phase: null,
      available_actions: [],
      required_participant_id: null,
      required_seat: null,
    });
    socket.state.set(waiting);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('3 / 3 игроков');
    expect((fixture.nativeElement as HTMLElement).querySelector('app-game-table')).toBeNull();

    socket.state.set(makeMultiplayerState(3, 'one', { version: 2 }));
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('app-game-table')).not.toBeNull();
  });

  it('renders active multiplayer Exit as a neutral room end', () => {
    socket.state.set(
      makeMultiplayerState(3, 'one', {
        room_phase: 'CLOSED',
        version: 2,
        available_actions: [],
      }),
    );
    socket.roomClosure.set('opponent_left');
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('Комната закрыта');
    expect(text).toContain('Результат партии не засчитан');
    expect(text).not.toContain('Победил');
  });

  it('shows the presentation-only activity perimeter only for the local actor', () => {
    let element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('app-turn-reminder')).not.toBeNull();

    socket.state.set(
      makeState({
        version: 2,
        required_participant_id: 'p2',
        required_seat: 'two',
        available_actions: [],
      }),
    );
    fixture.detectChanges();

    element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('app-turn-reminder')).toBeNull();
    expect(socket.sendAction).not.toHaveBeenCalled();
  });

  it('renders the latest bout summary from the local participant perspective', () => {
    socket.state.set(
      makeState({
        last_bout_summary: { outcome: 'TAKE', actor_seat: 'two', table_card_count: 5 },
      }),
    );
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Последний кон');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Bob взял(а) 5 карт');
  });

  it('resumes the same room from the stored reconnect credential', () => {
    expect(socket.connect).toHaveBeenCalledWith('ABC123', 'secret');
    expect(credentials.get).toHaveBeenCalledWith('ABC123');
  });

  it('sends selected card codes through the WebSocket without optimistic table changes', () => {
    const cardButton = (fixture.nativeElement as HTMLElement).querySelector(
      'app-hand .playing-card',
    ) as HTMLButtonElement;
    cardButton.click();
    fixture.detectChanges();
    expect(socket.requestHints).toHaveBeenCalledWith(['6C']);
    const action = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Ходить',
    ) as HTMLButtonElement;
    action.click();
    fixture.detectChanges();
    expect(socket.sendAction).toHaveBeenCalledWith('INITIAL_ATTACK', ['6C']);
    expect(socket.state()?.packets).toHaveLength(0);
    expect(cardButton.getAttribute('aria-pressed')).toBe('true');
  });

  it('does not request hints when the preference is off', () => {
    (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLButtonElement>('.hint-toggle')!
      .click();
    fixture.detectChanges();
    socket.requestHints.mockClear();
    socket.clearHints.mockClear();

    (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLButtonElement>('app-hand .playing-card')!
      .click();
    fixture.detectChanges();

    expect(socket.requestHints).not.toHaveBeenCalled();
    expect(socket.clearHints).toHaveBeenCalled();
  });

  it('animates an observed remote public card and closes the facedown hand gap', () => {
    socket.state.set(
      makeState({
        version: 2,
        opponent_hand_count: 6,
        players: makeState().players.map((player) =>
          player.seat === 'two' ? { ...player, hand_count: 6 } : player,
        ),
        table_cards: [card],
        required_participant_id: 'p1',
      }),
    );
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelectorAll('.opponent-zone .hidden-card')).toHaveLength(6);
    expect(element.querySelectorAll('.motion-card.from-top.to-table')).toHaveLength(1);
    expect(element.querySelector('.motion-layer')?.getAttribute('aria-hidden')).toBe('true');
  });

  it('sends TAKE without stale selected card codes', () => {
    socket.state.set(makeState({ available_actions: ['TAKE'] }));
    fixture.detectChanges();
    const cardButton = (fixture.nativeElement as HTMLElement).querySelector(
      'app-hand .playing-card',
    ) as HTMLButtonElement;
    cardButton.click();
    fixture.detectChanges();
    const action = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Взять',
    ) as HTMLButtonElement;
    action.click();
    expect(socket.sendAction).toHaveBeenCalledWith('TAKE', []);
  });

  it('shows a current-origin invite and copies it without exposing the credential', async () => {
    socket.state.set(
      makeState({
        room_phase: 'WAITING_FOR_OPPONENT',
        joined_count: 1,
        players: [makeState().players[0]],
        opponent: null,
        opponent_hand_count: null,
        game_phase: null,
        available_actions: [],
      }),
    );
    fixture.detectChanges();
    const writeText = vi.fn().mockResolvedValue(undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    try {
      const element = fixture.nativeElement as HTMLElement;
      expect(element.textContent).toContain('1 / 2 игроков');
      expect(element.querySelector('output')?.textContent).toBe(
        `${window.location.origin}/join/ABC123`,
      );
      const copy = [...element.querySelectorAll('button')].find((button) =>
        button.textContent?.includes('Скопировать'),
      ) as HTMLButtonElement;
      copy.click();
      await fixture.whenStable();
      fixture.detectChanges();
      expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/join/ABC123`);
      expect(element.textContent).toContain('Ссылка скопирована');
      expect(element.textContent).not.toContain('secret');
    } finally {
      if (originalClipboard === undefined) Reflect.deleteProperty(navigator, 'clipboard');
      else Object.defineProperty(navigator, 'clipboard', originalClipboard);
    }
  });

  it('shows disconnect state without declaring a forfeit', () => {
    socket.state.set(makeState({ available_actions: ['TAKE'] }));
    socket.opponentStatus.set('disconnected');
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Соперник отключился');
    expect(element.textContent).not.toContain('победили');
    expect(element.querySelector('app-turn-reminder')).toBeNull();
    expect(element.querySelector<HTMLButtonElement>('app-hand .playing-card')?.disabled).toBe(true);
    expect(element.querySelector<HTMLButtonElement>('app-action-bar button')?.disabled).toBe(true);

    element.querySelector<HTMLButtonElement>('app-action-bar button')?.click();
    expect(socket.sendAction).not.toHaveBeenCalled();
  });

  it('starts a fresh reminder cycle when the opponent returns to the same decision', () => {
    socket.opponentStatus.set('disconnected');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('app-turn-reminder')).toBeNull();

    socket.opponentStatus.set('connected');
    socket.state.set(makeState({ version: 1 }));
    fixture.detectChanges();

    expect(
      (fixture.nativeElement as HTMLElement).querySelector('app-turn-reminder'),
    ).not.toBeNull();
    expect(socket.sendAction).not.toHaveBeenCalled();
  });

  it('keeps invite copy fallback usable when clipboard access is unavailable', async () => {
    socket.state.set(
      makeState({
        room_phase: 'WAITING_FOR_OPPONENT',
        joined_count: 1,
        players: [makeState().players[0]],
        opponent: null,
        opponent_hand_count: null,
        game_phase: null,
        available_actions: [],
      }),
    );
    fixture.detectChanges();
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined });
    try {
      const copy = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
        (button) => button.textContent?.includes('Скопировать'),
      ) as HTMLButtonElement;
      copy.click();
      await fixture.whenStable();
      fixture.detectChanges();
      expect((fixture.nativeElement as HTMLElement).textContent).toContain('Выделите ссылку выше');
    } finally {
      if (originalClipboard === undefined) Reflect.deleteProperty(navigator, 'clipboard');
      else Object.defineProperty(navigator, 'clipboard', originalClipboard);
    }
  });

  it('clears an invalid reconnect credential and returns to the join flow', async () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    socket.actionError.set({ code: 'INVALID_CREDENTIAL', domain_code: null });
    fixture.detectChanges();

    expect(credentials.clear).toHaveBeenCalledWith('ABC123');
    expect(socket.disconnect).toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith(['/join', 'ABC123']);
  });

  it('preserves the table while reconnecting and disables gameplay controls', () => {
    socket.status.set('reconnecting');
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Переподключение');
    expect(element.querySelector('app-game-table')).not.toBeNull();
    expect(element.querySelector<HTMLButtonElement>('app-hand .playing-card')?.disabled).toBe(true);
    expect(element.querySelector<HTMLButtonElement>('app-action-bar button')?.disabled).toBe(true);
  });

  it('offers manual retry after bounded reconnect attempts are exhausted', () => {
    socket.status.set('disconnected');
    fixture.detectChanges();
    const retry = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Повторить',
    ) as HTMLButtonElement;
    retry.click();
    expect(socket.retry).toHaveBeenCalledOnce();
  });

  it('shows recovered and stale-state notices without changing the table locally', () => {
    socket.connectionNotice.set('state_updated');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Состояние игры обновилось',
    );
    expect(socket.state()?.packets).toHaveLength(0);
  });

  it('shows an expired-room terminal view and clears its stored credential', () => {
    socket.status.set('expired');
    socket.actionError.set({ code: 'INVITE_EXPIRED', domain_code: null });
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Комната больше недоступна');
    expect(element.textContent).toContain('Создать новую комнату');
    expect(element.textContent).toContain('Играть с ботом');
    expect(credentials.clear).toHaveBeenCalledWith('ABC123');
  });

  it('explicit leave waits for server confirmation before clearing resume state', () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const leave = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Выйти',
    ) as HTMLButtonElement;
    leave.click();
    fixture.detectChanges();
    const confirm = [
      ...(fixture.nativeElement as HTMLElement).querySelectorAll('.restart-confirmation button'),
    ].find((button) => button.textContent?.trim() === 'Выйти') as HTMLButtonElement;
    confirm.click();
    expect(socket.leaveRoom).toHaveBeenCalledOnce();
    expect(credentials.clear).not.toHaveBeenCalledWith('ABC123');
    expect(navigate).not.toHaveBeenCalledWith(['/pvp']);

    socket.state.set(makeState({ room_phase: 'CLOSED', version: 2, available_actions: [] }));
    socket.roomClosure.set('you_left');
    fixture.detectChanges();
    expect(credentials.clear).toHaveBeenCalledWith('ABC123');
    expect(navigate).toHaveBeenCalledWith(['/pvp']);
  });

  it('keeps the exit dialog keyboard-modal and cancel preserves the room', async () => {
    const trigger = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Выйти',
    ) as HTMLButtonElement;
    trigger.focus();
    trigger.click();
    fixture.detectChanges();
    await Promise.resolve();

    const dialog = (fixture.nativeElement as HTMLElement).querySelector(
      '[role="alertdialog"]',
    ) as HTMLElement;
    const buttons = dialog.querySelectorAll('button');
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(document.activeElement).toBe(buttons[0]);
    buttons[0].dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }),
    );
    expect(document.activeElement).toBe(buttons[1]);
    buttons[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(document.activeElement).toBe(buttons[0]);
    dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    fixture.detectChanges();
    await Promise.resolve();

    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alertdialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(socket.leaveRoom).not.toHaveBeenCalled();
    expect(credentials.clear).not.toHaveBeenCalledWith('ABC123');
  });

  it('shows a terminal opponent-left state without actions, timer, or reconnect promise', () => {
    socket.state.set(makeState({ room_phase: 'CLOSED', version: 2, available_actions: [] }));
    socket.roomClosure.set('opponent_left');
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Соперник вышел из игры');
    expect(element.textContent).toContain('Результат партии не засчитан');
    expect(element.textContent).toContain('Вернуться в PvP');
    expect(element.textContent).not.toContain('ждать вашего переподключения');
    expect(element.querySelector('app-action-bar')).toBeNull();
    expect(element.querySelector('app-turn-reminder')).toBeNull();
    expect(credentials.clear).toHaveBeenCalledWith('ABC123');
  });

  it.each([
    [{ outcome: 'WIN', winner_participant_id: 'p1', winner_display_name: 'Alice' }, 'Вы победили'],
    [{ outcome: 'WIN', winner_participant_id: 'p2', winner_display_name: 'Bob' }, 'Победил Bob'],
    [{ outcome: 'DRAW', winner_participant_id: null, winner_display_name: null }, 'Ничья'],
  ] as const)('renders participant-relative completion', (result, expected) => {
    socket.state.set(
      makeState({
        room_phase: 'COMPLETE',
        game_phase: 'complete',
        result: { winner_seat: null, ...result },
      }),
    );
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(expected);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Создайте аккаунт');
  });

  it('offers rematch as the primary result action and sends a request', () => {
    socket.state.set(
      makeState({
        room_phase: 'COMPLETE',
        game_phase: 'complete',
        result: {
          outcome: 'DRAW',
          winner_seat: null,
          winner_participant_id: null,
          winner_display_name: null,
        },
      }),
    );
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    const rematch = [...element.querySelectorAll<HTMLButtonElement>('.rematch-button')].find(
      (button) => button.textContent?.trim() === 'Сыграть ещё',
    );

    expect(rematch).toBeDefined();
    expect(element.querySelector('.rematch-actions > .room-again')?.textContent).toContain(
      'Создать новую комнату',
    );
    rematch?.click();
    expect(socket.requestRematch).toHaveBeenCalledOnce();
  });

  it('does not show rematch controls during active PvP', () => {
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('.rematch-actions')).toBeNull();
    expect(
      [...element.querySelectorAll('button')].some(
        (button) => button.textContent?.trim() === 'Сыграть ещё',
      ),
    ).toBe(false);
  });

  it('renders waiting, incoming, and declined rematch states with their actions', () => {
    const completed = {
      room_phase: 'COMPLETE' as const,
      game_phase: 'complete' as const,
      result: {
        outcome: 'DRAW' as const,
        winner_seat: null,
        winner_participant_id: null,
        winner_display_name: null,
      },
    };
    socket.state.set(
      makeState({
        ...completed,
        rematch_status: 'WAITING',
        rematch_requester_participant_id: 'p1',
      }),
    );
    fixture.detectChanges();
    let element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Ждём ответа соперника');
    element.querySelector<HTMLButtonElement>('.rematch-button')?.click();
    expect(socket.cancelRematch).toHaveBeenCalledOnce();

    socket.state.set(makeState({ ...completed, version: 3, rematch_status: 'INCOMING' }));
    fixture.detectChanges();
    element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('#rematch-incoming-title')?.textContent).toContain(
      'Соперник хочет реванш',
    );
    const incomingButtons = element.querySelectorAll<HTMLButtonElement>('.rematch-button');
    incomingButtons[0].click();
    incomingButtons[1].click();
    expect(socket.acceptRematch).toHaveBeenCalledOnce();
    expect(socket.declineRematch).toHaveBeenCalledOnce();

    socket.state.set(makeState({ ...completed, version: 4, rematch_status: 'DECLINED' }));
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Соперник отказался от повторной партии',
    );
  });

  it('switches rematch copy at runtime without changing rematch state', () => {
    const completed = makeState({
      room_phase: 'COMPLETE',
      game_phase: 'complete',
      rematch_status: 'INCOMING',
      result: {
        outcome: 'DRAW',
        winner_seat: null,
        winner_participant_id: null,
        winner_display_name: null,
      },
    });
    socket.state.set(completed);
    const i18n = TestBed.inject(TranslationService);
    i18n.setLocale('en');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Opponent wants a rematch',
    );

    i18n.setLocale('ru');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Соперник хочет реванш');
    expect(socket.state()).toBe(completed);
  });

  it('clears old presentation motion and shows a short rematch transition', () => {
    vi.useFakeTimers();
    socket.state.set(
      makeState({
        room_phase: 'COMPLETE',
        game_phase: 'complete',
        version: 7,
        result: {
          outcome: 'DRAW',
          winner_seat: null,
          winner_participant_id: null,
          winner_display_name: null,
        },
      }),
    );
    fixture.detectChanges();
    socket.state.set(makeState({ version: 8, match_id: 'match-two' }));
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Начинаем новую партию');
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.rematch-starting'),
    ).not.toBeNull();
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('Соперник отключился');
    vi.advanceTimersByTime(650);
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('.rematch-starting')).toBeNull();
    expect(element.querySelector('.result-panel')).toBeNull();
    expect(element.querySelector('app-game-table')).not.toBeNull();
    vi.useRealTimers();
  });

  it('still surfaces a real opponent disconnect during the rematch transition', () => {
    vi.useFakeTimers();
    socket.state.set(
      makeState({
        room_phase: 'COMPLETE',
        game_phase: 'complete',
        version: 7,
        result: {
          outcome: 'DRAW',
          winner_seat: null,
          winner_participant_id: null,
          winner_display_name: null,
        },
      }),
    );
    fixture.detectChanges();
    socket.state.set(makeState({ version: 8, match_id: 'match-two' }));
    socket.opponentStatus.set('disconnected');
    fixture.detectChanges();

    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.connection-banner')?.textContent,
    ).toContain('Соперник отключился');
    vi.useRealTimers();
  });

  it('preserves the local Hint preference and clears selected cards across rematch', () => {
    const hintToggle = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      '.hint-toggle',
    )!;
    hintToggle.click();
    const cardButton = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      'app-hand .playing-card',
    )!;
    cardButton.click();
    fixture.detectChanges();
    expect(hintToggle.getAttribute('aria-checked')).toBe('false');
    expect(cardButton.getAttribute('aria-pressed')).toBe('true');

    socket.state.set(
      makeState({
        room_phase: 'COMPLETE',
        game_phase: 'complete',
        version: 7,
        result: {
          outcome: 'DRAW',
          winner_seat: null,
          winner_participant_id: null,
          winner_display_name: null,
        },
      }),
    );
    fixture.detectChanges();
    socket.state.set(makeState({ version: 8, match_id: 'match-two' }));
    fixture.detectChanges();

    expect(
      (fixture.nativeElement as HTMLElement)
        .querySelector<HTMLButtonElement>('.hint-toggle')
        ?.getAttribute('aria-checked'),
    ).toBe('false');
    expect(
      (fixture.nativeElement as HTMLElement)
        .querySelector<HTMLButtonElement>('app-hand .playing-card')
        ?.getAttribute('aria-pressed'),
    ).toBe('false');
  });

  it('waits for server confirmation when exiting a completed room', () => {
    socket.state.set(
      makeState({
        room_phase: 'COMPLETE',
        game_phase: 'complete',
        result: {
          outcome: 'DRAW',
          winner_seat: null,
          winner_participant_id: null,
          winner_display_name: null,
        },
      }),
    );
    fixture.detectChanges();
    const exit = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Выйти',
    ) as HTMLButtonElement;
    exit.click();
    fixture.detectChanges();
    const confirm = [
      ...(fixture.nativeElement as HTMLElement).querySelectorAll('.restart-confirmation button'),
    ].find((button) => button.textContent?.trim() === 'Выйти') as HTMLButtonElement;
    confirm.click();

    expect(socket.leaveRoom).toHaveBeenCalledOnce();
    expect(credentials.clear).not.toHaveBeenCalledWith('ABC123');
  });

  it('renders only the authenticated local participant progression on completion', () => {
    socket.state.set(
      makeState({
        room_phase: 'COMPLETE',
        game_phase: 'complete',
        you: { ...makeState().you, authenticated: true },
        result: {
          outcome: 'WIN',
          winner_seat: 'one',
          winner_participant_id: 'p1',
          winner_display_name: 'Alice',
        },
        result_saved: true,
        progression_award: {
          base_xp: 100,
          achievement_bonus_xp: 25,
          total_awarded_xp: 125,
          total_xp: 125,
          level: 1,
          next_level_xp: 200,
          xp_needed_for_next_level: 75,
          new_achievements: [
            {
              code: 'FIRST_WIN',
              title: 'Первая победа',
              description: 'Победите впервые.',
              bonus_xp: 25,
            },
          ],
          new_cosmetics: [{ code: 'WINNER_FRAME', category: 'PROFILE_FRAME', title: 'Победитель' }],
        },
      }),
    );
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent;

    expect(text).toContain('+125 XP');
    expect(text).toContain('Результат сохранён');
    expect(text).toContain('Первая победа');
    expect(text).toContain('Победитель');
    expect(text).not.toContain('Создайте аккаунт');
    expect(
      (fixture.nativeElement as HTMLElement).querySelectorAll('.result-links .result-history-link'),
    ).toHaveLength(2);
  });
});
