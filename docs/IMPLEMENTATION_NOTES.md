# Cyber Durak / Kiba — Implementation Notes for Codex v0.1

## 1. Repository strategy

Use a single monorepo.

Suggested layout:

```text
cyber-durak-game/
├── frontend/
├── backend/
├── docs/
│   ├── GAME_RULES.md
│   ├── PRODUCT_BRIEF.md
│   └── IMPLEMENTATION_NOTES.md
├── tests/
├── docker/
├── .github/
│   └── workflows/
├── AGENTS.md
└── README.md
```

Do not split frontend and backend into separate repositories for the MVP.

---

## 2. Recommended stack

### Frontend

- TypeScript
- Angular
- responsive HTML/CSS
- lightweight animation layer
- PWA support later

### Backend

- FastAPI
- Python
- WebSocket for realtime multiplayer
- PostgreSQL once persistence/accounts are required

### Infrastructure

- Docker Compose for local development
- GitHub Actions for CI
- deploy as ordinary web app
- reverse proxy in production

For Alpha 1 vs bot, the game engine may initially run locally or server-side, but architecture should not prevent later authoritative multiplayer.

---

## 3. Authoritative game server

For online multiplayer, the server must be authoritative.

The client sends intent such as:

```text
play cards [card_12, card_26]
```

The server decides:

```text
legal / illegal
```

The client must never be trusted to:

- calculate final score;
- choose deck order;
- resolve trump;
- decide whether defense is legal;
- decide whether a transfer is legal;
- decide who attacks next.

---

## 4. Separate rules engine from UI

The rules engine should know nothing about Angular, DOM, animations or network transport.

Suggested conceptual modules:

```text
Card
Deck
PlayerState
TrumpState
BoutState
GameState
Move
MoveResult
```

Core functions:

```text
get_base_value(card)
get_trump_multiplier(card, trump_state)
get_effective_value(card, trump_state)

get_cards_value(cards, trump_state)

is_legal_initial_attack(...)
get_legal_throw_in_targets(...)
is_legal_throw_in(...)

is_legal_defense(...)
is_legal_transfer(...)

apply_attack(...)
apply_defense(...)
apply_transfer(...)
apply_take(...)
finish_bout(...)

refill_hands(...)
determine_next_attacker(...)
determine_winner(...)
```

---

## 5. Deterministic state machine

Suggested high-level states:

```text
WAITING_FOR_PLAYERS
DEALING
ATTACK
DEFENSE
TRANSFER
THROW_IN
TAKE
BOUT_COMPLETE
REFILL
GAME_COMPLETE
```

Exact naming can change, but legal actions must always depend on explicit game state.

Avoid implicit UI-driven state transitions.

---

## 6. Suggested game data model

### Card

```text
id
rank
suit
joker_color?
deck_instance?
```

`deck_instance` is not required for one-deck MVP but makes future multi-deck support possible.

### TrumpState

```text
source_card_id
trump_rank
trump_suit
joker_color?
active
```

### PlayerState

```text
player_id
seat
hand[]
is_connected
```

### BoutState

```text
attacker_seat
defender_seat
starting_defender_hand_size
table_cards[]
attack_value
transfer_target
trump_snapshot
status
```

### GameState

```text
game_id
players[]
draw_pile[]
discard_pile[]
bout
phase
result? (win with winner seat, or draw)
version
```

A game-level state owns the actual ordered card hands, draw pile and discard pile. `BoutState`
remains the authority for one bout's legality and tracks only numeric remaining hand counts; while
a bout is active, those counts must exactly equal the corresponding game-owned hand lengths.

A successful defense that spends the defender's final card transitions `BoutState` directly to a
BITO outcome. `GameState` immediately applies that completed bout in the same card-action
transition, so no intermediate attacker-decision state can expose another throw-in against a
zero-card defender. Winner/draw evaluation remains game-level and still runs only after discard and
refill.

Refill first calculates both seats' deficits to seven. A sufficient pile retains ordinary
attacker-first sequential refill. For an insufficient pile, the engine compares the small set of
legal two-seat draw quotas, minimizes the resulting hand-count difference, and uses the original
bout attacker's final hand count as the deterministic tie-break. Cards are then drawn from the
existing pile order, original attacker quota first; no held card is moved and hands at or above
seven receive no refill cards.

A monotonic `version` is useful for websocket reconciliation.

---

## 7. Important implementation detail: trump snapshot

The trump state must be copied into the bout when the bout begins.

Do not repeatedly derive trump from the deck while a bout is active.

Reason:

- cards may be drawn only after the bout;
- UI animation may expose changing deck state;
- replay/reconnect must reproduce exactly the same effective values.

Use:

```text
bout.trump_snapshot
```

for every card calculation during that bout.

### 7.1 New-game bootstrap

