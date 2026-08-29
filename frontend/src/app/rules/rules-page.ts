import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { GameCard } from '../core/api/game-api.models';
import { TranslationService } from '../core/i18n/translation.service';
import { PlayingCardComponent } from '../game/components/playing-card/playing-card';

const card = (
  code: string,
  rank: string,
  suit: GameCard['suit'],
  baseValue: number,
  effectiveValue = baseValue,
  isTrump = false,
): GameCard => ({
  code,
  rank,
  suit,
  base_value: baseValue,
  effective_value: effectiveValue,
  is_trump: isTrump,
});

@Component({
  selector: 'app-rules-page',
  imports: [PlayingCardComponent, RouterLink],
  templateUrl: './rules-page.html',
  styleUrl: './rules-page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RulesPageComponent {
  protected readonly i18n = inject(TranslationService);
  protected readonly trumpExamples = [
    card('7S', '7', 'spades', 7, 14, true),
    card('8H', '8', 'hearts', 8, 16, true),
    card('8C', '8', 'clubs', 8),
  ];
  protected readonly meanExamples = [
    card('JC', 'J', 'clubs', 12),
    card('KD', 'K', 'diamonds', 18),
    card('QS', 'Q', 'spades', 15),
  ];
}
