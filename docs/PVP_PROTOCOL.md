# Private PvP protocol

This document describes the backend room and WebSocket contract. The Angular client can create and
render private two-, three-, and four-player rooms when the server capability is enabled. The
three-/four-player product remains disabled by default until staged rollout.

## Feature capability

`KIBA_MULTIPLAYER_3_4_ENABLED` and `KIBA_DECK_VARIANTS_ENABLED` both default to `false`.
`GET /api/capabilities` exposes those two booleans and no environment contents. The first gate
controls capacity `3`/`4`; the second controls every configuration except CLASSIC ×1. The gates are
independent: for example, two-player EXTENDED requires only the deck gate, while three-player
EXTENDED requires both. Omitted configuration and explicit CLASSIC ×1 remain accepted when the
deck gate is off. Rejections use `FEATURE_NOT_AVAILABLE`.

## Room lifecycle

`POST /api/pvp/rooms` accepts the existing optional `nickname`, an optional `capacity` of `2`, `3`,
or `4`, and optional `deck_profile` (`classic`/`extended`) and `deck_count` (`1`/`2`). Omitting the
new fields means CLASSIC ×1 and preserves existing behavior. Capacity and deck configuration are
immutable room properties; joiners never choose or replace them.
The creator receives canonical seat `one`; later joins receive the lowest unoccupied canonical seat.
The room remains `WAITING_FOR_OPPONENT` until joined count equals capacity and then starts exactly
one authoritative generalized game with the same seat ring.

`POST /api/pvp/rooms/{invite_code}/join` cannot overfill a room. One authenticated account cannot
claim two participant identities in the same waiting room. `GET /api/pvp/rooms/{invite_code}` and
join/create snapshots add `capacity`, `joined_count`, stable `seat_order`, and ordered public player
descriptors.

When the room fills, the authoritative `GameState` is created from the room's exact profile and
copy count. Reconnect returns the same live state and physical card identities. A unanimous
rematch retains the room configuration while creating a new game object, shuffle, and `match_id`.
If a live release gate is later disabled, an active match may finish, but a new non-default
rematch is rejected without changing the completed result.

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

Card actions accept exactly one reference form. Existing CLASSIC ×1 clients may continue sending
face codes in `cards` (`JD`, `KS`, `10C`). Generalized clients send exact match-scoped physical IDs
in `card_ids`. Supplying both forms is invalid. Legacy face references are not accepted outside
CLASSIC ×1, and an ID is rejected if it is nonexistent, repeated, in another hand, on the table, in
discard, or in the draw pile. Thus duplicate faces can never resolve to an arbitrary copy.

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
- authoritative `deck_profile` and `deck_count`;
- ordered `players`, with public hand count, connected, active, finished, and `is_self` state;
- `active_seats`, `finished_seats`, and ordered `finish_groups`;
- `lead_attacker`, alongside the existing current bout `attacker`, `defender`, and required actor.
- participant-relative `rematch_status`, ready/total counts, and ordered public participant IDs
  that have accepted the current rematch proposal.

Every visible card adds `id` while retaining the existing `code`. Normal codes remain unchanged;
Jokers use stable non-translated codes `RJ` and `BJ`, `rank: "JOKER"`, nullable `suit`, and explicit
`joker_color`. The ID is a protocol reference and must not be rendered as a deck-copy label. Two
visible duplicate faces have the same code and distinct IDs. Own-hand cards, the exposed top card,
and table cards include IDs. The viewer receives exact cards only for their own hand. Other
participants expose counts only.
Future draw-pile cards, private RNG state, reconnect credentials, account IDs, and other secrets are
never serialized. The already-public exposed top draw card and table/discard metadata remain public.

Two-player CLASSIC ×1 completion continues to expose the legacy `WIN`/`DRAW` result and uses the
existing authenticated match-history/progression recorder. Three- and four-player completion
exposes canonical ordered finish groups and retains its no-progression policy. Every non-default
deck configuration skips history, XP, W/L/D statistics, achievements, rating, and other progression
for both bot and PvP play. No database schema or migration is involved.

## Multiplayer product behavior

Hints remain available only for capacity two across all four deck configurations. Requests may use
legacy `selected_card_ids` only for CLASSIC ×1 or exact `selected_physical_ids` generally. Responses
retain the legacy face-code fields and add exact physical-ID fields for selected, suggested, and
combination cards. A three- or four-player `HINT_REQUEST` is rejected as
`FEATURE_NOT_AVAILABLE`. After a terminal result, existing `REMATCH_REQUEST`, `REMATCH_ACCEPT`,
`REMATCH_DECLINE`, and `REMATCH_CANCEL` messages support every room capacity. A request counts as
the requester's consent; all original stable-seat participants, including early finishers, must
accept before a fresh match starts. Decline clears the proposal without changing the completed
result, requester cancel clears the proposal, duplicate acceptance is idempotent, and disconnect/reconnect
preserves recorded intent. The rematch keeps room identity, participants, seats and reconnect
credentials and deck configuration, but creates a fresh `GameState`, physical deck, shuffle and
`match_id`. Relevant live gates are rechecked before the new match starts.

Three-/four-player matches and their rematches deliberately write no history, XP, statistics,
achievements, or ratings. Two-player CLASSIC ×1 exactly-once persistence is unchanged. There are no
bots, matchmaking, external spectators, or durable active-room storage. Rooms and reconnect
credentials remain process-local and are lost on backend restart.

## Test matrix

The backend matrix covers default/invalid 2–4 capacity and deck configuration, waiting/start/full
rooms, lowest-free and concurrent final-seat assignment, account duplicate prevention, all-seat
reconnect, simultaneous
disconnects, cleanup, pre-start and active Exit, private projections for three and four seats,
nested hidden-card/deck/token checks, valid/wrong/stale/concurrent actions, initial attack, defense,
wrapped transfer, non-cycling attacker handoff, TAKE, BITO, 4→3→2 finish reduction, simultaneous
finish groups, feature-gate bypass rejection, real REST/WebSocket broadcasts, unanimous three- and
four-player rematch, and the existing two-player guest, persistence, hint, rematch, and reconnect
suites. Deck integration additionally covers two-player EXTENDED action/defense/reconnect,
three-player EXTENDED street/handoff, four-player EXTENDED ×2 with 108-card conservation and
WebSocket action broadcast, exact duplicate selection, hidden-ID rejection, all-config rematches,
live-gate rechecks, and non-default persistence exclusion.