Callers start a fresh 36-card MVP match through `create_new_game(rng=...)`. The factory creates the
canonical deck, shuffles a mutable copy, and delegates the round-robin deal to `GameState.deal`.
It derives trump from the exposed front of the remaining draw pile and selects the owner of the
lowest effective-value trump in the two dealt hands as initial attacker. It returns a
`READY_FOR_BOUT` immutable state and does not start the first bout automatically.

The optional random source is a standard-library `random.Random` instance. Tests inject a seeded
instance for reproducible hands, draw pile, and any attacker fallback. After shuffle, the same
source is consumed for a 50/50 attacker choice only when both seats have equal lowest-trump values
or neither hand contains trump; a unique lowest-trump result consumes no additional randomness.
Default local play receives a new standard-library generator rather than depending on global
mutable random state. A future authoritative multiplayer layer can own and replace this source
without changing the rules engine.

---

## 8. Arithmetic engine

The arithmetic logic deserves its own module.

### Effective value

```text
effectiveValue(card) =
    baseValue(card) × multiplier(card, trump_snapshot)
```

### Table statistics

After every accepted move calculate:

```text
table_total
physical_card_count
arithmetic_mean
represented_ranks
represented_effective_values
```

The arithmetic mean should only produce an exact target if the result is representable according to the rules.

Use exact integer/rational arithmetic.

Do not use floating-point equality for legality checks.

Example:

```text
32 / 3
```

must not become a fake legal value because of rounding.

---

## 9. Combination validation

Do not implement legal combinations as a collection of UI special cases.

Build a reusable validator that can answer:

```text
Can these selected cards satisfy target value X?
```

and:

```text
Are these cards a legal initial attack structure?
```

The same core logic can be reused for:

- attack
- throw-in
- transfer
- bot planning
- tutorial hints

---

## 10. Bot architecture

Do not start with machine learning.

Start with deterministic search / heuristics.

### 10.1 Baseline policy

The baseline bot is an isolated deterministic policy in `game/bot.py`. Given the same immutable
`GameState` and bot seat, it returns the same explicit `BotAction`. `play_bot_turn` chooses and
applies exactly one action through the existing authoritative game transitions; it does not edit
hands or bout state and does not hide a recursive game loop.

Candidate ordering uses effective values from the fixed bout trump snapshot. Initial attacks only
need single-card candidates because every single card is legal and all card values are positive, so
no multi-card candidate can improve the policy's primary lowest-total criterion. For defense,
transfer, and throw-ins, a value-indexed dynamic program retains one preferred subset for each
reachable effective total. This avoids power-set growth after TAKE creates a large hand. Two
bounded rank-focused supplements cover rules that cannot be reduced to one effective total:
same-rank transfer candidates contain at most the four physical cards of the packet rank, while
rank-run throw-in candidates use at most one cheapest held card per normal rank. Every retained or
supplemental candidate is still submitted to the authoritative `GameState` action before the bot
may choose it.

The baseline prioritizes the cheapest legal defense and defends before transferring. It transfers
only when no defense exists and an exact or same-rank-extended legal transfer survives bout limits;
otherwise it takes.
After defense it chooses the cheapest legal throw-in or finishes as bito when none exists. This is a
legality-and-completion baseline, not an optimal or difficulty-ranked strategy.

### 10.2 Alpha human-versus-bot sessions and REST boundary

The Phase 3C1 application layer lives outside `kiba_api.game`. A process-local `GameSessionService`
owns opaque game identifiers, the current immutable `GameState` reference, and the fixed Alpha seat
mapping: the human is Seat ONE and the baseline bot is Seat TWO. It automatically starts ready
bouts and applies one authoritative bot action at a time until the human owns the next decision or
the game completes. Human actions and bot actions both delegate to the existing `GameState` and
`BoutState` transitions; the application and HTTP layers do not duplicate legality rules.

`InMemoryGameSessionStore` uses a repository lock for creation and lookup plus a per-session lock
for transitions, preventing two requests from applying to the same state snapshot. Sessions are
process-local and are lost whenever the backend restarts. This is intentional for Alpha; no
database, restart recovery, or distributed locking is provided.

The FastAPI boundary exposes `POST /api/games`, `GET /api/games/{game_id}`, and
`POST /api/games/{game_id}/actions`. Requests use canonical normal-card codes such as `6C`, `10H`,
`QS`, `KD`, and `AC`. Pydantic schemas explicitly translate domain snapshots: the human receives
their ordered hand and public table state, while the bot hand is represented only by a count and
the draw pile only by a count plus its single exposed top card. Bot cards, future draw-pile order,
and random-generator state never enter the response schema.

### 10.3 Alpha Angular game table

The Phase 3C2 Angular client is a thin presentation layer over the Phase 3C1 REST contract. A typed
`GameApiService` calls relative `/api` URLs; the development server proxies those requests to the
backend, while a future deployment can serve both applications behind one origin. The game page
uses focused standalone components for cards, hand selection, trump/deck status, packet-oriented
table history, exact arithmetic facts, and the action bar. Lightweight Angular signals hold the
current public snapshot, pending state, errors, and selected card codes; no separate state-management
dependency is required.

