import { Injectable, signal } from '@angular/core';
import { GameResponse } from '../core/api/game-api.models';

@Injectable({ providedIn: 'root' })
export class GameSessionState {
  readonly game = signal<GameResponse | null>(null);
}
