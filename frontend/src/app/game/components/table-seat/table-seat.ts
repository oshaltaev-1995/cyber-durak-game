import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { TranslationService } from '../../../core/i18n/translation.service';
import { HiddenTableSeat } from '../../presentation/table-seat.models';

@Component({
  selector: 'app-table-seat',
  templateUrl: './table-seat.html',
  styleUrl: './table-seat.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TableSeatComponent {
  protected readonly i18n = inject(TranslationService);
  readonly seat = input.required<HiddenTableSeat>();

  protected readonly cardIndexes = computed(() =>
    Array.from({ length: Math.max(0, this.seat().cardCount) }, (_, index) => index),
  );

  protected readonly sizeClass = computed(() => {
    const count = this.seat().cardCount;
    if (count > 14) return 'hand-huge';
    if (count > 9) return 'hand-large';
    return 'hand-normal';
  });
}