Action buttons come exclusively from the server's `available_actions`. The client may sum the
backend-supplied `effective_value` fields to explain a local selection, but it never uses that sum to
decide legality. Every move is submitted to the authoritative session API, which also performs bot
auto-advance before returning the next public snapshot. A rejected move keeps the current snapshot
and selection available for correction. The serializer contract supplies only the human hand, bot
count, draw-pile count and exposed top card, so the UI neither expects nor renders bot cards or
future draw order.

The Alpha session retains the latest resolved bout snapshot as presentation history outside
`GameState`. When a match completes, serialization uses that public snapshot to keep the decisive
table, packet structure, and exact arithmetic visible without changing game-completion semantics or
putting UI history into the rules model. Later throw-in packets also include explanation metadata
derived by the existing authoritative `analyze_throw_in` primitive. Angular renders those confirmed
reason codes and expressions after acceptance; it does not infer throw-in legality before submission.
Rank-run explanations additionally carry the server-confirmed start, end, length, and ordered ranks;
Angular renders that metadata but never derives run legality.

Human-vs-bot action responses may additionally carry a response-scoped `recent_events` trace for
confirmed bot actions. The trace contains only safe public action type/count/value metadata, is not
stored in PostgreSQL or retained by subsequent GET responses, and never drives game correctness.
Angular renders the authoritative response immediately and may retain pointer-inert visual card
ghosts long enough to explain a confirmed bot TAKE or other transition. The presentation never
delays, rejects, or creates a game action.

The shared Angular table uses a local 30-second activity perimeter only while the local participant
owns the current decision in bot and private-PvP modes. Its context key changes with authoritative
bout/packet/action state, so ordinary rerenders do not restart the cycle but a genuinely new local
decision does. At the end of one cycle it shows one localized, non-blocking turn reminder. The
feature has no server clock, timeout, forced move, penalty, or automatic action. Reduced-motion
preferences replace the draining animation with a static waiting treatment while retaining the
same delayed reminder.

Presentation intentionally suspends that reminder while a blocking New Game dialog is open or a
private-PvP opponent is disconnected. PvP card selection and action controls are also disabled
during the remote absence even though the authoritative decision snapshot is preserved. Closing
the dialog or receiving the opponent's reconnect state remounts a fresh 30-second presentation
cycle; neither transition sends or synthesizes a gameplay action.

The live game board owns the viewport-height layout: opponent, bounded active-table region, status,
hand, and actions occupy explicit grid rows. Large physical tables scroll inside the table region
rather than pushing the hand below the viewport, and the action row is never overlaid on selectable
cards. A compact `last_bout_summary` is serialized from the already-retained resolved-bout snapshot
so TAKE/BITO context remains visible after the next bout begins and through ordinary R1 refresh.
This metadata is process-local, public/presentation-only, contains no hidden cards, and does not
change rules or database state.

Opponent presentation uses a reusable table-seat model with explicit `top`, `bottom`, `left`, and
`right` positions. Current two-player Bot and PvP games populate only the local bottom hand and one
top opponent; tests exercise three- and four-seat visual maps without enabling additional players,
changing room limits, or defining multiplayer rules. Hidden hands render exactly one generic,
accessible card back per authoritative public count and never receive card identities.
Ordinary desktop top hands use the same card dimensions and open row spacing as the local hand;
overlap is reserved for mobile width, large TAKE-created hands, and constrained side seats. Seat
identity and count remain a separate header above the card backs.

A small card-motion coordinator compares consecutive public snapshots only after an accepted REST
or WebSocket transition. It combines the already-submitted local cards, safe bot presentation
events, public table-card differences, `last_bout_summary`, and draw-pile deltas into short,
pointer-inert card ghosts for play, TAKE, BITO, and refill. Refill staggering follows the previous
authoritative `bout_starting_attacker` value exposed in public state; allocation and legality remain
backend-owned. Initial GET/reconnect snapshots establish a baseline and do not replay history.
Rapid batches replace stale ghosts, and reduced-motion preferences skip flight/flip effects
entirely.

Player-facing card shorthand is formatted centrally with Unicode suit symbols. High-confidence
pre-action hints cover only server-exposed numeric defense/transfer targets and attack-card limits;
complex combination legality remains authoritative on submit. Confirmed throw-in explanations use
structured source-card metadata instead of embedding machine card codes in display strings.

### 10.4 Tutorial, rules, and product shell

The Angular shell routes `/`, `/play`, `/tutorial`, and `/rules` behind one compact navigation. A
root-scoped frontend holder retains only the latest public `GameResponse`, so visiting Tutorial or
Rules and returning to Play does not discard an active process-local session. This is convenience
state, not saved-game persistence; a browser or backend restart may still lose the Alpha session.
Every major route exposes a localized skip-to-main link and a focusable semantic main region.
Rules and Tutorial show an explicit Back to game link only when the current tab holds a recoverable
`kiba.activeBotGameId`; following it leaves that identifier untouched so `/play` performs the
existing authoritative R1 recovery rather than dealing a new game.

