import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { GameCard, GameResponse, HumanActionType } from '../core/api/game-api.models';
import { GameApiService } from '../core/api/game-api.service';
import { AuthService } from '../core/auth/auth.service';
import { ActionBarComponent } from './components/action-bar/action-bar';
import { GameTableComponent } from './components/game-table/game-table';
import { HandComponent } from './components/hand/hand';
import { TrumpIndicatorComponent } from './components/trump-indicator/trump-indicator';
import { GameSessionState } from './game-session-state';

const ERROR_MESSAGES: Readonly<Record<string, string>> = {
  illegal_initial_attack: 'Эти карты нельзя объединить для первого хода.',
  illegal_defense: 'Недостаточно очков для покрытия текущей атаки.',
  illegal_transfer: 'Перевод должен точно совпадать со значением атаки.',
  illegal_throw_in: 'Эти карты сейчас нельзя подкинуть.',
  attack_card_limit_exceeded: 'Превышен лимит атакующих карт в этом коне.',
  card_not_owned: 'Выбранной карты больше нет в вашей руке.',
  not_human_turn: 'Сейчас ход бота. Обновите состояние игры.',
  game_complete: 'Эта игра уже завершена.',
};

@Component({
  selector: 'app-game-page',
  imports: [
    ActionBarComponent,
    GameTableComponent,
    HandComponent,
    RouterLink,
    TrumpIndicatorComponent,
  ],
  templateUrl: './game-page.html',
  styleUrl: './game-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GamePageComponent implements OnInit {
  private readonly api = inject(GameApiService);
  private readonly session = inject(GameSessionState);
  protected readonly auth = inject(AuthService);

  protected readonly game = this.session.game;
  protected readonly pending = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly restartConfirmation = signal(false);
  protected readonly selectedCodes = signal<ReadonlySet<string>>(new Set());
  protected readonly selectedCards = computed<readonly GameCard[]>(() => {
    const selected = this.selectedCodes();
    return this.game()?.human_hand.filter((card) => selected.has(card.code)) ?? [];
  });
  protected readonly statusText = computed(() => this.getStatusText());

  ngOnInit(): void {
    if (this.game() === null) {
      this.startNewGame();
    }
  }

  protected requestNewGame(): void {
    if (!this.pending()) {
      this.restartConfirmation.set(true);
    }
  }

  protected cancelNewGame(): void {
    this.restartConfirmation.set(false);
  }

  protected startNewGame(): void {
    if (this.pending()) {
      return;
    }
    this.restartConfirmation.set(false);
    this.pending.set(true);
    this.errorMessage.set(null);
    this.api
      .createGame()
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (game) => {
          this.game.set(game);
          this.selectedCodes.set(new Set());
        },
        error: (error: unknown) => this.errorMessage.set(this.messageForError(error)),
      });
  }

  protected toggleCard(code: string): void {
    if (this.pending()) {
      return;
    }
    this.selectedCodes.update((current) => {
      const updated = new Set(current);
      if (updated.has(code)) {
        updated.delete(code);
      } else {
        updated.add(code);
      }
      return updated;
    });
    this.errorMessage.set(null);
  }

  protected submitAction(action: HumanActionType): void {
    const game = this.game();
    if (game === null || this.pending() || !game.available_actions.includes(action)) {
      return;
    }
    this.pending.set(true);
    this.errorMessage.set(null);
    this.api
      .submitAction(
        game.game_id,
        action,
        this.selectedCards().map((card) => card.code),
      )
      .pipe(finalize(() => this.pending.set(false)))
      .subscribe({
        next: (updatedGame) => {
          this.game.set(updatedGame);
          this.selectedCodes.set(new Set());
        },
        error: (error: unknown) => this.errorMessage.set(this.messageForError(error)),
      });
  }

  protected resultTitle(game: GameResponse): string {
    if (game.result?.outcome === 'DRAW') {
      return 'Ничья 🤝';
    }
    return game.result?.winner === 'HUMAN' ? 'Вы победили! 🏆' : 'Бот победил';
  }

  private getStatusText(): string {
    if (this.pending()) {
      return 'Бот думает…';
    }
    const game = this.game();
    if (game === null) {
      return 'Новая партия ждёт вас';
    }
    if (game.phase === 'complete') {
      return 'Партия завершена';
    }
    if (game.available_actions.includes('INITIAL_ATTACK')) {
      return 'Ваш ход — выберите карты для атаки';
    }
    if (game.available_actions.includes('DEFEND')) {
      return game.active_attack_value === null
        ? 'Ваш ход — ответьте на атаку'
        : `Нужно покрыть больше ${game.active_attack_value}`;
    }
    if (game.available_actions.includes('THROW_IN')) {
      return 'Можно подкинуть карты или закончить кон';
    }
    return game.required_actor === 'BOT' ? 'Бот ходит…' : 'Ваш ход';
  }

  private messageForError(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const body = error.error as { detail?: { code?: string } } | null;
      const code = body?.detail?.code;
      if (code !== undefined && ERROR_MESSAGES[code] !== undefined) {
        return ERROR_MESSAGES[code];
      }
      if (error.status === 0) {
        return 'Сервер недоступен. Проверьте, что backend запущен, и попробуйте снова.';
      }
    }
    return 'Ход не принят. Измените выбор карт и попробуйте снова.';
  }
}
