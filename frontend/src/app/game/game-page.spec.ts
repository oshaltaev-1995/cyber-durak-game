import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Observable, of, Subject, throwError } from 'rxjs';
import {
  BotPresentationState,
  DeckConfig,
  GameCard,
  GameResponse,
  HintResponse,
} from '../core/api/game-api.models';
import { GameApiService } from '../core/api/game-api.service';
import { AuthService } from '../core/auth/auth.service';
import { TranslationService } from '../core/i18n/translation.service';
import { GamePageComponent } from './game-page';
import { GameSessionState } from './game-session-state';

const card = (
  code: string,
  rank: string,
  suit: GameCard['suit'],
  value: number,
  isTrump = false,
): GameCard => ({
  code,
  rank,
  suit,
  base_value: isTrump ? value / 2 : value,
  effective_value: value,
  is_trump: isTrump,
});

const sixClubs = card('6C', '6', 'clubs', 6);
const queenDiamonds = card('QD', 'Q', 'diamonds', 15);
const sevenHearts = card('7H', '7', 'hearts', 14, true);

const makeGame = (overrides: Partial<GameResponse> = {}): GameResponse => ({
  game_id: 'game-1',
  account_associated: false,
  result_saved: false,
  progression_award: null,
  cosmetics: {
    card_back_code: 'CLASSIC',
    table_theme_code: 'CLASSIC_TABLE',
    profile_frame_code: 'NO_FRAME',
  },
  recent_events: [],
  last_bout_summary: null,
  phase: 'bout_active',
  result: null,
  human_seat: 'one',
  bot_seat: 'two',
  total_players: 2,
  deck_profile: 'classic',
  deck_count: 1,
  participants: [
    {
      participant_id: 'human',
      seat: 'one',
      display_name: 'Player',
      is_bot: false,
      active: true,
      finished: false,
      hand_count: 3,
    },
    {
      participant_id: 'bot',
      seat: 'two',
      display_name: 'БОТ',
      is_bot: true,
      active: true,
      finished: false,
      hand_count: 6,
    },
  ],
  active_seats: ['one', 'two'],
  finished_seats: [],
  finish_groups: [],
  human_hand: [sixClubs, queenDiamonds, sevenHearts],
  bot_hand_count: 6,
  draw_pile_count: 21,
  exposed_top_card: sevenHearts,
  trump: {
    active: true,
    source_card: sevenHearts,
    trump_rank: '7',
    trump_suit: 'hearts',
  },
  discard_count: 0,
  table_cards: [],
  table_arithmetic: {
    total_effective_value: 0,
    physical_card_count: 0,
    arithmetic_mean: null,
  },
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
  required_actor: 'HUMAN',
  required_seat: 'one',
  available_actions: ['INITIAL_ATTACK'],
  ...overrides,
});

const makeMultiplayerGame = (
  totalPlayers: 3 | 4,
  overrides: Partial<GameResponse> = {},
): GameResponse => {
  const seats = ['one', 'two', 'three', 'four'] as const;
  const names = ['You', 'Milo', 'Nika', 'Otto'];
  return makeGame({
    total_players: totalPlayers,
    participants: seats.slice(0, totalPlayers).map((seat, index) => ({
      participant_id: index === 0 ? 'human' : `bot-${index}`,
      seat,
      display_name: names[index],
      is_bot: index > 0,
      active: true,
      finished: false,
      hand_count: index === 0 ? 3 : 7,
    })),
    active_seats: seats.slice(0, totalPlayers),
    finished_seats: [],
    finish_groups: [],
    bot_hand_count: 7,
    ...overrides,
  });
};

const presentationState = (
  game: GameResponse,
  overrides: Partial<BotPresentationState> = {},
): BotPresentationState => ({
  phase: game.phase,
  viewer_hand: game.human_hand,
  hand_counts: Object.fromEntries(
    game.participants.map((participant) => [participant.seat, participant.hand_count]),
  ) as Partial<Record<'one' | 'two' | 'three' | 'four', number>>,
  draw_pile_count: game.draw_pile_count,
  discard_count: game.discard_count,
  exposed_top_card: game.exposed_top_card,
  trump: game.trump,
  active_seats: game.active_seats,
  finished_seats: game.finished_seats,
  finish_groups: game.finish_groups,
  table_cards: game.table_cards,
  table_arithmetic: game.table_arithmetic,
  bout_starting_attacker: game.bout_starting_attacker,
  attacker: game.attacker,
  lead_attacker: game.lead_attacker,
  defender: game.defender,
  bout_phase: game.bout_phase,
  packets: game.packets,
  active_packet: game.active_packet,
  direct_anchor_cards: game.direct_anchor_cards,
  active_attack_value: game.active_attack_value,
  attack_card_limit: game.attack_card_limit,
  max_attack_card_addition: game.max_attack_card_addition,
  total_attack_card_count: game.total_attack_card_count,
  transfer_open: game.transfer_open,
  required_seat: game.required_seat,
  last_bout_summary: game.last_bout_summary,
  ...overrides,
});

interface ApiStub {
  getCapabilities: ReturnType<
    typeof vi.fn<
      () => Observable<{ multiplayer_3_4_enabled: boolean; deck_variants_enabled?: boolean }>
    >
  >;
  createGame: ReturnType<
    typeof vi.fn<(totalPlayers?: 2 | 3 | 4, deckConfig?: DeckConfig) => Observable<GameResponse>>
  >;
  getGame: ReturnType<typeof vi.fn<(id: string) => Observable<GameResponse>>>;
  restartGame: ReturnType<typeof vi.fn<(id: string) => Observable<GameResponse>>>;
  getHints: ReturnType<
    typeof vi.fn<(id: string, cards: readonly string[]) => Observable<HintResponse>>
  >;
  submitAction: ReturnType<
    typeof vi.fn<
      (id: string, action: string, cards?: readonly string[]) => Observable<GameResponse>
    >
  >;
}