The root landing route shows a compact first-run orientation until the browser records
`kiba.firstRunSeen=true` in `localStorage`. Start Tutorial and Play Now both set the flag; direct
routes, bot-game recovery and PvP invite/reconnect routes never mount the Welcome. The flag contains
no account identity, cards, or game state, and clearing site data simply makes the Welcome eligible
again.

The tutorial is deterministic, scripted educational content. Quiz exercises compare the user's
choice only with an explicitly authored answer for that fixed example. One controlled defense
exercise reuses selectable card components to teach select cards, inspect their total, then press
the action; it checks only the predefined `J + 7 = 19 > 18` answer, creates no API game, and is not a
second rules engine. The nine-step flow also explains that the attack-card count is bounded by the
current defender's hand and recalculated after transfer. The EN/RU Rules page remains the complete
player-facing transformation of `GAME_RULES.md`, while real match actions continue to use
backend-provided actions and authoritative REST/WebSocket transitions.

### 10.5 Optional account identity and persistence

Phase 4A adds optional identity without placing an authentication wall in front of gameplay. The
Angular shell checks `/api/auth/me` at startup and otherwise remains in guest state; `/play` has no
route guard. Registration, login, logout, and display-name changes use a small root-scoped auth
service. Browsers retain only the HTTP-only cookie managed by the backend—passwords and session
tokens never enter frontend storage.

The persistence layer uses SQLAlchemy 2.x models and Alembic migrations against PostgreSQL. `users`
contains identity fields only, and `auth_sessions` contains a SHA-256 digest of each cryptographically
random opaque token plus expiry/revocation metadata. Passwords use Argon2id. The session cookie is
HTTP-only, same-site, scoped to `/`, configurable as Secure for HTTPS, and protected from browser
cross-site mutations through Origin/Referer validation. Registration and login also have a bounded
process-local rate limiter suitable for Alpha development. In insecure local mode, loopback and
private-LAN IP origins on the documented development ports are accepted; Secure production mode
requires an exact configured trusted origin.

Persistent account identity and active games intentionally remain separate. A process-local
`GameSession` retains the optional user UUID captured when the game is created, plus a start time
and a small set of accepted-human-action counters. Logging in during a guest game does not attach
it retroactively, and logging out does not detach a game that began authenticated.

Phase 4B records a compact `completed_matches` row only after the authoritative `GameState` first
reaches `COMPLETE`, after bout resolution, refill, and WIN/DRAW evaluation. A stable opaque game ID
has a database uniqueness constraint, while the process-local session records successful
persistence. If a write fails, the terminal game snapshot remains authoritative and a later GET
retries the same idempotent write without replaying an action. Guests skip this path entirely.

Completed rows contain outcome from the account owner's perspective, timestamps/duration, seat and
initial-attacker metadata, final hand counts, and bounded counters for accepted human actions,
transfers, takes, throw-ins, highest resulting unresolved-packet target after a transfer, and
arithmetic-mean throw-ins. Rejected moves
never affect them. `/api/stats` derives totals, percentage win rate, and win streaks from match rows
(losses and draws both break a streak); `/api/matches` returns only the current user's newest
summaries with bounded limit/offset pagination. There is no mutable aggregate stats row and no
replay payload, hidden hand, draw order, or RNG state in persistence.

`GameState`/`BoutState`, hands, deck order, and in-progress actions are still not stored in
PostgreSQL. Backend restart therefore destroys active matches. Phase 4B provides completed-match
facts that later progression may consume, but adds no XP, levels, achievements, or placeholder
schema.

### 10.6 Persistent progression

Phase 4C derives account progression only from authoritative `completed_matches`. An append-only
`xp_ledger` records base match awards and achievement bonuses with a unique `(user_id, source_key)`
constraint; `user_achievements` has a unique `(user_id, achievement_code)` constraint. These
database constraints are the final retry/idempotency protection. No mutable total-XP, level,
games-played, or wins aggregate is stored.

`ProgressionService.synchronize(user_id)` processes completed matches oldest-first by completion
time, creation time, and stable match ID. It backfills missing base XP, reconstructs chronological
counts and win streaks, records the first match satisfying each static achievement definition, and
writes its bonus XP in the same transaction. Repeated synchronization converges without duplicate
awards, including for authenticated matches completed before Phase 4C. Levels and current progress
are calculated from ledger total with the integer-safe threshold `50 × (level - 1)²`.

After a new authenticated terminal match is persisted, the completion callback synchronizes that
user and attaches a replay-safe award summary to the process-local completed session. The result
response may therefore show server-confirmed base XP, newly unlocked achievement XP, total XP, and
level without letting Angular calculate awards. Repeated result GETs can display the same summary
but cannot create ledger rows. Guests skip match persistence and progression entirely.

