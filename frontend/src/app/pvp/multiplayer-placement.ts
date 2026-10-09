import { Seat } from '../core/api/game-api.models';

export interface MultiplayerPlacement {
  readonly seat: Seat;
  readonly rank: number;
}

export function deriveMultiplayerPlacements(
  finishGroups: readonly (readonly Seat[])[],
): readonly MultiplayerPlacement[] {
  const placements: MultiplayerPlacement[] = [];
  let rank = 1;
  for (const group of finishGroups) {
    for (const seat of group) placements.push({ seat, rank });
    rank += group.length;
  }
  return placements;
}
