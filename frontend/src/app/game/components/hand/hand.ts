import { ChangeDetectionStrategy, Component, inject, input, output } from '@angular/core';
import { GameCard } from '../../../core/api/game-api.models';
import { PlayingCardComponent } from '../playing-card/playing-card';
import { TranslationService } from '../../../core/i18n/translation.service';
import { cardIdentity } from '../../../core/deck/deck-config';

@Component({
  selector: 'app-hand',
  imports: [PlayingCardComponent],
  templateUrl: './hand.html',
  styleUrl: './hand.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HandComponent {
  protected readonly i18n = inject(TranslationService);
  readonly cards = input.required<readonly GameCard[]>();
  readonly selectedIds = input.required<ReadonlySet<string>>();
  readonly suggestedIds = input<ReadonlySet<string>>(new Set());
  readonly disabled = input(false);
  readonly cardSelected = output<string>();
  protected readonly identity = cardIdentity;
}
