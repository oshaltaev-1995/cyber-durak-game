import { ChangeDetectionStrategy, Component, input } from '@angular/core';
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
}
