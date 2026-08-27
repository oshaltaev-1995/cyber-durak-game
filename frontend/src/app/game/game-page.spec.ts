import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';
import { GameCard, GameResponse } from '../core/api/game-api.models';
import { GameApiService } from '../core/api/game-api.service';
import { AuthService } from '../core/auth/auth.service';
import { GamePageComponent } from './game-page';

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
  phase: 'bout_active',
  result: null,
  human_seat: 'one',
  bot_seat: 'two',
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
  required_actor: 'HUMAN',
  required_seat: 'one',
  available_actions: ['INITIAL_ATTACK'],
  ...overrides,
});

interface ApiStub {
  createGame: ReturnType<typeof vi.fn<() => Observable<GameResponse>>>;
  getGame: ReturnType<typeof vi.fn<(id: string) => Observable<GameResponse>>>;
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
    api = {
      createGame: vi.fn(),
      getGame: vi.fn(),
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
    expect(element.textContent).toContain('Партия против бота');
    expect(element.textContent).toContain('Ваш ход');
  }, 15_000);

  it('keeps the active public game snapshot when the routed page is recreated', () => {
    create();
    fixture.destroy();

    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();

    expect(api.createGame).toHaveBeenCalledOnce();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Бот · 6 карт');
  });

  it('creates and renders a public human-vs-bot state without hidden cards', () => {
    create();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(api.createGame).toHaveBeenCalledOnce();
    expect(
      (fixture.nativeElement as HTMLElement).querySelectorAll('app-hand .playing-card'),
    ).toHaveLength(3);
    expect(text).toContain('Бот · 6 карт');
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

    expect(element.querySelector('.opponent-zone')?.textContent).toContain('Бот · 6 карт');
    expect(element.querySelectorAll('.opponent-zone .opponent-card-backs i')).toHaveLength(3);
    expect(stage.querySelector('.draw-zone .deck-count')?.textContent).toContain('21');
    expect(stage.querySelectorAll('.draw-zone app-playing-card')).toHaveLength(1);
    expect(stage.querySelector(':scope > app-game-table.center-table')).not.toBeNull();
    expect(stage.querySelector('.discard-zone')?.textContent).toContain('Бито');
    expect(stage.querySelector('.discard-zone')?.textContent).toContain('16');
    expect(stage.textContent).not.toContain('Порядок колоды');
  });

  it('keeps the turn status next to the player interaction region', () => {
    create();
    const element = fixture.nativeElement as HTMLElement;
    const status = element.querySelector('.status-banner') as HTMLElement;
    const hand = element.querySelector('.player-hand-region') as HTMLElement;

    expect(status.textContent).toContain('Ваш ход');
    expect(status.compareDocumentPosition(hand) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0);
  });

  it('selects cards, sends canonical codes, and clears selection after success', () => {
    create();
    const updated = makeGame({ human_hand: [queenDiamonds, sevenHearts] });
    api.submitAction.mockReturnValue(of(updated));
    const firstCard = (fixture.nativeElement as HTMLElement).querySelector(
      'app-hand .playing-card',
    ) as HTMLButtonElement;
    firstCard.click();
    fixture.detectChanges();
    expect(firstCard.getAttribute('aria-pressed')).toBe('true');

    clickButton('Ходить');
    expect(api.submitAction).toHaveBeenCalledWith('game-1', 'INITIAL_ATTACK', ['6C']);
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.selection-summary')?.textContent,
    ).toContain('Выбрано: 0');
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

  it('asks before replacing an active game', () => {
    create();
    clickButton('Новая игра');

    const dialog = (fixture.nativeElement as HTMLElement).querySelector('[role="alertdialog"]');
    expect(dialog?.textContent).toContain('Текущая партия будет потеряна');
    expect(api.createGame).toHaveBeenCalledOnce();

    clickButton('Отмена');
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alertdialog"]')).toBeNull();
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
    expect(element.querySelectorAll('app-hand .playing-card')).toHaveLength(1);
    api.createGame.mockReturnValue(of(makeGame({ game_id: 'game-2' })));
    clickButton('Сыграть ещё');
    expect(api.createGame).toHaveBeenCalledTimes(2);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Ваш ход');
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
      'Можно подкинуть карты или закончить кон',
    );
    clickButton('Бито');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Вы победили! 🏆');
    expect(api.submitAction).toHaveBeenCalledTimes(3);
  });
});
