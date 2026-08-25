import { ChangeDetectionStrategy, Component } from '@angular/core';
import { GamePageComponent } from './game/game-page';

@Component({
  imports: [GamePageComponent],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {}
