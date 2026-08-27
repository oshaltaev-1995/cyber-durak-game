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
reachable effective total. This avoids power-set growth after TAKE creates a large hand. Every
retained candidate is still submitted to the authoritative `GameState` action before the bot may
choose it.

The baseline prioritizes the cheapest legal defense and defends before transferring. It transfers
only when no defense exists and an exact legal transfer survives bout limits; otherwise it takes.
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

### 10.4 Tutorial, rules, and product shell

The Angular shell routes `/`, `/play`, `/tutorial`, and `/rules` behind one compact navigation. A
root-scoped frontend holder retains only the latest public `GameResponse`, so visiting Tutorial or
Rules and returning to Play does not discard an active process-local session. This is convenience
state, not saved-game persistence; a browser or backend restart may still lose the Alpha session.

The tutorial is deterministic, scripted educational content. Each exercise compares the user's
choice only with an explicitly authored answer for that fixed example. It does not calculate trump,
attack, defense, throw-in, mean, transfer, or winner legality and is not a second rules engine. The
Russian Rules page is a player-facing transformation of `GAME_RULES.md`, while real match actions
continue to use backend-provided actions and authoritative REST transitions.

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
`GameSession` may retain an optional user UUID when an authenticated account creates it, but
`GameState`/`BoutState`, hands, deck order, and in-progress actions are not stored in PostgreSQL.
Backend restart therefore still destroys active matches. Phase 4B may record completed match
history and statistics; Phase 4A does not create counters, XP, achievements, or placeholder data.

Docker Compose keeps PostgreSQL on its private service network and applies `alembic upgrade head`
before FastAPI starts. Production deployment must supply external database credentials, HTTPS with
Secure cookies, explicit trusted origins, robust distributed rate limiting, email verification,
password reset, account deletion/data export, secrets management, and database backups.

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
