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
- New Game
- short interactive rules/tutorial
- automatic arithmetic hints
- no account required; optional profile identity is available without gating play
- authenticated completed matches have private history and lightweight statistics; guest matches
  remain unsaved

### Alpha 2

- private online rooms
- create room
- share invite link
- join with nickname
- no mandatory registration
- reconnect support

Example flow:

`Create Game → Copy Link → Friend Opens → Nickname → Play`

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
- achievements
- daily challenges
- private tournaments
- replays
- spectator mode
- custom tables
- card backs
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
- XP, levels or achievements
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

The project should prove the game before becoming a platform.