The static Alpha achievement catalogue lives in backend code and `/api/achievements` returns its
metadata plus per-user unlock state; Angular does not maintain a second catalogue.
`/api/progression` returns the ledger-derived level summary after retroactive synchronization. XP
and achievements cannot change gameplay. Currencies, quests, seasons, leaderboards, multiplayer
achievements, and admin configuration remain deferred.

### 10.7 Cosmetic progression rewards

Phase 4D keeps the cosmetic catalogue as static backend code. Definitions contain stable codes,
one of the three categories (`CARD_BACK`, `TABLE_THEME`, `PROFILE_FRAME`), presentation metadata,
and a default, level, or canonical-achievement requirement. The frontend consumes this catalogue
from `GET /api/cosmetics`; it does not own an independent unlock table.

`user_cosmetic_unlocks` permanently records each earned non-default cosmetic behind a unique
`(user_id, cosmetic_code)` constraint. `CosmeticService.synchronize` first converges the existing
XP/achievement progression, then backfills every currently satisfied level and achievement reward.
Repeated progression, achievement, cosmetic, and completed-result reads remain idempotent. A
one-row `user_cosmetic_loadout` stores the current choices, while default cosmetics require no
unlock rows. `PATCH /api/profile/cosmetics` accepts only known category-correct codes and verifies
the account's unlock before equipping.

The application session captures a presentation-only loadout snapshot when a new authenticated
game is created; guests receive the classic defaults. The snapshot is serialized beside public
game state and never enters `GameState` or `BoutState`. Angular applies card backs and table themes
through CSS custom properties/classes, and profile frames through the account presentation layer.
A completed authenticated session may include newly inserted cosmetic definitions in its
server-confirmed progression delta. No CSS strings, hidden cards, currency, inventory economy, or
gameplay decisions cross this boundary.

### 10.8 Process-local private multiplayer rooms

Phase 5A adds a separate `kiba_api.pvp` application layer; it does not extend the bot session or put
transport concerns into `kiba_api.game`. An `InMemoryPvPRoomStore` holds immutable room snapshots
behind a repository lock and one transition lock per room. A room assigns its creator to Seat ONE,
its joiner to Seat TWO, and creates exactly one existing `GameState` when the second participant
joins. Ready bouts are started automatically by the application layer, while every card action,
TAKE, and BITO still delegates to the shared authoritative `GameState`/`BoutState` transitions. No
bot policy is imported or invoked by a private room.

`POST /api/pvp/rooms` creates an opaque invite, `POST /api/pvp/rooms/{invite_code}/join` claims the
second seat, and `GET /api/pvp/rooms/{invite_code}` returns non-secret invitation status. Guest
requests require a trimmed visible nickname of 1–24 Unicode characters; authenticated requests use
the account display name. Creation and join responses return a participant ID and a cryptographically
random reconnect credential once. The credential is then sent in the first WebSocket `AUTH` message
to `/api/pvp/rooms/{invite_code}/ws`; it is never put in `GameState`, a database row, public state,
application logs, or a URL query string.

Every accepted WebSocket `ACTION` applies under the room lock, increments a monotonically increasing
room version once, and broadcasts a full participant-specific `STATE`. Client actions include the
version they observed, so stale submissions are rejected without mutation. Each view contains only
the requesting participant's cards, the opponent's hand count, the exposed top draw card, public
table/packet/arithmetic facts, and that participant's available actions. Opponent cards, future draw
order, reconnect credentials, and RNG state never cross the serializer boundary. `PING`/`PONG`,
connection notifications, structured rejections, complete-state messages, a bounded action rate,
and a bounded JSON message size keep the Alpha protocol explicit without changing gameplay rules.

Live sockets are tracked outside immutable room snapshots by an API connection hub. A reconnect with
the same credential restores the latest version and replaces an older socket for that participant.
Disconnect is neither a forfeit nor a bot takeover. The server preserves the authoritative decision
snapshot while the opponent is temporarily offline; the Angular client pauses local gameplay
controls and reminder presentation until the opponent returns. Browser origins use the same trusted
local/same-origin policy as authentication, and the Angular development proxy forwards WebSocket
upgrades under `/api`.

Rooms remain backend-process memory only. Lazy cleanup expires inactive waiting rooms after 30
minutes, completed rooms after 15 minutes, and fully disconnected active rooms after two hours;
connected rooms are never removed by cleanup. Backend restart still destroys every active private
room and reconnect credential. Phase 5A intentionally writes no multiplayer match history, XP, or
achievement rows and adds no database migration. Persistent/resumable rooms and multi-worker room
coordination require a later shared-state architecture.

Phase 5B adds an Angular presentation/application client without changing that protocol. `/pvp`
creates rooms, `/join/:inviteCode` handles public invite status and guest/account identity, and
`/pvp/room/:inviteCode` presents waiting and active states using the existing Kiba table components.
Invite URLs are constructed from `window.location.origin`, so same-origin HTTP and WebSocket proxying
also works from LAN hostnames. A focused native-WebSocket service sends `AUTH` first, applies only
monotonic participant-specific `STATE` snapshots, sends versioned `ACTION` messages, surfaces
rejections/connectivity, and reconnects after transient closure. The opaque reconnect credential is
stored only in `sessionStorage` under the invite code; it is never placed in a URL or rendered.

