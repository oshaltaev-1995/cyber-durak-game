import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter, Router } from '@angular/router';
import { GameCard } from '../core/api/game-api.models';
import { PvPCredentialStore } from '../core/pvp/pvp-credential.store';
import { PvPWebSocketService } from '../core/pvp/pvp-websocket.service';
import { PvPErrorBody, PvPState } from '../core/pvp/pvp.models';
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
  room_phase: 'GAME_ACTIVE',
  version: 1,
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
  hand: [card],
  opponent_hand_count: 7,
  draw_pile_count: 22,
  exposed_top_card: card,
  trump: { active: true, source_card: card, trump_rank: '6', trump_suit: 'clubs' },
  discard_count: 0,
  table_cards: [],
  table_arithmetic: { total_effective_value: 0, physical_card_count: 0, arithmetic_mean: null },
  attacker: 'one',
  defender: 'two',
  bout_phase: 'waiting_for_initial_attack',
  packets: [],
  active_packet: null,
  direct_anchor_cards: [],
  active_attack_value: null,
  attack_card_limit: 7,
  total_attack_card_count: 0,
  transfer_open: true,
  required_participant_id: 'p1',
  required_seat: 'one',
  available_actions: ['INITIAL_ATTACK'],
  ...overrides,
});

describe('PvPRoomPageComponent', () => {
  let fixture: ComponentFixture<PvPRoomPageComponent>;
  const credentials = { get: vi.fn(), clear: vi.fn() };
  const socket = {
    state: signal<PvPState | null>(makeState()),
    status: signal<'connected'>('connected'),
    actionError: signal<PvPErrorBody | null>(null),
    actionPending: signal(false),
    opponentDisconnected: signal(false),
    connect: vi.fn(),
    disconnect: vi.fn(),
    sendAction: vi.fn(),
  };

  beforeEach(async () => {
    socket.state.set(makeState());
    socket.actionError.set(null);
    socket.sendAction.mockReset();
    socket.disconnect.mockReset();
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
    expect(element.textContent).toContain('Bob · 7 карт');
    expect(element.textContent).not.toContain('opponent_hand');
    expect(element.textContent).not.toContain('draw_pile');
  });

  it('sends selected card codes through the WebSocket without optimistic table changes', () => {
    const cardButton = (fixture.nativeElement as HTMLElement).querySelector(
      'app-hand .playing-card',
    ) as HTMLButtonElement;
    cardButton.click();
    fixture.detectChanges();
    const action = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Ходить',
    ) as HTMLButtonElement;
    action.click();
    fixture.detectChanges();
    expect(socket.sendAction).toHaveBeenCalledWith('INITIAL_ATTACK', ['6C']);
    expect(socket.state()?.packets).toHaveLength(0);
    expect(cardButton.getAttribute('aria-pressed')).toBe('true');
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
      expect(element.textContent).toContain('Ждём второго игрока');
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
    socket.opponentDisconnected.set(true);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Соперник отключился');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('победили');
  });

  it('clears an invalid reconnect credential and returns to the join flow', async () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    socket.actionError.set({ code: 'INVALID_CREDENTIAL', domain_code: null });
    fixture.detectChanges();

    expect(credentials.clear).toHaveBeenCalledWith('ABC123');
    expect(socket.disconnect).toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith(['/join', 'ABC123']);
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
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('не сохраняются');
  });
});
