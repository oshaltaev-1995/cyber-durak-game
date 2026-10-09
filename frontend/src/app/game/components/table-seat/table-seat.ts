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
    if (count > 12) return 'hand-huge';
    if (count > 9) return 'hand-large';
    if (count > 7) return 'hand-crowded';
    return 'hand-normal';
  });

  protected readonly roleLabels = computed(() => {
    const seat = this.seat();
    const labels: string[] = [];
    if (seat.defender) labels.push(this.i18n.t('pvp.defender'));
    if (seat.currentAttacker) labels.push(this.i18n.t('pvp.currentAttacker'));
    if (seat.leadAttacker && !seat.currentAttacker) labels.push(this.i18n.t('pvp.leadAttacker'));
    if (seat.required) labels.push(this.i18n.t('pvp.currentTurn'));
    if (seat.finished) labels.push(this.i18n.t('pvp.finishedPlayer'));
    if (seat.connected === false) labels.push(this.i18n.t('pvp.disconnectedPlayer'));
    return labels;
  });

  protected readonly accessibleLabel = computed(() => {
    const seat = this.seat();
    return [
      this.i18n.t('game.hiddenHandLabel', { name: seat.displayName, count: seat.cardCount }),
      ...(seat.isBot ? [this.i18n.t('game.botAccessible')] : []),
      ...this.roleLabels(),
    ].join('. ');
  });
}