The PvP client receives its own hand and only the opponent's public name/connection state/hand
count. It does not model opponent cards or future draw order, does not optimistically mutate the
table, and drives actions exclusively from server `available_actions`. PvP rooms remain guest-first
and process-local, with no bot participation, matchmaking, chat, spectators, match persistence, XP,
statistics, or rematch protocol. A post-match “new room” starts the invitation flow again.

Phase 5C hardens this client around one constrained connection state. Unexpected closure retries at
bounded `0.5s`, `1s`, `2s`, `4s`, then `5s` intervals for at most eight attempts; a manual retry is
available after exhaustion. `visibilitychange`, `pageshow`, `offline`, and `online` feed the same
single-socket recovery path. A returning visible page health-checks the socket with existing
`PING`/`PONG`; recovery always waits for a full participant-specific authoritative `STATE` and never
resends an uncertain action. Socket-generation guards prevent handlers from a replaced connection
from changing current UI state.

The client keeps the last table visible but disables actions while its own connection is unsafe,
surfaces opponent disconnect/return separately, and retains selected cards until an authoritative
newer version proves an action was accepted. Older state versions are ignored; stale actions are
rejected and followed by the server's latest state. Explicit leave disables reconnect and clears
only that room's `sessionStorage` credential, while ordinary internal navigation preserves it.
Unlike a recoverable socket loss, a confirmed explicit leave sends one authenticated `LEAVE`
message. The room moves to neutral `CLOSED`, publishes one participant-specific terminal snapshot
to both seats, revokes both reconnect claims, and exposes no further actions or turn reminder. It
does not create a winner, completed-match row, XP, achievement, or cosmetic award. The remaining
participant sees that the opponent intentionally left and can return to the PvP lobby instead of
waiting for a reconnect that cannot happen.
Authoritative room-expired/not-found closes stop retry, clear the stale credential, and show a
terminal room-unavailable screen; invalid credentials return through public room status/join flow.
These transport changes do not alter `GameState`, gameplay versions, hidden-information boundaries,
or the process-local room TTL policy.

The local hand keeps ordinary spacing for seven cards and applies count-based overlap only as TAKE
creates larger hands. Its scroll container owns symmetric inline gutters, so the first and last card
remain inside the usable hand bounds at the resting edges; exceptionally large hands remain
internally scrollable without widening the page or overlapping the action row.

### 10.9 Persistent private-PvP results

Phase 5D extends the existing user-owned `completed_matches` stream instead of creating PvP-only
statistics or progression tables. A completed room's opaque `room_id` is its non-secret shared PvP
match identity. Each authenticated participant receives one perspective row, protected by a unique
`(user_id, pvp_match_id)` index: outcomes, final card counts, and accepted-action counters are local
to that seat. The row snapshots the opponent's public display name and nullable user ID; it never
stores email, reconnect credentials, hidden hands, draw order, or live room state. Guests create no
row and no anonymous account.

The room tracks only minimal per-seat accepted-action summaries in memory. The authoritative
completion transition persists all authenticated perspectives in one idempotent transaction, then
reuses the existing XP ledger, achievement synchronization, and cosmetic synchronization for each
user. WebSocket delivery cannot trigger persistence. Participant-specific COMPLETE serialization
repeats only the local account's saved flag and progression delta on reconnect; it never broadcasts
one participant's private progression to the opponent. History and statistics combine BOT and PVP
rows chronologically, with compact bot/PvP splits and an optional opponent-type history filter.

Room identity remains fixed at create/join: signing in or out later does not reassign a participant.
Active rooms and reconnect credentials are still process-local and disappear on restart; only
completed summaries/progression survive. Rating, ELO, matchmaking, public profiles, replay logs, and
private-room progression-abuse prevention are deliberately deferred before competitive launch.

Development Docker Compose keeps PostgreSQL private and applies migrations for convenience.

### 10.10 Phase 6A production-readiness boundary

Runtime configuration names `development`, `test`, and `production`. Production rejects local or
wildcard hosts/origins, insecure cookies, the development email sender, default database credentials,
and incomplete SMTP values. The browser boundary remains same-origin: cookie mutations and PvP
WebSockets validate configured origins, broad CORS is absent, and a Phase 6B reverse proxy is the
trusted public edge.

Email verification and recovery share a persistent `account_tokens` table. Raw random tokens exist
only in delivery links; SHA-256 digests, type, expiry, and consumption are stored. Password reset
uses Argon2id and revokes every opaque auth session. Registration remains usable after delivery
failure and unverified accounts retain gameplay access. `EmailSender` provides a development outbox
and a generic SMTP production adapter.

