import { ChangeDetectionStrategy, Component, inject, input, output } from '@angular/core';
import {
  HintCombination,
  HintReasonType,
  HumanActionType,
} from '../../../core/api/game-api.models';
import { TranslationService } from '../../../core/i18n/translation.service';
import { TranslationKey } from '../../../core/i18n/translations/ru';

@Component({
  selector: 'app-hint-panel',
  templateUrl: './hint-panel.html',
  styleUrl: './hint-panel.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HintPanelComponent {
  protected readonly i18n = inject(TranslationService);
  readonly enabled = input.required<boolean>();
  readonly loading = input(false);
  readonly combinations = input<readonly HintCombination[]>([]);
  readonly enabledChange = output<boolean>();

  protected reason(reason: HintReasonType): string {
    return this.i18n.t(`hints.reason.${reason}` as TranslationKey);
  }

  protected action(action: HumanActionType): string {
    return this.i18n.t(`action.${action}` as TranslationKey);
  }

  protected equation(hint: HintCombination): string {
    return hint.target_value === null
      ? `Σ ${hint.selected_value}`
      : `Σ ${hint.selected_value} → ${hint.target_value}`;
  }
}
