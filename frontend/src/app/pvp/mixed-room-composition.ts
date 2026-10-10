export type RoomPlayerCount = 2 | 3 | 4;

export function humanPlayerOptions(totalPlayers: RoomPlayerCount): readonly RoomPlayerCount[] {
  if (totalPlayers === 2) return [2];
  if (totalPlayers === 3) return [2, 3];
  return [2, 3, 4];
}

export function nextHumanPlayerCount(
  previousTotal: RoomPlayerCount,
  previousHumans: RoomPlayerCount,
  nextTotal: RoomPlayerCount,
): RoomPlayerCount {
  if (previousHumans === previousTotal) return nextTotal;
  return Math.min(nextTotal, Math.max(2, previousHumans)) as RoomPlayerCount;
}