Production requests have UUID correlation, safe JSON logs, generic internal errors, trusted hosts,
security headers, and database readiness. Human-vs-Bot TTL cleanup joins the existing PvP cleanup
policy. The production backend is non-root and pins exactly one Uvicorn worker; the production
Angular image is static content behind unprivileged nginx with API/WebSocket proxying. Multiple
backend workers are unsafe because active games, rooms, reconnect state, and rate limits remain
process-local. Production migrations are an explicit release step. Operational details live in
`docs/PRODUCTION_READINESS.md`.

### 10.11 Runtime Russian/English localization

Player-facing localization is a presentation/application concern. One Angular build contains typed
English and Russian catalogues and switches them at runtime; routes, `GameState`, `BoutState`, REST
action codes, and the PvP WebSocket protocol remain language-neutral. A first guest visit with no
saved preference always starts in English for the EU/international release. The effective guest
choice is stored as `kiba.preferred-locale` in `localStorage`, updates `<html lang>` and browser
titles, and does not reload or replace active game/PvP state. Existing saved Russian preferences are
not reset.

Authenticated users persist constrained `users.preferred_locale` (`ru` or `en`). Registration sends
the current UI locale; `/api/auth/me` and login restore the account locale across devices. A runtime
switch applies immediately and patches the existing profile. Failure to persist is shown as a
recoverable warning while the local choice stays active; logout preserves that current guest choice.

Angular adds `Accept-Language` to HTTP requests. Backend-owned achievement and cosmetic display
metadata is localized at serialization while stable catalogue codes, database enum values, error
codes, and gameplay state remain unchanged. PvP participant identity captures locale at room
create/join only for participant-private completion metadata; the core WebSocket state is not
localized.

Verification and password-reset messages use the account's stored locale through the existing
provider-neutral development/SMTP sender seam. Request-browser language never overrides a known
account preference. Russian remains the backend compatibility fallback for absent or unsupported
request languages and for migrated existing users. Adding another locale should primarily require
a new frontend catalogue and backend catalogue/email copy, not a separate build or rules engine.

### 10.12 Phase 6A.6 privacy and account-data boundary

Public Privacy and Terms use one `/privacy` and `/terms` route with runtime EN/RU content and
centralized version/effective-date constants. The public controller is Oleg Shaltaev, Finland,
`support@cyberdurak.com`. Legal pages and registration links are public; the compact footer is
suppressed on active game/room routes so legal navigation does not disrupt play.

`GET /api/account/export` creates a versioned JSON response in memory from the authenticated user's
profile, own match summaries, XP ledger, achievements and cosmetics. It deliberately omits password
hashes, session/account-token digests, opponent UUIDs, reconnect credentials and game secrets. No
export file is persisted.

`POST /api/account/delete` requires the current password and an explicit `DELETE` confirmation.
One database transaction anonymizes the deleted identity in other users' retained PvP summaries,
removes the user's owned match/progression/auth/token/profile rows, and permits later reuse of the
email. The auth cookie is cleared only after commit. Process-local bot sessions and PvP participants
are then detached from the deleted UUID and continue as guests, preventing later persistence to a
missing user. A failed transaction rolls back without logging out the account.

No schema migration is needed: existing `ON DELETE SET NULL` opponent references and nullable
snapshot fields support anonymization, while owned records already reference the user. Active games
and rooms remain process-local. Operational policy/data inventory is maintained in the privacy,
retention, processor, incident, rights, processing-record, and legal-review documents rather than
duplicated in code.

No analytics/advertising/marketing tracker is present. The auth cookie, locale and first-run flag
in `localStorage`, and bot/PvP recovery data in `sessionStorage` are necessary/functional storage,
so no optional cookie banner is used. Any future non-essential tracking requires a fresh
consent/privacy assessment.

### 10.13 Human-vs-Bot refresh recovery

The browser stores only the current opaque bot-game ID under `kiba.activeBotGameId` in
`sessionStorage`. On `/play` initialization, Angular first requests the existing public state with
`GET /api/games/{id}` and creates no replacement game when recovery succeeds. The server remains
authoritative; hands, table state, draw order, bot cards, RNG state, and the complete `GameState`
are never stored in the browser.

A definitive `game_not_found` response clears the stale ID and presents an explicit localized
message before the player may start a new game. Network failures and 5xx responses preserve the ID
and offer recovery retry. New Game and Play Again replace the stored ID only after the new server
session is created successfully. The existing in-memory snapshot still preserves ordinary Angular
route navigation, while `sessionStorage` covers full page reload in the same tab.

This does not add active-game database persistence. Recovery ends when the six-hour active or
30-minute completed server-session TTL expires, or when the single backend process restarts. The
independent PvP reconnect credential and flow are unchanged.

Possible bot priorities:

### Defense

Find legal combinations where:

```text
sum > attack_value
```

and minimize:

```text
sum - attack_value
```

while adding a penalty for spending strategically valuable trump cards.

### Transfer

