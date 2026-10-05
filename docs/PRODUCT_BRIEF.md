# Cyber Durak / Kiba — Product Brief v0.1

## 1. Working identity

Repository:

`cyber-durak-game`

Historical / internal game name:

**Kiba**

Possible future public name can be decided later.

For now:

- repository name = `cyber-durak-game`
- gameplay codename = `Kiba`

---

## 2. Product idea

A lightweight browser-based card game inspired by Durak but built around a custom arithmetic ruleset:

- dynamic trump rank + suit;
- point values for every card;
- arithmetic combinations;
- total-sum and arithmetic-mean throw-ins;
- snowball transfers;
- quick shedding-game objective.

The game should work well on:

- desktop browsers;
- mobile browsers;
- installable PWA later if useful.

The strongest product advantage of the web version is that the software can calculate combinations automatically and make a rule-heavy physical card game easy to understand.

### 2.1 Current launch positioning

The current target is an **EU/international portfolio public beta** with planned production
infrastructure in the Netherlands/EEA. English is the primary/default language for new visitors;
Russian remains an explicitly selectable secondary language. Existing saved guest and account
preferences are preserved.

The launch is not intentionally marketed to the Russian market: there is no VK Play integration,
Russian payment flow, `.ru` product domain, or RF production/data region. Availability of Russian
copy does not by itself define market targeting. Russian-market/data-residency obligations must be
reassessed before any deliberate RF-market launch, VK Play publication, RF-targeted marketing, or
RF-specific infrastructure.

---

## 3. Core product principle

The first goal is **not monetization**.

The first goal is to answer:

> Is Kiba fun enough that people want to immediately play another match?

Everything else depends on this.

---

## 4. MVP

### Alpha 1

- 36-card deck
- 2-player game
- one human vs bot
- complete core rules
- responsive desktop/mobile UI
- complete English and Russian player-facing UI with an instant runtime language switch; English
  is the first-visit default
- New Game
- short interactive rules/tutorial
- optional arithmetic hints, enabled by default and switchable off during play
- no account required; optional profile identity is available without gating play
- authenticated completed matches have private history and lightweight statistics; guest matches
  remain unsaved
- authenticated completed matches grant exactly-once XP, derived levels, and a small Alpha
  achievement catalogue; guest play remains registration-free and does not persist progression
- authenticated progression unlocks a small visual-only Alpha catalogue of card backs, table
  themes, and profile frames; guests use the default appearance

### Alpha 2

- private online rooms
- create room
- share invite link
- join with nickname
- no mandatory registration
- reconnect support
- authoritative two-participant WebSocket gameplay
- participant-specific state that never exposes the opponent hand or future draw order
- authenticated private-PvP results participate in the same history, statistics, XP, achievement,
  and cosmetic progression as bot results; guest PvP remains unsaved
- after a normal completed match, either participant may request a rematch; a fresh match starts in
  the same room only after both participants consent, while decline and explicit Exit preserve their
  distinct non-gameplay meanings
- optional hints use ordinary Unicode suit notation and give a deterministic, truthful explanation;
  a mixed selection whose ranks all occur in the latest defense is not described as one same-rank
  group
- Russian and English use the same routes, authoritative gameplay, and one frontend build

Example flow:

`Create Game → Copy Link → Friend Opens → Nickname → Play`

The Alpha 2 private-room slice is deliberately process-local: it provides private room
creation/join, a responsive Angular invite and game flow, guest or optional-account display
identity, browser-session reconnect credentials, authoritative two-seat WebSocket action routing,
and complete WIN/DRAW matches. Active rooms are lost on backend restart, while completed
authenticated participant summaries and progression survive. Each rematch completion is an
independent history/progression event with its own match identity. Matchmaking, rating, chat,
spectators, persistent active rooms, and distributed room infrastructure remain later work.

R10 closes the post-v1 two-player polish cycle. Its hint-explanation, card-notation, and rematch
transition corrections do not change move legality or introduce any 3–4-player behavior.

---

## 5. Later product layers

Only after the core game is proven:

- accounts
- profiles
- friends
- matchmaking
- rating / ELO
- richer match analytics and replay history
- leaderboards
- richer achievements and achievement notifications
- daily challenges
- private tournaments
- replays
- spectator mode
- richer custom tables and card backs
- avatars
- seasonal cosmetics
- optional 54-card mode
- alternative rulesets

---

## 6. UX principles

### 6.1 Never force arithmetic homework

