# Private PvP protocol

This document describes the backend room and WebSocket contract. The current Angular client still
creates only two-player rooms; three- and four-player rooms are backend-only integration capability
until a later UI phase.

## Room lifecycle

`POST /api/pvp/rooms` accepts the existing optional `nickname` and an optional `capacity` of `2`,
`3`, or `4`. Omitting `capacity` preserves the existing two-player behavior. Capacity is immutable.
The creator receives canonical seat `one`; later joins receive the lowest unoccupied canonical seat.
The room remains `WAITING_FOR_OPPONENT` until joined count equals capacity and then starts exactly
one authoritative generalized game with the same seat ring.

`POST /api/pvp/rooms/{invite_code}/join` cannot overfill a room. One authenticated account cannot
claim two participant identities in the same waiting room. `GET /api/pvp/rooms/{invite_code}` and
join/create snapshots add `capacity`, `joined_count`, stable `seat_order`, and ordered public player
descriptors.

Before a three- or four-player match starts, explicit `LEAVE` releases that participant's lobby
seat when another participant remains, emits `PARTICIPANT_LEFT`, and lets a later join claim the
lowest free seat. A creator alone, every two-player Exit, and every Exit after a match starts use the
existing neutral `CLOSED` lifecycle. Closing is not FINISH, never adds a finish group, and creates
no competitive result.

## Identity, reconnect, and transport

Connection, participant identity, reconnect credential, canonical seat, and engine actor are
separate values. A reconnect credential restores the same participant and seat; replacing a socket
does not reassign gameplay order. Several participants may be disconnected simultaneously without
freeing seats or changing the game. A canonically finished participant stays in the room, may keep
observing public updates, and has no available action.

Every `ACTION` is resolved from the authenticated participant credential to its owned seat. Clients
do not submit a trusted role or actor seat. The engine remains authoritative for turn and action
legality. The room lock and expected `version` preserve atomic application: one accepted action
increments the version once, while stale, replayed, wrong-turn, or illegal actions do not mutate the
snapshot.

State changes are broadcast to every connected room participant, but the server serializes a fresh
private projection for each recipient. Existing message names (`STATE`, `GAME_COMPLETE`,
`OPPONENT_CONNECTED`, `OPPONENT_DISCONNECTED`, and rejection types) remain unchanged. Connection
events add the affected `participant_id` and canonical `seat` so a future multiplayer client can
identify which peer changed state.

## Projection and results

Each `STATE` retains the legacy two-player `you`, `opponent`, `opponent_hand_count`, and binary
`result` fields. For a two-player room they keep their previous meaning. Additive generalized fields
are:

- `capacity`, `joined_count`, and canonical `seat_order`;
- ordered `players`, with public hand count, connected, active, finished, and `is_self` state;
- `active_seats`, `finished_seats`, and ordered `finish_groups`;
- `lead_attacker`, alongside the existing current bout `attacker`, `defender`, and required actor.

The viewer receives exact cards only for their own hand. Other participants expose counts only.
Future draw-pile cards, private RNG state, reconnect credentials, account IDs, and other secrets are
never serialized. The already-public exposed top draw card and table/discard metadata remain public.

Two-player completion continues to expose the legacy `WIN`/`DRAW` result and uses the existing
authenticated match-history/progression recorder. Three- and four-player completion exposes
canonical ordered finish groups and deliberately has no binary result or persistence write. No
database schema or migration is involved.

## Deferred multiplayer product behavior

Hints and rematch consent remain available only for capacity two. A three- or four-player
`HINT_REQUEST` is rejected as `FEATURE_NOT_AVAILABLE`; rematch messages are rejected as
`REMATCH_NOT_AVAILABLE`. There are no bots, matchmaking, ratings, external spectators, or durable
active-room storage. Rooms and reconnect credentials remain process-local and are lost on backend
restart.

## Test matrix

The backend matrix covers default/invalid 2–4 capacity, waiting/start/full rooms, lowest-free and
concurrent final-seat assignment, account duplicate prevention, all-seat reconnect, simultaneous
disconnects, cleanup, pre-start and active Exit, private projections for three and four seats,
nested hidden-card/deck/token checks, valid/wrong/stale/concurrent actions, initial attack, defense,
wrapped transfer, non-cycling attacker handoff, TAKE, BITO, 4→3→2 finish reduction, simultaneous
finish groups, real REST/WebSocket broadcasts, and the existing two-player guest, persistence,
hint, rematch, and reconnect suites.