Search combinations where:

```text
sum == current_transfer_target
```

### Throw-in

Prefer moves that:

- are legal;
- use low-value cards;
- create difficult future targets;
- avoid wasting flexible arithmetic cards.

The first bot only needs to be competent enough to play legally.

Difficulty levels can come later.

---

## 11. Test strategy

The rules engine needs extensive unit tests before realtime multiplayer work.

Minimum categories:

### Card values

- every rank base value
- trump rank
- trump suit
- Joker
- no trump after deck exhaustion

### Attack

- one card
- same-rank cards
- invalid unrelated cards
- arithmetic relation
- trump-adjusted relation

### Defense

- exact equality rejected
- greater value accepted
- multi-card defense

### Throw-ins

- existing rank
- equivalent value
- total sum
- arithmetic mean
- combination satisfying mean
- recomputation after every addition
- non-integer mean

### Transfer

- exact equality
- greater value rejected
- lower value rejected
- snowball accumulation
- 18 → 36 → 72 chain

### Bout resolution

- successful defense → defender attacks next
- take → previous attacker attacks next
- attacker draws first
- refill to 7
- fixed defender starting-hand limit
- deck exhaustion

### Victory

- correct winner
- no premature winner during unresolved bout

---

## 12. Example acceptance tests

### Test: trump arithmetic relation

Given:

- Hearts are trump
- player selects `K♣` and `9♥`

Then:

- `K♣ = 18`
- `9♥ = 18`
- relation is legal

### Test: arithmetic mean throw-in

Given table:

- `J = 12`
- `K = 18`

Then:

- total = 30
- card count = 2
- mean = 15
- `Q = 15` is legal
- `7 + 8 = 15` is also legal

### Test: snowball transfer

Given:

- Player A attacks for 18
- Player B transfers exactly 18

Then:

- next transfer target = 36

When Player C transfers exactly 36:

- next transfer target = 72

---

## 13. UX-engine contract

The backend/rules engine should expose enough information for the UI to explain moves.

Example move-preview response:

```json
{
  "legal": true,
  "selected_value": 15,
  "reason": {
    "type": "ARITHMETIC_MEAN",
    "expression": "30 / 2 = 15"
  }
}
```

Example defense preview:

```json
{
  "legal": false,
  "selected_value": 32,
  "required": {
    "operator": ">",
    "value": 36
  }
}
```

The frontend should not reverse-engineer legality from raw state.

---

## 14. Reconnect and realtime design

For multiplayer:

- every committed action increments game version;
- clients receive complete enough authoritative state to recover;
- server rejects stale or illegal actions;
- reconnect must restore the current bout;
- timers, if later added, belong to server state.

Do not build timers into Alpha 1.

---

## 15. Security / fairness

For real multiplayer:

- shuffle only on server;
- use secure random source;
- never send opponents' hidden cards to clients;
- validate every action server-side;
- use opaque room/player tokens;
- rate-limit room creation and action spam;
- keep server logs sufficient to debug desyncs.

---

## 16. Suggested implementation phases

### Phase 0 — repository bootstrap

- repo conventions
- frontend/backend skeletons
- linting
- formatting
- tests
- CI
- Docker Compose
- docs checked in

### Phase 1 — deterministic rules engine

- card/deck model
- scoring
- trump snapshot
- attack validation
- defense
- throw-ins
- arithmetic mean
- transfer
- bout resolution
- unit tests

No UI polish yet.

### Phase 2 — bot + local playable game

- bot
- game orchestration
- responsive table UI
- move previews
- explanations
- new game
- basic tutorial

### Phase 3 — private multiplayer

- WebSocket rooms
- nickname join
- invite links
- reconnect
- authoritative server
- basic production deployment

### Phase 4 — playtest improvements

- instrumentation
- UX polish
- balance changes
- 3–4 player support
- 54-card/Joker mode

### Phase 5 — growth / monetization only if justified

- accounts
- matchmaking
- stats
- ranking
- cosmetics
- ads
- premium

---

## 17. Codex working style

Do not ask Codex to "build the whole game" in one task.

Use narrow feature prompts with acceptance criteria.

Example:

```text
Implement card value and trump calculation according to docs/GAME_RULES.md.

Requirements:
- pure deterministic functions
- no UI dependencies
- unit tests for every rank
- tests for trump suit and trump rank
- trump multiplier is x2
- no trump when TrumpState.active is false
- do not implement multi-deck x3 yet

Run the test suite and report changed files.
```

Then move feature by feature.

---

## 18. Source-of-truth hierarchy

When implementation and documentation disagree:

1. `docs/GAME_RULES.md` controls gameplay behavior.
2. `docs/PRODUCT_BRIEF.md` controls MVP/product scope.
3. `docs/IMPLEMENTATION_NOTES.md` controls preferred architecture.
4. Existing code should be changed to match the above unless a deliberate spec update is made first.

Any rule change discovered during playtesting should be documented before or together with the code change.
