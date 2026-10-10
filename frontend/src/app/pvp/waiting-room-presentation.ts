import { Seat } from '../core/api/game-api.models';
import { PvPParticipant } from '../core/pvp/pvp.models';

const CANONICAL_SEATS: readonly Seat[] = ['one', 'two', 'three', 'four'];

export interface WaitingRoomSeat {
  readonly seat: Seat;
  readonly participant: PvPParticipant | null;
  readonly humanSeat: boolean;
}

export function waitingRoomSeats(
  capacity: 2 | 3 | 4,
  humanPlayers: 2 | 3 | 4,
  participants: readonly PvPParticipant[],
  seatOrder: readonly Seat[] = CANONICAL_SEATS.slice(0, capacity),
): readonly WaitingRoomSeat[] {
  return seatOrder.slice(0, capacity).map((seat, index) => ({
    seat,
    participant: participants.find((participant) => participant.seat === seat) ?? null,
    humanSeat: index < humanPlayers,
  }));
}