The player should understand the mathematics but should not need to calculate everything manually.

Example attack display:

`J + J + 6 + 6`

`12 + 12 + 6 + 6 = 36`

When the defender selects cards:

`32  ✕ Need > 36`

then:

`38  ✓ Can defend`

### 6.2 Show why a move is legal

Examples:

`9 + 9 = 18 = K`

`J(12) + K(18) = 30`

`30 / 2 = 15 = Q`

This is important because the game is unfamiliar.

### 6.3 Mobile-first interaction

The base interaction should work with taps.

Drag-and-drop may be optional enhancement, not a requirement.

### 6.4 Fast start

A new player should be able to open the game and start playing against a bot within seconds.

### 6.5 No forced signup for friend games

Private-room invites should work without account creation.

Accounts become useful later for ranking, history and cosmetics.

---

## 7. Bot importance

A bot is required early because small multiplayer games suffer from the cold-start problem:

`no players → empty matchmaking → new player leaves`

The bot also provides a low-friction tutorial environment.

Bot decisions can later become an interesting optimization problem:

- find legal combinations;
- minimize overpayment when defending;
- preserve valuable trump cards;
- plan future arithmetic chains;
- decide when to transfer vs defend;
- choose strategically useful throw-ins.

---

## 8. Monetization hypothesis

This is better described as an **indie multiplayer web game** than a mini-SaaS.

Potential monetization after retention is proven:

- interstitial ads between matches;
- rewarded ads only for optional bonuses;
- one-time remove-ads purchase;
- cosmetics;
- premium private-room features;
- tournament tools;
- optional lightweight subscription much later.

Avoid:

- pay-to-win;
- ads during active bouts;
- paywalls before the game is proven.

---

## 9. Distribution hypothesis

Start with a standalone website.

Later possible channels:

- direct web/PWA
- CrazyGames
- Poki
- itch.io
- Android wrapper/app
- iOS app if audience justifies it

Distribution work should come after the core loop is fun and stable.

---

## 10. Success metrics for early testing

Before monetization, watch:

- tutorial completion
- first match completion
- immediate rematch rate
- average matches per session
- average session length
- bot win/loss distribution
- where players make illegal-move mistakes
- whether arithmetic hints are understood
- invite-link conversion for friend matches

A strong early signal would be:

> People finish one game and voluntarily start another.

---

## 11. Initial scope boundaries

Not in Alpha 1:

- account-gated gameplay
- progression that changes gameplay strength
- payments
- ads
- marketplace
- ranking
- tournaments
- chat
- social feed
- clans
- native mobile apps
- elaborate 3D graphics

### 11.1 Alpha progression values

Authenticated completed matches grant base XP from the persisted human result:

- win: 100 XP;
- draw: 50 XP;
- loss: 25 XP.

Level is derived from total XP with the threshold `50 × (level - 1)²`; it is not stored as mutable
account state. The Alpha achievement bonuses are:

- `FIRST_MATCH`: 25 XP;
- `FIRST_WIN`: 50 XP;
- `TEN_GAMES`: 100 XP;
- `TEN_WINS`: 150 XP;
- `WIN_STREAK_3`: 100 XP;
- `SNOWBALL_36`: 75 XP;
- `AVALANCHE_72`: 150 XP;
- `ARITHMETIC_MEAN`: 75 XP.

XP, levels, achievements, and cosmetic choices are profile metadata only. They do not affect
shuffle, hands, trump, card values, available moves, or bot strength. Alpha has no currency, shop,
battle pass, purchases, or gameplay advantage.

### 11.2 Alpha cosmetic catalogue

The visual-only Alpha catalogue is deliberately small and backend-owned:

- card backs: `CLASSIC`, Level 3 `LEVEL_3_BACK`, `SNOWBALL_BACK` for `SNOWBALL_36`, and
  `AVALANCHE_BACK` for `AVALANCHE_72`;
- table themes: `CLASSIC_TABLE`, Level 4 `NIGHT_TABLE`, and `MATHEMATICIAN_TABLE` for
  `ARITHMETIC_MEAN`;
- profile frames: `NO_FRAME`, Level 2 `LEVEL_2_FRAME`, and `WINNER_FRAME` for `TEN_WINS`.

Default cosmetics remain available to every player. Authenticated unlocks are permanent and
loadouts persist; guests always use the classic defaults. Cosmetics are rewards from the existing
level/achievement system, not an economy.

The project should prove the game before becoming a platform.