describe('GamePageComponent', () => {
  let fixture: ComponentFixture<GamePageComponent>;
  let api: ApiStub;

  beforeEach(async () => {
    sessionStorage.clear();
    localStorage.removeItem('kiba.hintsEnabled');
    localStorage.removeItem('kiba.multiplayerOnboarding.v1');
    localStorage.removeItem('kiba.deckVariantsOnboarding.v1');
    localStorage.removeItem('kiba.botPresentationSpeed');
    api = {
      getCapabilities: vi.fn().mockReturnValue(of({ multiplayer_3_4_enabled: false })),
      createGame: vi.fn(),
      getGame: vi.fn(),
      restartGame: vi.fn(),
      getHints: vi.fn().mockReturnValue(
        of({
          selected_card_ids: [],
          suggested_card_ids: [],
          suggested_action_types: [],
          combinations: [],
        }),
      ),
      submitAction: vi.fn(),
    };
    await TestBed.configureTestingModule({
      imports: [GamePageComponent],
      providers: [
        provideRouter([]),
        { provide: GameApiService, useValue: api },
        {
          provide: AuthService,
          useValue: { currentUser: signal(null), initialized: signal(true) },
        },
      ],
    }).compileComponents();
  });

  const clickButton = (label: string): void => {
    const button = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (candidate) => candidate.textContent?.trim() === label,
    );
    expect(button).toBeDefined();
    (button as HTMLButtonElement).click();
    fixture.detectChanges();
  };

  const create = (game = makeGame()): void => {
    api.createGame.mockReturnValue(of(game));
    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();
  };

  it('starts a new game automatically when the play route opens', () => {
    create();
    const element = fixture.nativeElement as HTMLElement;
    expect(api.createGame).toHaveBeenCalledOnce();
    expect(sessionStorage.getItem('kiba.activeBotGameId')).toBe('game-1');
    expect(element.textContent).toContain('Партия против бота');
    expect(element.textContent).toContain('Ваш ход');
    expect(element.querySelector('app-deck-config-selector')).toBeNull();
  }, 15_000);

  it('shows a neutral loading state while fresh capabilities are unresolved', () => {
    const capabilities = new Subject<{
      multiplayer_3_4_enabled: boolean;
      deck_variants_enabled?: boolean;
    }>();
    api.getCapabilities.mockReturnValue(capabilities);
    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;

    expect(element.textContent).toContain('Загружаем варианты игры');
    expect(element.textContent).not.toContain('Не удалось начать игру');
    expect(api.createGame).not.toHaveBeenCalled();

    capabilities.next({ multiplayer_3_4_enabled: true, deck_variants_enabled: true });
    capabilities.complete();
    fixture.detectChanges();
    expect(element.textContent).toContain('Игра с ботами');
    expect(element.textContent).not.toContain('Не удалось начать игру');
  });

  it('shows a keyboard-native bot speed preference in setup and stores changes locally', () => {
    api.getCapabilities.mockReturnValue(
      of({ multiplayer_3_4_enabled: true, deck_variants_enabled: true }),
    );
    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();

    const select = (fixture.nativeElement as HTMLElement).querySelector<HTMLSelectElement>(
      '.setup-speed select',
    )!;
    expect(select.getAttribute('aria-label')).toBe('Темп ботов');
    expect(select.value).toBe('normal');
    select.value = 'relaxed';
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    expect(localStorage.getItem('kiba.botPresentationSpeed')).toBe('relaxed');
  });

  it('keeps a genuine fresh-game creation failure visible after startup completes', () => {
    api.createGame.mockReturnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 503,
            error: { detail: { code: 'internal_error' } },
          }),
      ),
    );
    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('Не удалось начать игру');
    expect(text).toContain('Ход не принят');
    expect(api.createGame).toHaveBeenCalledOnce();
  });

  it('creates the independently selected 108-card bot configuration behind the capability', () => {
    localStorage.setItem('kiba.deckVariantsOnboarding.v1', 'true');
    localStorage.setItem('kiba.multiplayerOnboarding.v1', 'true');
    api.getCapabilities.mockReturnValue(
      of({ multiplayer_3_4_enabled: true, deck_variants_enabled: true }),
    );
    api.createGame.mockReturnValue(
      of(makeMultiplayerGame(4, { deck_profile: 'extended', deck_count: 2, draw_pile_count: 80 })),
    );
    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    element.querySelector<HTMLInputElement>('input[name="botPlayerCount"][value="4"]')!.click();
    element.querySelector<HTMLInputElement>('input[name="deckProfile"][value="extended"]')!.click();
    element.querySelector<HTMLInputElement>('input[name="deckCount"][value="2"]')!.click();
    fixture.detectChanges();

    expect(element.textContent).toContain('Всего 108 карт');
    expect(element.textContent).toContain('Рекомендуется для 3–4 игроков');
    clickButton('Играть');

    expect(api.createGame).toHaveBeenCalledWith(4, {
      deck_profile: 'extended',
      deck_count: 2,
    });
    expect(element.textContent).toContain('Расширенная · 2 колоды · 108 карт');
    expect(element.querySelector('app-hint-panel')).not.toBeNull();
  });

  it('shows a native total-player selector only when the shared capability is enabled', () => {
    localStorage.setItem('kiba.multiplayerOnboarding.v1', 'true');
    api.getCapabilities.mockReturnValue(of({ multiplayer_3_4_enabled: true }));
    api.createGame.mockReturnValue(of(makeMultiplayerGame(4)));
    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(api.createGame).not.toHaveBeenCalled();
    expect(element.textContent).toContain('Игра с ботами');
    expect(element.querySelectorAll('input[name="botPlayerCount"]')).toHaveLength(3);
    expect(element.querySelector<HTMLInputElement>('input[value="2"]')?.checked).toBe(true);

    element.querySelector<HTMLInputElement>('input[value="4"]')?.click();
    fixture.detectChanges();
    clickButton('Играть');

    expect(api.createGame).toHaveBeenCalledWith(4);
    expect(element.querySelectorAll('app-table-seat')).toHaveLength(3);
    expect(element.textContent).toContain('Milo');
    expect(element.textContent).toContain('Nika');
    expect(element.textContent).toContain('Otto');
    expect(element.querySelectorAll('.seat-badge')).toHaveLength(3);
  });

  it('maps three named bots to stable left, top and right seats with accessible bot identity', () => {
    create(makeMultiplayerGame(4));
    const element = fixture.nativeElement as HTMLElement;

    expect(element.querySelector('.seat-left .seat-name')?.textContent).toBe('Milo');
    expect(element.querySelector('.seat-top .seat-name')?.textContent).toBe('Nika');
    expect(element.querySelector('.seat-right .seat-name')?.textContent).toBe('Otto');
    expect(element.querySelector('.seat-left section')?.getAttribute('aria-label')).toContain(
      'Компьютерный соперник',
    );
    expect(element.querySelector('app-hint-panel')).not.toBeNull();
  });

  it('keeps two-player bot geometry at portrait top and local bottom only', () => {
    create();
    const element = fixture.nativeElement as HTMLElement;
    const hand = element.querySelector<HTMLElement>('.position-top .hidden-hand')!;

    expect(element.querySelector('.position-left')).toBeNull();
    expect(element.querySelector('.position-right')).toBeNull();
    expect(element.querySelector('.playfield')?.classList).toContain('has-top-seat');
    expect(element.querySelector('.playfield')?.classList).not.toContain('has-side-seats');
    expect(hand.dataset['cardOrientation']).toBe('portrait');
    expect(hand.dataset['handFlow']).toBe('horizontal');
  });

  it('keeps three-player bot geometry at rotated left and right with no top seat', () => {
    create(makeMultiplayerGame(3));
    const element = fixture.nativeElement as HTMLElement;

    expect(element.querySelector('.position-left .seat-name')?.textContent).toBe('Milo');
    expect(element.querySelector('.position-right .seat-name')?.textContent).toBe('Nika');
    expect(element.querySelector('.position-top')).toBeNull();
    expect(element.querySelector('.playfield')?.classList).not.toContain('has-top-seat');
    expect(element.querySelector('.playfield')?.classList).toContain('has-side-seats');
  });

  it('replays a multiplayer bot game in the same session and preserves names', () => {
    localStorage.setItem('kiba.multiplayerOnboarding.v1', 'true');
    const completed = makeMultiplayerGame(3, {
      phase: 'complete',
      result: { outcome: 'WIN', winner: 'HUMAN', winner_seat: 'one' },
      finish_groups: [['one'], ['two'], ['three']],
      active_seats: [],
      finished_seats: ['one', 'two', 'three'],
    });
    const restarted = makeMultiplayerGame(3, { game_id: completed.game_id });
    api.restartGame.mockReturnValue(of(restarted));
    create(completed);

    clickButton('Сыграть ещё');

    expect(api.restartGame).toHaveBeenCalledWith('game-1');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Milo');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Nika');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('Порядок финиша');
  });

  it('keeps a completed multiplayer result when replay is feature-gated off', () => {
    localStorage.setItem('kiba.multiplayerOnboarding.v1', 'true');
    const completed = makeMultiplayerGame(3, {
      phase: 'complete',
      result: { outcome: 'WIN', winner: 'HUMAN', winner_seat: 'one' },
      finish_groups: [['one'], ['two'], ['three']],
    });
    api.restartGame.mockReturnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            error: { detail: { code: 'FEATURE_NOT_AVAILABLE' } },
            status: 409,
          }),
      ),
    );
    create(completed);
    api.createGame.mockClear();

    clickButton('Сыграть ещё');

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Выбранный вариант сейчас недоступен');
    expect(text).toContain('Порядок финиша');
    expect(api.createGame).not.toHaveBeenCalledWith(2);
  });

  it('renders authoritative tied multiplayer placements without progression controls', () => {
    localStorage.setItem('kiba.multiplayerOnboarding.v1', 'true');
    create(
      makeMultiplayerGame(4, {
        phase: 'complete',
        result: { outcome: 'DRAW', winner: null, winner_seat: null },
        finish_groups: [
          ['one', 'two'],
          ['three', 'four'],
        ],
        active_seats: [],
        finished_seats: ['one', 'two', 'three', 'four'],
      }),
    );
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('1-е место');
    expect(text).toContain('3-е место');
    expect(text).toContain('Матчи на 3–4 игроков пока не влияют');
    expect(text).not.toContain('XP');
    expect(text).toContain('В меню');
  });

  it('keeps the table visible and removes controls while the finished human observes bots', () => {
    localStorage.setItem('kiba.multiplayerOnboarding.v1', 'true');
    const observing = makeMultiplayerGame(4);
    create({
      ...observing,
      human_hand: [],
      participants: observing.participants.map((participant) =>
        participant.seat === 'one'
          ? { ...participant, active: false, finished: true, hand_count: 0 }
          : participant,
      ),
      active_seats: ['two', 'three', 'four'],
      finished_seats: ['one'],
      finish_groups: [['one']],
      required_actor: 'BOT',
      required_seat: 'two',
      available_actions: [],
    });

    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Вы финишировали — партия продолжается');
    expect(element.querySelector('app-game-table')).not.toBeNull();
    expect(element.querySelector('app-action-bar')).toBeNull();
  });

  it('shows versioned onboarding once for a newly created multiplayer bot match', () => {
    api.getCapabilities.mockReturnValue(of({ multiplayer_3_4_enabled: true }));
    api.createGame.mockReturnValue(of(makeMultiplayerGame(3)));
    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();
    (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLInputElement>('input[value="3"]')
      ?.click();
    fixture.detectChanges();
    clickButton('Играть');

    expect(api.createGame).not.toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Больше игроков — та же KIBA',
    );
    clickButton('Понятно');
    expect(api.createGame).toHaveBeenCalledWith(3);
    expect(localStorage.getItem('kiba.multiplayerOnboarding.v1')).toBe('true');
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.multiplayer-onboarding'),
    ).toBeNull();
  });

  it('shows deck onboarding for a fresh non-default game but not a restored session', () => {
    api.getCapabilities.mockReturnValue(
      of({ multiplayer_3_4_enabled: false, deck_variants_enabled: true }),
    );
    api.createGame.mockReturnValue(of(makeGame({ deck_profile: 'extended' })));
    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();
    (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLInputElement>('input[name="deckProfile"][value="extended"]')!
      .click();
    fixture.detectChanges();
    clickButton('Играть');

    expect(api.createGame).not.toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Пробуете другую колоду?');
    clickButton('Понятно');
    expect(api.createGame).toHaveBeenCalledWith(2, {
      deck_profile: 'extended',
      deck_count: 1,
    });
    expect(localStorage.getItem('kiba.deckVariantsOnboarding.v1')).toBe('true');

    fixture.destroy();
    localStorage.removeItem('kiba.deckVariantsOnboarding.v1');
    sessionStorage.setItem('kiba.activeBotGameId', 'variant-game');
    api.getGame.mockReturnValue(
      of(makeGame({ game_id: 'variant-game', deck_profile: 'extended' })),
    );
    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain(
      'Пробуете другую колоду?',
    );
  });

  it('acknowledges deck and multiplayer onboarding before creating a non-default game', () => {
    api.getCapabilities.mockReturnValue(
      of({ multiplayer_3_4_enabled: true, deck_variants_enabled: true }),
    );
    api.createGame.mockReturnValue(of(makeMultiplayerGame(4, { deck_profile: 'extended' })));
    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    element.querySelector<HTMLInputElement>('input[name="botPlayerCount"][value="4"]')!.click();
    element.querySelector<HTMLInputElement>('input[name="deckProfile"][value="extended"]')!.click();
    fixture.detectChanges();

    clickButton('Играть');
    expect(api.createGame).not.toHaveBeenCalled();
    expect(element.textContent).toContain('Пробуете другую колоду?');
    clickButton('Понятно');
    expect(api.createGame).not.toHaveBeenCalled();
    expect(element.textContent).toContain('Больше игроков — та же KIBA');
    clickButton('Понятно');

    expect(api.createGame).toHaveBeenCalledWith(4, {
      deck_profile: 'extended',
      deck_count: 1,
    });
    expect(element.querySelector('.game-board')).not.toBeNull();
  });

  it('preserves a non-default deck configuration through Play Again', () => {
    localStorage.setItem('kiba.deckVariantsOnboarding.v1', 'true');
    const completed = makeGame({
      phase: 'complete',
      result: { outcome: 'WIN', winner: 'HUMAN', winner_seat: 'one' },
      deck_profile: 'extended',
      deck_count: 2,
    });
    const restarted = makeGame({ deck_profile: 'extended', deck_count: 2 });
    api.restartGame.mockReturnValue(of(restarted));
    create(completed);

    clickButton('Сыграть ещё');

    expect(api.restartGame).toHaveBeenCalledWith('game-1');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Расширенная · 2 колоды · 108 карт',
    );
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('Игра окончена');
  });

  it('requests hints after selection and highlights only server-suggested cards', () => {
    api.getHints.mockReturnValue(
      of({
        selected_card_ids: ['6C'],
        continuation_card_ids: ['QD'],
        suggested_card_ids: ['QD'],
        legal_action_types: [],
        suggested_action_types: ['INITIAL_ATTACK'],
        combinations: [
          {
            action: 'INITIAL_ATTACK',
            card_ids: ['6C', 'QD'],
            added_card_ids: ['QD'],
            reason: 'arithmetic_equality',
            selected_value: 21,
            target_value: null,
          },
        ],
      }),
    );
    create();

    (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLButtonElement>('app-hand .playing-card')!
      .click();
    fixture.detectChanges();

    expect(api.getHints).toHaveBeenCalledWith('game-1', ['6C']);
    const cards = (fixture.nativeElement as HTMLElement).querySelectorAll('app-hand .playing-card');
    expect(cards[0].classList).toContain('selected');
    expect(cards[1].classList).toContain('suggested');
    const hintPanel = (fixture.nativeElement as HTMLElement).querySelector('.hint-panel')!;
    expect(hintPanel.textContent).toContain('6♣ + Q♦');
    expect(hintPanel.textContent).not.toMatch(/(?:10|[6-9JQKA])[CDHS](?![a-z])/);
    expect(hintPanel.outerHTML).not.toMatch(/(?:aria-label|title)="[^"]*(?:10|[6-9JQKA])[CDHS]/);
  });

  it.each([2, 3, 4] as const)(
    'requests untouched initial hints for a %i-player bot game',
    (totalPlayers) => {
      create(totalPlayers === 2 ? makeGame() : makeMultiplayerGame(totalPlayers));

      expect(api.getHints).toHaveBeenCalledTimes(1);
      expect(api.getHints).toHaveBeenCalledWith('game-1', []);
    },
  );

  it('builds a five-rank Street one card at a time before enabling submission', () => {
    const street = [
      card('8C', '8', 'clubs', 8),
      card('9D', '9', 'diamonds', 9),
      card('10H', '10', 'hearts', 10),
      card('JS', 'J', 'spades', 12),
      card('QC', 'Q', 'clubs', 15),
    ];
    api.getHints.mockImplementation((_id, selected) =>
      of({
        selected_card_ids: [...selected],
        continuation_card_ids: street
          .filter((value) => !selected.includes(value.code))
          .map((value) => value.code),
        suggested_card_ids: [],
        legal_action_types: selected.length === 5 ? ['INITIAL_ATTACK'] : [],
        suggested_action_types: ['INITIAL_ATTACK'],
        combinations: [],
      }),
    );
    api.submitAction.mockReturnValue(of(makeGame({ human_hand: [], table_cards: street })));
    create(makeGame({ human_hand: street, max_attack_card_addition: 7 }));

    const buttons = (fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>(
      'app-hand .playing-card',
    );
    const attack = (): HTMLButtonElement =>
      [
        ...(fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>('button'),
      ].find((value) => value.textContent?.trim() === 'Ходить')!;

    for (let index = 0; index < street.length; index += 1) {
      expect(buttons[index].disabled).toBe(false);
      buttons[index].click();
      fixture.detectChanges();
      expect(attack().disabled).toBe(index < street.length - 1);
    }

    attack().click();
    fixture.detectChanges();
    expect(api.submitAction).toHaveBeenCalledWith('game-1', 'INITIAL_ATTACK', [
      '8C',
      '9D',
      '10H',
      'JS',
      'QC',
    ]);
  });

  it('never calls the hint API while the saved preference is off', () => {
    localStorage.setItem('kiba.hintsEnabled', 'false');
    create();

    (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLButtonElement>('app-hand .playing-card')!
      .click();
    fixture.detectChanges();

    expect(api.getHints).not.toHaveBeenCalled();
  });

  it('cancels stale hint work and keeps failures separate from gameplay errors', () => {
    const first = new Subject<HintResponse>();
    api.getHints
      .mockReturnValueOnce(first)
      .mockReturnValueOnce(throwError(() => new Error('hint service unavailable')));
    create();
    const cards = (fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>(
      'app-hand .playing-card',
    );

    cards[0].click();
    cards[1].click();
    fixture.detectChanges();
    first.next({
      selected_card_ids: ['6C'],
      suggested_card_ids: ['7H'],
      suggested_action_types: ['INITIAL_ATTACK'],
      combinations: [],
    });
    fixture.detectChanges();

    expect(first.observed).toBe(false);
    expect((fixture.nativeElement as HTMLElement).querySelector('.error-message')).toBeNull();
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.playing-card.suggested'),
    ).toBeNull();
  });

  it('restores a stored authoritative game without creating a new deal', () => {
    sessionStorage.setItem('kiba.activeBotGameId', 'progressed-game');
    const progressed = makeGame({
      game_id: 'progressed-game',
      draw_pile_count: 11,
      discard_count: 14,
      human_hand: [queenDiamonds, sevenHearts],
    });
    api.getGame.mockReturnValue(of(progressed));

    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(api.getGame).toHaveBeenCalledWith('progressed-game');
    expect(api.createGame).not.toHaveBeenCalled();
    expect(text).toContain('Бито');
    expect(text).toContain('14');
    expect(
      (fixture.nativeElement as HTMLElement).querySelectorAll('app-hand .playing-card'),
    ).toHaveLength(2);
    expect((fixture.nativeElement as HTMLElement).querySelector('.motion-card')).toBeNull();
  });

  it('keeps setup visible after an explicit leave and refresh instead of resurrecting a game', () => {
    sessionStorage.setItem('kiba.botSetupRequested', 'true');
    api.getCapabilities.mockReturnValue(
      of({ multiplayer_3_4_enabled: true, deck_variants_enabled: true }),
    );

    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();

    expect(api.getGame).not.toHaveBeenCalled();
    expect(api.createGame).not.toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).querySelector('.bot-setup')).not.toBeNull();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Игра с ботами');
  });

  it('shows a recovery loading state without flashing a replacement game', () => {
    sessionStorage.setItem('kiba.activeBotGameId', 'progressed-game');
    const recovery = new Subject<GameResponse>();
    api.getGame.mockReturnValue(recovery);

    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Восстанавливаем партию…');
    expect(api.createGame).not.toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).querySelector('.game-board')).toBeNull();
  });

  it('clears a definitively missing game and waits for an intentional new start', () => {
    sessionStorage.setItem('kiba.activeBotGameId', 'expired-game');
    api.getGame.mockReturnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            error: { detail: { code: 'game_not_found' } },
            status: 404,
          }),
      ),
    );

    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Предыдущую партию больше нельзя восстановить');
    expect(sessionStorage.getItem('kiba.activeBotGameId')).toBeNull();
    expect(api.createGame).not.toHaveBeenCalled();

    api.createGame.mockReturnValue(of(makeGame({ game_id: 'replacement' })));
    clickButton('Начать');
    expect(api.createGame).toHaveBeenCalledOnce();
    expect(sessionStorage.getItem('kiba.activeBotGameId')).toBe('replacement');
  });

  it('preserves the stored game after a transient recovery failure and retries GET', () => {
    sessionStorage.setItem('kiba.activeBotGameId', 'recoverable-game');
    api.getGame
      .mockReturnValueOnce(
        throwError(
          () =>
            new HttpErrorResponse({
              error: { detail: { code: 'internal_error' } },
              status: 503,
            }),
        ),
      )
      .mockReturnValueOnce(of(makeGame({ game_id: 'recoverable-game', discard_count: 8 })));

    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Не удалось восстановить партию',
    );
    expect(sessionStorage.getItem('kiba.activeBotGameId')).toBe('recoverable-game');
    expect(api.createGame).not.toHaveBeenCalled();

    clickButton('Повторить');
    expect(api.getGame).toHaveBeenCalledTimes(2);
    expect(api.createGame).not.toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Бито');
  });

  it('localizes the stale-game recovery message in English', () => {
    localStorage.setItem('kiba.preferred-locale', 'en');
    sessionStorage.setItem('kiba.activeBotGameId', 'expired-game');
    api.getGame.mockReturnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            error: { detail: { code: 'game_not_found' } },
            status: 404,
          }),
      ),
    );

    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Your previous game is no longer available',
    );
  });

  it('keeps the active public game snapshot when the routed page is recreated', () => {
    create();
    fixture.destroy();

    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();

    expect(api.createGame).toHaveBeenCalledOnce();
    expect((fixture.nativeElement as HTMLElement).querySelector('.seat-name')?.textContent).toBe(
      'БОТ',
    );
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.seat-count')?.textContent,
    ).toContain('6 карт');
  });

  it('creates and renders a public human-vs-bot state without hidden cards', () => {
    create();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(api.createGame).toHaveBeenCalledOnce();
    expect(
      (fixture.nativeElement as HTMLElement).querySelectorAll('app-hand .playing-card'),
    ).toHaveLength(3);
    expect((fixture.nativeElement as HTMLElement).querySelector('.seat-name')?.textContent).toBe(
      'БОТ',
    );
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.seat-count')?.textContent,
    ).toContain('6 карт');
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.draw-zone .deck-count')?.textContent,
    ).toContain('21');
    expect(text).toContain('♥ и все 7');
    expect(text).toContain('Ходить');
    expect(text).not.toContain('Скрытая карта бота');
    expect(text).not.toContain('Порядок колоды');
  });

  it('renders the opponent, public draw pile, center table, and bito as distinct table zones', () => {
    create(makeGame({ discard_count: 16 }));
    const element = fixture.nativeElement as HTMLElement;
    const stage = element.querySelector('.table-stage') as HTMLElement;

    expect(element.querySelector('.opponent-zone .seat-name')?.textContent).toBe('БОТ');
    expect(element.querySelector('.opponent-zone .seat-count')?.textContent).toContain('6 карт');
    expect(element.querySelectorAll('.opponent-zone .hidden-card')).toHaveLength(6);
    expect(stage.querySelector('.draw-zone .deck-count')?.textContent).toContain('21');
    expect(stage.querySelectorAll('.draw-zone app-playing-card')).toHaveLength(1);
    expect(stage.querySelector(':scope > app-game-table.center-table')).not.toBeNull();
    expect(stage.querySelector('.discard-zone')?.textContent).toContain('Бито');
    expect(stage.querySelector('.discard-zone')?.textContent).toContain('16');
    expect(stage.textContent).not.toContain('Порядок колоды');
  });

  it('animates a server-confirmed opening bot card from the hidden hand without exposing hand data', () => {
    create(
      makeGame({
        bot_hand_count: 6,
        table_cards: [sixClubs],
        recent_events: [
          {
            type: 'BOT_INITIAL_ATTACK',
            actor: 'BOT',
            card_count: 1,
            value: 6,
            target: null,
          },
        ],
      }),
    );

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelectorAll('.opponent-zone .hidden-card')).toHaveLength(6);
    expect(element.querySelectorAll('.motion-card.from-top.to-table')).toHaveLength(1);
    expect(element.querySelector('.motion-layer')?.getAttribute('aria-hidden')).toBe('true');
    expect(element.querySelector('.opponent-zone')?.innerHTML).not.toContain('6C');
  });

  it('keeps caption, public table, and roles synchronized through a five-event bot cascade', () => {
    vi.useFakeTimers();
    try {
      const cards = [
        { ...sixClubs, id: 'a', code: '6C' },
        { ...queenDiamonds, id: 'b', code: 'QD' },
        { ...sevenHearts, id: 'c', code: '7H' },
        { ...sixClubs, id: 'd', code: '6D', suit: 'diamonds' as const },
        { ...queenDiamonds, id: 'e', code: 'QS', suit: 'spades' as const },
      ];
      const packet = (attack: readonly GameCard[], defense: readonly GameCard[] = []) => ({
        attack_cards: attack,
        attack_value: attack.reduce((total, value) => total + value.effective_value, 0),
        defense_cards: defense,
        defense_value:
          defense.length === 0
            ? null
            : defense.reduce((total, value) => total + value.effective_value, 0),
        closed: defense.length > 0,
        throw_in_reasons: [],
      });
      const frames = [
        makeMultiplayerGame(4, {
          table_cards: cards.slice(0, 1),
          packets: [packet(cards.slice(0, 1))],
          attacker: 'two',
          lead_attacker: 'two',
          defender: 'three',
          required_seat: 'three',
        }),
        makeMultiplayerGame(4, {
          table_cards: cards.slice(0, 2),
          packets: [packet(cards.slice(0, 2))],
          attacker: 'three',
          lead_attacker: 'three',
          defender: 'four',
          required_seat: 'four',
        }),
        makeMultiplayerGame(4, {
          table_cards: cards.slice(0, 3),
          packets: [packet(cards.slice(0, 2), cards.slice(2, 3))],
          attacker: 'two',
          lead_attacker: 'two',
          defender: 'four',
          required_seat: 'two',
        }),
        makeMultiplayerGame(4, {
          table_cards: cards.slice(0, 4),
          packets: [packet(cards.slice(0, 2), cards.slice(2, 3)), packet(cards.slice(3, 4))],
          attacker: 'two',
          lead_attacker: 'two',
          defender: 'four',
          required_seat: 'four',
        }),
        makeMultiplayerGame(4, {
          table_cards: cards,
          packets: [
            packet(cards.slice(0, 2), cards.slice(2, 3)),
            packet(cards.slice(3, 4), cards.slice(4, 5)),
          ],
          attacker: 'one',
          lead_attacker: 'one',
          defender: 'four',
          required_actor: 'HUMAN',
          required_seat: 'one',
          available_actions: ['THROW_IN', 'BITO'],
        }),
      ];
      const types = [
        'BOT_INITIAL_ATTACK',
        'BOT_TRANSFER',
        'BOT_DEFEND',
        'BOT_THROW_IN',
        'BOT_DEFEND',
      ] as const;
      const actors = ['two', 'three', 'four', 'two', 'three'] as const;
      const latest = {
        ...frames[4],
        recent_events: types.map((type, index) => ({
          type,
          actor: 'BOT' as const,
          actor_seat: actors[index],
          card_count: 1,
          value: cards[index].effective_value,
          target: null,
          cards: [cards[index]],
          presentation_state: presentationState(frames[index]),
        })),
      };

      create(makeMultiplayerGame(4));
      api.getHints.mockClear();
      api.submitAction.mockReturnValue(of(latest));
      const firstCard = (fixture.nativeElement as HTMLElement).querySelector(
        'app-hand .playing-card',
      ) as HTMLButtonElement;
      firstCard.click();
      fixture.detectChanges();
      api.getHints.mockClear();
      clickButton('Ходить');

      const expected = [
        ['Milo атакует', 1, 'Nika'],
        ['Nika переводит', 2, 'Otto'],
        ['Otto покрывает', 3, 'Milo'],
        ['Milo подкидывает', 4, 'Otto'],
        ['Nika покрывает', 5, null],
      ] as const;
      const durations = [1_500, 1_800, 1_600, 1_650, 1_600];
      for (let index = 0; index < expected.length; index += 1) {
        fixture.detectChanges();
        const element = fixture.nativeElement as HTMLElement;
        expect(element.textContent).toContain(expected[index][0]);
        expect(element.querySelectorAll('.packet app-playing-card')).toHaveLength(
          expected[index][1],
        );
        if (expected[index][2] !== null) {
          expect(element.querySelector('.table-seat.is-required .seat-name')?.textContent).toBe(
            expected[index][2],
          );
        }
        vi.advanceTimersByTime(durations[index]);
      }
      fixture.detectChanges();
      expect(
        (fixture.nativeElement as HTMLElement).querySelectorAll('.packet app-playing-card'),
      ).toHaveLength(5);
      expect(api.getHints).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it('keeps the turn status next to the player interaction region', () => {
    create();
    const element = fixture.nativeElement as HTMLElement;
    const status = element.querySelector('.status-banner') as HTMLElement;
    const hand = element.querySelector('.player-hand-region') as HTMLElement;

    expect(status.textContent).toContain('Ваш ход');
    expect(status.compareDocumentPosition(hand) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0);
  });

  it('selects legacy unique-face cards and clears selection after success', () => {
    create();
    api.getHints.mockReturnValue(
      of({
        selected_card_ids: ['6C'],
        suggested_card_ids: ['QD'],
        suggested_action_types: ['INITIAL_ATTACK'],
        combinations: [],
      }),
    );
    const updated = makeGame({ human_hand: [queenDiamonds, sevenHearts] });
    api.submitAction.mockReturnValue(of(updated));
    const firstCard = (fixture.nativeElement as HTMLElement).querySelector(
      'app-hand .playing-card',
    ) as HTMLButtonElement;
    firstCard.click();
    fixture.detectChanges();
    expect(firstCard.getAttribute('aria-pressed')).toBe('true');
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.playing-card.suggested'),
    ).not.toBeNull();

    clickButton('Ходить');
    expect(api.submitAction).toHaveBeenCalledWith('game-1', 'INITIAL_ATTACK', ['6C']);
    expect(
      (fixture.nativeElement as HTMLElement).querySelectorAll('.motion-card.from-bottom.to-table'),
    ).toHaveLength(1);
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.selection-summary')?.textContent,
    ).toContain('Выбрано: 0');
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.playing-card.suggested'),
    ).not.toBeNull();
  });

  it('selects and submits one exact duplicate by physical ID while the other remains', () => {
    const firstKing = {
      ...queenDiamonds,
      id: 'deck-1:KH',
      code: 'KH',
      rank: 'K',
      suit: 'hearts' as const,
    };
    const secondKing = { ...firstKing, id: 'deck-2:KH' };
    const initial = makeGame({
      deck_profile: 'classic',
      deck_count: 2,
      human_hand: [firstKing, secondKing],
    });
    const updated = makeGame({
      deck_profile: 'classic',
      deck_count: 2,
      human_hand: [secondKing],
      table_cards: [firstKing],
    });
    api.getHints.mockReturnValue(
      of({
        selected_card_ids: ['KH'],
        suggested_card_ids: [],
        selected_physical_ids: ['deck-1:KH'],
        suggested_physical_ids: [],
        suggested_action_types: ['INITIAL_ATTACK'],
        combinations: [],
      }),
    );
    api.submitAction.mockReturnValue(of(updated));
    create(initial);

    const cards = (fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>(
      'app-hand .playing-card',
    );
    cards[0].click();
    fixture.detectChanges();
    expect(cards[0].getAttribute('aria-pressed')).toBe('true');
    expect(cards[1].getAttribute('aria-pressed')).toBe('false');

    clickButton('Ходить');
    expect(api.getHints).toHaveBeenCalledWith('game-1', ['deck-1:KH']);
    expect(api.submitAction).toHaveBeenCalledWith('game-1', 'INITIAL_ATTACK', ['deck-1:KH']);
    const remaining = (fixture.nativeElement as HTMLElement).querySelectorAll(
      'app-hand .playing-card',
    );
    expect(remaining).toHaveLength(1);
    expect(remaining[0].getAttribute('aria-label')).toContain('K');
  });

  it('can submit both visually identical physical cards in one selection', () => {
    const firstKing = {
      ...queenDiamonds,
      id: 'deck-1:KH',
      code: 'KH',
      rank: 'K',
      suit: 'hearts' as const,
    };
    const secondKing = { ...firstKing, id: 'deck-2:KH' };
    api.submitAction.mockReturnValue(
      of(makeGame({ deck_count: 2, human_hand: [], table_cards: [firstKing, secondKing] })),
    );
    create(makeGame({ deck_count: 2, human_hand: [firstKing, secondKing] }));

    const cards = (fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>(
      'app-hand .playing-card',
    );
    cards[0].click();
    cards[1].click();
    fixture.detectChanges();
    clickButton('Ходить');

    expect(api.submitAction).toHaveBeenCalledWith('game-1', 'INITIAL_ATTACK', [
      'deck-1:KH',
      'deck-2:KH',
    ]);
  });

  it('keeps the current state and selected cards when the server rejects a move', () => {
    create(
      makeGame({
        available_actions: ['DEFEND', 'TRANSFER', 'TAKE'],
        active_attack_value: 18,
      }),
    );
    api.submitAction.mockReturnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            error: { detail: { code: 'illegal_defense' } },
            status: 409,
          }),
      ),
    );
    const firstCard = (fixture.nativeElement as HTMLElement).querySelector(
      'app-hand .playing-card',
    ) as HTMLButtonElement;
    firstCard.click();
    fixture.detectChanges();
    clickButton('Покрыть');
    expect((fixture.nativeElement as HTMLElement).querySelector('.motion-card')).toBeNull();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('[role="alert"]')?.textContent).toContain('Недостаточно очков');
    expect(element.querySelector('app-hand .playing-card')?.getAttribute('aria-pressed')).toBe(
      'true',
    );
    expect(element.textContent).toContain('6♣');
  });

  it('renders table packets, current defense threshold, and exact arithmetic', () => {
    create(
      makeGame({
        table_cards: [sixClubs, queenDiamonds],
        table_arithmetic: {
          total_effective_value: 21,
          physical_card_count: 2,
          arithmetic_mean: '21/2',
        },
        packets: [
          {
            attack_cards: [sixClubs],
            attack_value: 6,
            defense_cards: [queenDiamonds],
            defense_value: 15,
            closed: true,
            throw_in_reasons: [],
          },
        ],
        active_attack_value: 18,
        direct_anchor_cards: [queenDiamonds],
      }),
    );
    const text = (fixture.nativeElement as HTMLElement).querySelector(
      'app-game-table',
    )?.textContent;
    expect(text).toContain('Атака · 6');
    expect(text).toContain('Защита · 15');
    expect(text).toContain('Сумма 21');
    expect(text).toContain('Среднее 21 / 2');
    expect(text).toContain('Покрыть > 18');
    expect(text).toContain('Q♦ · 15');
    expect(text).not.toContain('QD · 15');
  });

  it('keeps a localized summary of the immediately previous bout', () => {
    create(
      makeGame({
        last_bout_summary: { outcome: 'TAKE', actor_seat: 'two', table_card_count: 11 },
      }),
    );
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Последний кон');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Бот взял 11 карт');

    TestBed.inject(GameSessionState).game.set(
      makeGame({
        last_bout_summary: { outcome: 'TAKE', actor_seat: 'one', table_card_count: 1 },
      }),
    );
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Вы взяли 1 карту');

    TestBed.inject(GameSessionState).game.set(
      makeGame({
        last_bout_summary: { outcome: 'BITO', actor_seat: 'one', table_card_count: 4 },
      }),
    );
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Ваша защита завершена');
  });

  it('keeps a complete multi-card selection visible in the persistent action summary', () => {
    create();
    const cards = (fixture.nativeElement as HTMLElement).querySelectorAll('app-hand .playing-card');
    (cards[0] as HTMLButtonElement).click();
    (cards[2] as HTMLButtonElement).click();
    fixture.detectChanges();

    const summary = (fixture.nativeElement as HTMLElement).querySelector(
      '.action-dock .selection-summary',
    ) as HTMLElement;
    expect(summary.textContent).toContain('Выбрано: 2');
    expect(summary.textContent).toContain('6♣');
    expect(summary.textContent).toContain('7♥');
    expect(summary.textContent).toContain('6 + 14 = 20');
    expect(summary.getAttribute('aria-label')).toContain('Сумма 20');
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.player-hand-region'),
    ).not.toBeNull();
  });

  it('renders exact mean values and server-confirmed throw-in explanations', () => {
    create(
      makeGame({
        table_arithmetic: {
          total_effective_value: 32,
          physical_card_count: 3,
          arithmetic_mean: '32/3',
        },
        packets: [
          {
            attack_cards: [sixClubs],
            attack_value: 6,
            defense_cards: [queenDiamonds],
            defense_value: 15,
            closed: true,
            throw_in_reasons: [],
          },
          {
            attack_cards: [queenDiamonds],
            attack_value: 15,
            defense_cards: [],
            defense_value: null,
            closed: false,
            throw_in_reasons: [
              {
                type: 'arithmetic_mean',
                target_value: 15,
                expression: '30 / 2 = 15',
              },
            ],
          },
        ],
      }),
    );

    const tableText = (fixture.nativeElement as HTMLElement).querySelector(
      'app-game-table',
    )?.textContent;
    expect(tableText).toContain('Среднее 32 / 3');
    expect(tableText).toContain('Подкинуто по среднему');
    expect(tableText).toContain('30 / 2 = 15');
  });

  it('renders the server-confirmed latest-defense-total explanation', () => {
    create(
      makeGame({
        packets: [
          {
            attack_cards: [queenDiamonds],
            attack_value: 15,
            defense_cards: [],
            defense_value: null,
            closed: false,
            throw_in_reasons: [
              {
                type: 'defense_total',
                target_value: 20,
                expression: '12 + 8 = 20',
              },
            ],
          },
        ],
      }),
    );

    const tableText = (fixture.nativeElement as HTMLElement).querySelector(
      'app-game-table',
    )?.textContent;
    expect(tableText).toContain('Подкинуто по сумме защиты');
    expect(tableText).toContain('12 + 8 = 20');
  });

  it('formats server-confirmed reason cards with player-facing suit symbols', () => {
    create(
      makeGame({
        packets: [
          {
            attack_cards: [sixClubs],
            attack_value: 6,
            defense_cards: [],
            defense_value: null,
            closed: false,
            throw_in_reasons: [
              {
                type: 'existing_value',
                target_value: 15,
                expression: null,
                source_cards: [queenDiamonds],
              },
            ],
          },
        ],
      }),
    );

    const tableText = (fixture.nativeElement as HTMLElement).querySelector(
      'app-game-table',
    )?.textContent;
    expect(tableText).toContain('Q♦ = 15');
    expect(tableText).not.toContain('QD = 15');
  });

  it('renders a server-confirmed rank run without inferring legality', () => {
    create(
      makeGame({
        packets: [
          {
            attack_cards: [queenDiamonds],
            attack_value: 15,
            defense_cards: [],
            defense_value: null,
            closed: false,
            throw_in_reasons: [
              {
                type: 'rank_run',
                target_value: null,
                expression: '10–A',
                run_start: '10',
                run_end: 'A',
                run_length: 5,
                run_ranks: ['10', 'J', 'Q', 'K', 'A'],
              },
            ],
          },
        ],
      }),
    );

    const tableText = (fixture.nativeElement as HTMLElement).querySelector(
      'app-game-table',
    )?.textContent;
    expect(tableText).toContain('Ряд');
    expect(tableText).toContain('10–A');
  });

  it('renders an exact integer arithmetic mean without decimal formatting', () => {
    create(
      makeGame({
        table_arithmetic: {
          total_effective_value: 30,
          physical_card_count: 2,
          arithmetic_mean: '15',
        },
      }),
    );

    expect(
      (fixture.nativeElement as HTMLElement).querySelector('app-game-table')?.textContent,
    ).toContain('Среднее 15');
  });

  it('uses every server-provided action type and terminal actions need no cards', () => {
    create(
      makeGame({
        available_actions: ['INITIAL_ATTACK', 'DEFEND', 'TRANSFER', 'THROW_IN', 'TAKE', 'BITO'],
      }),
    );
    const text = (fixture.nativeElement as HTMLElement).querySelector(
      'app-action-bar',
    )?.textContent;
    expect(text).toContain('Ходить');
    expect(text).toContain('Покрыть');
    expect(text).toContain('Перевести');
    expect(text).toContain('Подкинуть');
    expect(text).toContain('Взять');
    expect(text).toContain('Бито');
    api.submitAction.mockReturnValue(of(makeGame()));
    clickButton('Взять');
    expect(api.submitAction).toHaveBeenCalledWith('game-1', 'TAKE', []);
  });

  it('shows only high-confidence numeric selection hints', () => {
    create(
      makeGame({
        available_actions: ['DEFEND', 'TRANSFER', 'TAKE'],
        active_attack_value: 14,
      }),
    );
    const cards = (fixture.nativeElement as HTMLElement).querySelectorAll('app-hand .playing-card');
    (cards[0] as HTMLButtonElement).click();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Выбрано 6 — нужно больше 14',
    );

    (cards[0] as HTMLButtonElement).click();
    (cards[2] as HTMLButtonElement).click();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'совпадает с целью перевода',
    );
  });

  it('prevents the screenshot-style exact transfer when the next defender has only five cards', () => {
    const base = makeMultiplayerGame(3);
    const transferCards = [
      card('6C', '6', 'clubs', 12, true),
      card('7H', '7', 'hearts', 14, true),
      card('7S', '7', 'spades', 14, true),
    ];
    const attackCards = [
      card('10D', '10', 'diamonds', 10),
      card('10H', '10', 'hearts', 10),
      card('8H', '8', 'hearts', 8),
      card('JD', 'J', 'diamonds', 12),
    ];
    const packet = {
      attack_cards: attackCards,
      attack_value: 40,
      defense_cards: [],
      defense_value: null,
      closed: false,
      throw_in_reasons: [],
    };
    create(
      makeMultiplayerGame(3, {
        human_hand: transferCards,
        participants: base.participants.map((participant) =>
          participant.seat === 'two' ? { ...participant, hand_count: 5 } : participant,
        ),
        attacker: 'two',
        lead_attacker: 'two',
        defender: 'one',
        required_actor: 'HUMAN',
        required_seat: 'one',
        bout_phase: 'waiting_for_defender_response',
        table_cards: attackCards,
        packets: [packet],
        active_packet: packet,
        active_attack_value: 40,
        attack_card_limit: 7,
        total_attack_card_count: 4,
        max_attack_card_addition: 3,
        transfer_open: true,
        available_actions: ['DEFEND', 'TRANSFER', 'TAKE'],
      }),
    );

    (fixture.nativeElement as HTMLElement)
      .querySelectorAll<HTMLButtonElement>('app-hand .playing-card')
      .forEach((button) => button.click());
    fixture.detectChanges();

    const transfer = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Перевести',
    ) as HTMLButtonElement;
    expect(transfer.disabled).toBe(true);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'После перевода будет 7 атакующих карт, а у следующего защитника только 5 карт',
    );
  });

  it('warns when the selected attack count exceeds the remaining server limit', () => {
    create(
      makeGame({
        attack_card_limit: 7,
        max_attack_card_addition: 1,
        total_attack_card_count: 2,
      }),
    );
    const cards = (fixture.nativeElement as HTMLElement).querySelectorAll('app-hand .playing-card');
    (cards[0] as HTMLButtonElement).click();
    (cards[1] as HTMLButtonElement).click();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Выбрано 2 — остаток лимита атаки 1',
    );
    const attack = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Ходить',
    );
    expect(attack?.disabled).toBe(true);
  });

  it('shows bout cap and authoritative current maximum addition separately', () => {
    create(
      makeGame({
        attack_card_limit: 7,
        total_attack_card_count: 2,
        max_attack_card_addition: 2,
      }),
    );

    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Атака 2 / 7 · Добавить не более 2',
    );
  });

  it('explains and disables a defense with an unnecessary selected card', () => {
    create(
      makeGame({
        available_actions: ['DEFEND', 'TAKE'],
        active_attack_value: 18,
      }),
    );
    const cards = (fixture.nativeElement as HTMLElement).querySelectorAll('app-hand .playing-card');
    cards.forEach((value) => (value as HTMLButtonElement).click());
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Одна или несколько выбранных карт защиты лишние',
    );
    const defend = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Покрыть',
    );
    expect(defend?.disabled).toBe(true);
  });

  it('asks before leaving an active game', () => {
    create();
    clickButton('Покинуть игру');

    const dialog = (fixture.nativeElement as HTMLElement).querySelector('[role="dialog"]');
    expect(dialog?.textContent).toContain('Незавершённая партия не будет засчитана');
    expect(api.createGame).toHaveBeenCalledOnce();

    clickButton('Остаться');
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="dialog"]')).toBeNull();
    expect(sessionStorage.getItem('kiba.activeBotGameId')).toBe('game-1');
  });

  it('suppresses the turn reminder behind the Leave modal and restarts it after cancel', () => {
    create();
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('app-turn-reminder'),
    ).not.toBeNull();

    clickButton('Покинуть игру');
    expect((fixture.nativeElement as HTMLElement).querySelector('app-turn-reminder')).toBeNull();

    clickButton('Остаться');
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('app-turn-reminder'),
    ).not.toBeNull();
  });

  it('relocalizes an already-visible semantic action error when locale changes', () => {
    create(makeGame({ available_actions: ['DEFEND'] }));
    const translations = TestBed.inject(TranslationService);
    translations.setLocale('en');
    api.submitAction.mockReturnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 409,
            error: { detail: { code: 'illegal_defense' } },
          }),
      ),
    );
    fixture.detectChanges();
    (
      (fixture.nativeElement as HTMLElement).querySelector(
        'app-hand .playing-card',
      ) as HTMLButtonElement
    ).click();
    fixture.detectChanges();
    clickButton('Defend');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'The selected total is not enough to defend the active attack',
    );

    translations.setLocale('ru');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Недостаточно очков для покрытия текущей атаки',
    );
  });

  it('keeps keyboard focus inside the Leave dialog and restores it on Escape', async () => {
    create();
    const trigger = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Покинуть игру',
    ) as HTMLButtonElement;
    trigger.focus();
    trigger.click();
    fixture.detectChanges();
    await Promise.resolve();

    const dialog = (fixture.nativeElement as HTMLElement).querySelector(
      '[role="dialog"]',
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
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('confirmed abandonment clears resume state and returns to setup without creating a result', () => {
    create();
    clickButton('Покинуть игру');
    expect(sessionStorage.getItem('kiba.activeBotGameId')).toBe('game-1');

    const confirm = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      '.restart-confirmation button:last-child',
    )!;
    confirm.click();
    fixture.detectChanges();
    expect(api.createGame).toHaveBeenCalledOnce();
    expect(api.restartGame).not.toHaveBeenCalled();
    expect(sessionStorage.getItem('kiba.activeBotGameId')).toBeNull();
    expect(sessionStorage.getItem('kiba.botSetupRequested')).toBe('true');
    expect((fixture.nativeElement as HTMLElement).querySelector('.bot-setup')).not.toBeNull();
  });

  it.each([
    [{ outcome: 'WIN', winner: 'HUMAN', winner_seat: 'one' } as const, 'Вы победили! 🏆'],
    [{ outcome: 'WIN', winner: 'BOT', winner_seat: 'two' } as const, 'Бот победил'],
    [{ outcome: 'DRAW', winner: null, winner_seat: null } as const, 'Ничья 🤝'],
  ])('renders a completed result and can play again', (result, title) => {
    create(
      makeGame({
        phase: 'complete',
        result,
        available_actions: [],
        human_hand: [sixClubs],
        table_cards: [sixClubs, queenDiamonds],
        table_arithmetic: {
          total_effective_value: 21,
          physical_card_count: 2,
          arithmetic_mean: '21/2',
        },
        packets: [
          {
            attack_cards: [sixClubs],
            attack_value: 6,
            defense_cards: [queenDiamonds],
            defense_value: 15,
            closed: true,
            throw_in_reasons: [],
          },
        ],
      }),
    );
    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain(title);
    expect(element.querySelector('app-game-table')?.textContent).toContain('Финальный кон');
    expect(element.querySelector('app-game-table')?.textContent).toContain('Атака · 6');
    expect(element.querySelectorAll('app-hand .playing-card')).toHaveLength(0);
    api.restartGame.mockReturnValue(of(makeGame({ game_id: 'game-2' })));
    clickButton('Сыграть ещё');
    expect(api.restartGame).toHaveBeenCalledWith('game-1');
    expect(sessionStorage.getItem('kiba.activeBotGameId')).toBe('game-2');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Ваш ход');
  });

  it('returns a completed result to setup without replaying or duplicating persistence', () => {
    create(
      makeGame({
        phase: 'complete',
        result: { outcome: 'WIN', winner: 'HUMAN', winner_seat: 'one' },
        result_saved: true,
        available_actions: [],
      }),
    );

    clickButton('В меню');

    expect(api.restartGame).not.toHaveBeenCalled();
    expect(api.createGame).toHaveBeenCalledOnce();
    expect((fixture.nativeElement as HTMLElement).querySelector('.bot-setup')).not.toBeNull();
  });

  it('restores a completed result and keeps Play Again available', () => {
    sessionStorage.setItem('kiba.activeBotGameId', 'completed-game');
    api.getGame.mockReturnValue(
      of(
        makeGame({
          game_id: 'completed-game',
          phase: 'complete',
          result: { outcome: 'DRAW', winner: null, winner_seat: null },
          available_actions: [],
        }),
      ),
    );

    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();

    expect(api.createGame).not.toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Ничья 🤝');
    expect(
      [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].some(
        (button) => button.textContent?.trim() === 'Сыграть ещё',
      ),
    ).toBe(true);
  });

  it('shows saved history feedback for an authenticated completed game', () => {
    create(
      makeGame({
        phase: 'complete',
        result: { outcome: 'WIN', winner: 'HUMAN', winner_seat: 'one' },
        account_associated: true,
        result_saved: true,
        available_actions: [],
      }),
    );

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Результат сохранён в статистике');
    expect(text).toContain('Открыть историю');
  });

  it('shows server-confirmed XP, level, and multiple new achievements', () => {
    create(
      makeGame({
        phase: 'complete',
        result: { outcome: 'WIN', winner: 'HUMAN', winner_seat: 'one' },
        account_associated: true,
        result_saved: true,
        progression_award: {
          base_xp: 100,
          achievement_bonus_xp: 75,
          total_awarded_xp: 175,
          total_xp: 175,
          level: 2,
          next_level_xp: 200,
          xp_needed_for_next_level: 25,
          new_achievements: [
            {
              code: 'FIRST_MATCH',
              title: 'Первая партия',
              description: 'Сыграть первую партию.',
              bonus_xp: 25,
            },
            {
              code: 'FIRST_WIN',
              title: 'Первая победа',
              description: 'Выиграть первую партию.',
              bonus_xp: 50,
            },
          ],
          new_cosmetics: [],
        },
        available_actions: [],
      }),
    );

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('+175 XP');
    expect(text).toContain('За партию 100 XP');
    expect(text).toContain('достижения +75 XP');
    expect(text).toContain('Уровень 2');
    expect(text).toContain('до следующего 25 XP');
    expect(text).toContain('Первая партия');
    expect(text).toContain('Первая победа');
  });

  it('applies server-provided card-back and table-theme variants', () => {
    create(
      makeGame({
        cosmetics: {
          card_back_code: 'SNOWBALL_BACK',
          table_theme_code: 'MATHEMATICIAN_TABLE',
          profile_frame_code: 'NO_FRAME',
        },
      }),
    );

    const shell = (fixture.nativeElement as HTMLElement).querySelector('.game-shell');
    expect(shell?.classList.contains('back-snowball')).toBe(true);
    expect(shell?.classList.contains('table-mathematician')).toBe(true);
    expect((fixture.nativeElement as HTMLElement).querySelector('.hidden-hand')).not.toBeNull();
  });

  it('shows server-confirmed newly unlocked cosmetics on the result', () => {
    create(
      makeGame({
        phase: 'complete',
        result: { outcome: 'WIN', winner: 'HUMAN', winner_seat: 'one' },
        account_associated: true,
        result_saved: true,
        available_actions: [],
        progression_award: {
          base_xp: 100,
          achievement_bonus_xp: 75,
          total_awarded_xp: 175,
          total_xp: 650,
          level: 4,
          next_level_xp: 800,
          xp_needed_for_next_level: 150,
          new_achievements: [],
          new_cosmetics: [
            {
              code: 'SNOWBALL_BACK',
              category: 'CARD_BACK',
              title: 'Снежный ком',
            },
          ],
        },
      }),
    );

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Новая награда');
    expect(text).toContain('Снежный ком');
    expect(text).toContain('Новое оформление открыто');
  });

  it('tells guests that only future games can be saved', () => {
    create(
      makeGame({
        phase: 'complete',
        result: { outcome: 'WIN', winner: 'BOT', winner_seat: 'two' },
        account_associated: false,
        result_saved: false,
        available_actions: [],
      }),
    );

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('сохранять следующие партии');
    expect(text).not.toContain('Результат сохранён');
    const actions = (fixture.nativeElement as HTMLElement).querySelector('.result-actions');
    expect(actions?.querySelector('button')?.textContent).toContain('Сыграть ещё');
    expect(actions?.querySelector('.result-register')?.textContent).toContain('Создать аккаунт');
    expect(actions?.children).toHaveLength(3);
  });

  it('keeps physical table-card ghosts visible while presenting a confirmed bot TAKE', () => {
    vi.useFakeTimers();
    try {
      create(
        makeGame({
          table_cards: [sixClubs],
          packets: [
            {
              attack_cards: [sixClubs],
              attack_value: 6,
              defense_cards: [],
              defense_value: null,
              closed: false,
              throw_in_reasons: [],
            },
          ],
        }),
      );
      api.submitAction.mockReturnValue(
        of(
          makeGame({
            table_cards: [],
            packets: [],
            last_bout_summary: { outcome: 'TAKE', actor_seat: 'two', table_card_count: 1 },
            recent_events: [
              {
                type: 'BOT_TAKE',
                actor: 'BOT',
                card_count: 4,
                value: null,
                target: 18,
              },
            ],
          }),
        ),
      );
      const firstCard = (fixture.nativeElement as HTMLElement).querySelector(
        'app-hand .playing-card',
      ) as HTMLButtonElement;
      firstCard.click();
      fixture.detectChanges();

      clickButton('Ходить');

      let element = fixture.nativeElement as HTMLElement;
      expect(element.textContent).toContain('Бот берёт 4 карты…');
      expect(element.querySelector('app-game-table')?.textContent).toContain('Стол пуст');
      expect(element.querySelectorAll('.motion-card.from-table.to-top')).toHaveLength(1);

      vi.advanceTimersByTime(1_800);
      fixture.detectChanges();
      element = fixture.nativeElement as HTMLElement;
      expect(element.querySelector('app-game-table')?.textContent).toContain('Стол пуст');
      expect(element.textContent).not.toContain('Бот берёт 4 карты…');
      expect(element.querySelector('.motion-card')).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('presents consecutive named bot actions in order while accepting the newest state immediately', () => {
    vi.useFakeTimers();
    try {
      localStorage.setItem('kiba.multiplayerOnboarding.v1', 'true');
      create(makeMultiplayerGame(4));
      const updated = makeMultiplayerGame(4, {
        required_actor: 'HUMAN',
        required_seat: 'one',
        recent_events: [
          {
            type: 'BOT_INITIAL_ATTACK',
            actor: 'BOT',
            actor_seat: 'two',
            card_count: 1,
            value: 6,
            target: null,
          },
          {
            type: 'BOT_TRANSFER',
            actor: 'BOT',
            actor_seat: 'three',
            card_count: 1,
            value: 6,
            target: 6,
          },
          {
            type: 'BOT_BITO',
            actor: 'BOT',
            actor_seat: 'four',
            card_count: 0,
            value: null,
            target: null,
          },
        ],
      });
      api.submitAction.mockReturnValue(of(updated));
      const firstCard = (fixture.nativeElement as HTMLElement).querySelector(
        'app-hand .playing-card',
      ) as HTMLButtonElement;
      firstCard.click();
      fixture.detectChanges();
      clickButton('Ходить');

      expect(TestBed.inject(GameSessionState).game()).toBe(updated);
      expect((fixture.nativeElement as HTMLElement).textContent).toContain('Milo атакует');
      vi.advanceTimersByTime(1_500);
      fixture.detectChanges();
      expect((fixture.nativeElement as HTMLElement).textContent).toContain('Nika переводит');
      vi.advanceTimersByTime(1_800);
      fixture.detectChanges();
      expect((fixture.nativeElement as HTMLElement).textContent).toContain('Otto: пас');
    } finally {
      vi.useRealTimers();
    }
  });

  it('retains the authoritative bot TAKE response when navigation interrupts presentation', () => {
    vi.useFakeTimers();
    try {
      create(
        makeGame({
          table_cards: [sixClubs],
          packets: [
            {
              attack_cards: [sixClubs],
              attack_value: 6,
              defense_cards: [],
              defense_value: null,
              closed: false,
              throw_in_reasons: [],
            },
          ],
        }),
      );
      const updated = makeGame({
        table_cards: [],
        packets: [],
        recent_events: [
          {
            type: 'BOT_TAKE',
            actor: 'BOT',
            card_count: 1,
            value: null,
            target: 6,
          },
        ],
      });
      api.submitAction.mockReturnValue(of(updated));
      const firstCard = (fixture.nativeElement as HTMLElement).querySelector(
        'app-hand .playing-card',
      ) as HTMLButtonElement;
      firstCard.click();
      fixture.detectChanges();
      clickButton('Ходить');

      fixture.destroy();

      expect(TestBed.inject(GameSessionState).game()).toBe(updated);
    } finally {
      vi.useRealTimers();
    }
  });

  it('shows bot thinking while an action request is pending', () => {
    create();
    const response = new Subject<GameResponse>();
    api.submitAction.mockReturnValue(response);
    const firstCard = (fixture.nativeElement as HTMLElement).querySelector(
      'app-hand .playing-card',
    ) as HTMLButtonElement;
    firstCard.click();
    fixture.detectChanges();

    clickButton('Ходить');

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Бот думает…');
    expect(firstCard.disabled).toBe(true);
    response.complete();
  });

  it('shows the presentation-only turn reminder only for the local actor', () => {
    vi.useFakeTimers();
    try {
      create();
      expect(
        (fixture.nativeElement as HTMLElement).querySelector('app-turn-reminder'),
      ).not.toBeNull();
      expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('Ваш ходВаш ход');

      vi.advanceTimersByTime(31_000);
      fixture.detectChanges();
      expect(api.submitAction).not.toHaveBeenCalled();
      expect(
        (fixture.nativeElement as HTMLElement).querySelector('.turn-reminder')?.textContent,
      ).toContain('Ваш ход');

      const session = TestBed.inject(GameSessionState);
      session.game.set(
        makeGame({
          required_actor: 'BOT',
          required_seat: 'two',
          available_actions: [],
        }),
      );
      fixture.detectChanges();
      expect((fixture.nativeElement as HTMLElement).querySelector('app-turn-reminder')).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('keeps elapsed time across rerenders and resets only for a new decision context', () => {
    vi.useFakeTimers();
    try {
      create();
      vi.advanceTimersByTime(20_000);
      fixture.detectChanges();
      vi.advanceTimersByTime(10_000);
      fixture.detectChanges();
      expect((fixture.nativeElement as HTMLElement).querySelector('.turn-reminder')).not.toBeNull();

      TestBed.inject(GameSessionState).game.set(
        makeGame({
          bout_phase: 'waiting_for_defender_response',
          active_attack_value: 10,
          available_actions: ['DEFEND', 'TRANSFER', 'TAKE'],
          packets: [
            {
              attack_cards: [sixClubs],
              attack_value: 6,
              defense_cards: [],
              defense_value: null,
              closed: false,
              throw_in_reasons: [],
            },
          ],
          active_packet: {
            attack_cards: [sixClubs],
            attack_value: 6,
            defense_cards: [],
            defense_value: null,
            closed: false,
            throw_in_reasons: [],
          },
        }),
      );
      fixture.detectChanges();
      expect((fixture.nativeElement as HTMLElement).querySelector('.turn-reminder')).toBeNull();
      vi.advanceTimersByTime(29_999);
      fixture.detectChanges();
      expect((fixture.nativeElement as HTMLElement).querySelector('.turn-reminder')).toBeNull();
      vi.advanceTimersByTime(1);
      fixture.detectChanges();
      expect((fixture.nativeElement as HTMLElement).querySelector('.turn-reminder')).not.toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('updates through several server states without triggering bot turns itself', () => {
    create();
    const defending = makeGame({
      human_hand: [queenDiamonds, sevenHearts],
      available_actions: ['DEFEND', 'TRANSFER', 'TAKE'],
      active_attack_value: 10,
      bout_phase: 'waiting_for_defender_response',
    });
    const decision = makeGame({
      human_hand: [sevenHearts],
      available_actions: ['THROW_IN', 'BITO'],
      bout_phase: 'waiting_for_attacker_decision',
    });
    const complete = makeGame({
      phase: 'complete',
      result: { outcome: 'WIN', winner: 'HUMAN', winner_seat: 'one' },
      available_actions: [],
    });
    api.submitAction
      .mockReturnValueOnce(of(defending))
      .mockReturnValueOnce(of(decision))
      .mockReturnValueOnce(of(complete));

    (
      (fixture.nativeElement as HTMLElement).querySelector('app-hand .playing-card') as HTMLElement
    ).click();
    fixture.detectChanges();
    clickButton('Ходить');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Нужно покрыть больше 10');
    (
      (fixture.nativeElement as HTMLElement).querySelector('app-hand .playing-card') as HTMLElement
    ).click();
    fixture.detectChanges();
    clickButton('Покрыть');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Можно подкинуть карты или объявить «Бито»',
    );
    clickButton('Бито');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Вы победили! 🏆');
    expect(api.submitAction).toHaveBeenCalledTimes(3);
  });
});
