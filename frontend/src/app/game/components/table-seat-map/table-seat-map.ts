import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { HiddenTableSeat } from '../../presentation/table-seat.models';
import { TableSeatComponent } from '../table-seat/table-seat';

@Component({
  selector: 'app-table-seat-map',
  imports: [TableSeatComponent],
  templateUrl: './table-seat-map.html',
  styleUrl: './table-seat-map.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TableSeatMapComponent {
  readonly seats = input.required<readonly HiddenTableSeat[]>();
  readonly terminal = input(false);
  protected readonly hasTopSeat = computed(() =>
    this.seats().some((seat) => seat.position === 'top'),
  );
  protected readonly hasSideSeats = computed(() =>
    this.seats().some((seat) => seat.position === 'left' || seat.position === 'right'),
  );
}
