import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DeckCount, DeckProfile } from '../api/game-api.models';
import { TranslationService } from '../i18n/translation.service';
import { deckCardCount } from './deck-config';

@Component({
  selector: 'app-deck-config-selector',
  imports: [RouterLink],
  templateUrl: './deck-config-selector.html',
  styleUrl: './deck-config-selector.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DeckConfigSelectorComponent {
  protected readonly i18n = inject(TranslationService);
  readonly profile = input.required<DeckProfile>();
  readonly deckCount = input.required<DeckCount>();
  readonly playerCount = input<2 | 3 | 4>(2);
  readonly profileChange = output<DeckProfile>();
  readonly deckCountChange = output<DeckCount>();
  protected readonly total = computed(() => deckCardCount(this.profile(), this.deckCount()));
  protected readonly profiles = ['classic', 'extended'] as const;
  protected readonly deckCounts = [1, 2] as const;
}
