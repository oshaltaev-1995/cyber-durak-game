import { Seat } from '../../core/api/game-api.models';

export type TableSeatPosition = 'top' | 'bottom' | 'left' | 'right';
export type RemoteTableSeatPosition = Exclude<TableSeatPosition, 'bottom'>;

export interface HiddenTableSeat {
  readonly id: string;
  readonly seat?: Seat;
  readonly position: RemoteTableSeatPosition;
  readonly displayName: string;
  readonly cardCount: number;
  readonly badge: string;
  readonly isBot?: boolean;
  readonly connected?: boolean;
  readonly active?: boolean;
  readonly finished?: boolean;
  readonly currentAttacker?: boolean;
  readonly leadAttacker?: boolean;
  readonly defender?: boolean;
  readonly required?: boolean;
}

export function relativeSeatPosition(
  seatOrder: readonly Seat[],
  viewer: Seat,
  seat: Seat,
): TableSeatPosition {
  const viewerIndex = seatOrder.indexOf(viewer);
  const seatIndex = seatOrder.indexOf(seat);
  if (viewerIndex < 0 || seatIndex < 0 || seatOrder.length < 2 || seatOrder.length > 4) {
    throw new Error('seats must belong to a canonical 2-4 seat ring');
  }
  const offset = (seatIndex - viewerIndex + seatOrder.length) % seatOrder.length;
  if (offset === 0) return 'bottom';
  if (seatOrder.length === 2) return 'top';
  if (offset === 1) return 'left';
  if (seatOrder.length === 3) return 'top';
  return offset === 2 ? 'top' : 'right';
}
