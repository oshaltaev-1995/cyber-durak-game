export type TableSeatPosition = 'top' | 'bottom' | 'left' | 'right';

export interface HiddenTableSeat {
  readonly id: string;
  readonly position: Exclude<TableSeatPosition, 'bottom'>;
  readonly displayName: string;
  readonly cardCount: number;
  readonly badge: string;
}
