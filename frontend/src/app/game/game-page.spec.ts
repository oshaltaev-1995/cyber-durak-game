import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Observable, of, throwError } from 'rxjs';
import { GameCard, GameResponse } from '../core/api/game-api.models';
import { GameApiService } from '../core/api/game-api.service';
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
      providers: [{ provide: GameApiService, useValue: api }],
    }).compileComponents();
    fixture = TestBed.createComponent(GamePageComponent);
    fixture.detectChanges();
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
    clickButton('Играть');
  };

  it('shows the initial playable landing screen', () => {
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('h1')?.textContent).toBe('KIBA');
    expect(element.textContent).toContain('Арифметический карточный дурак');
    expect(element.querySelector('button')?.textContent?.trim()).toBe('Играть');
  });

  it('creates and renders a public human-vs-bot state without hidden cards', () => {
    create();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(api.createGame).toHaveBeenCalledOnce();
    expect(
      (fixture.nativeElement as HTMLElement).querySelectorAll('app-hand .playing-card'),
    ).toHaveLength(3);
    expect(text).toContain('Бот · 6 карт');
    expect(text).toContain('в колоде 21');
    expect(text).toContain('♥ и все 7');
    expect(text).toContain('Ходить');
    expect(text).not.toContain('Скрытая карта бота');
    expect(text).not.toContain('Порядок колоды');
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
    expect(text).toContain('Среднее 21/2');
    expect(text).toContain('Покрыть > 18');
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

  it.each([
    [{ outcome: 'WIN', winner: 'HUMAN', winner_seat: 'one' } as const, 'Вы победили! 🏆'],
    [{ outcome: 'WIN', winner: 'BOT', winner_seat: 'two' } as const, 'Бот победил'],
    [{ outcome: 'DRAW', winner: null, winner_seat: null } as const, 'Ничья 🤝'],
  ])('renders a completed result and can play again', (result, title) => {
    create(makeGame({ phase: 'complete', result, available_actions: [] }));
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(title);
    api.createGame.mockReturnValue(of(makeGame({ game_id: 'game-2' })));
    clickButton('Сыграть ещё');
    expect(api.createGame).toHaveBeenCalledTimes(2);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Ваш ход');
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
