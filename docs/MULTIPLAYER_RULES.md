# KIBA 2–4 Player Canon

> Status: **M1 canonical freeze with D1 deck-variant amendment**. This document is the authoritative
> multiplayer extension of [`GAME_RULES.md`](GAME_RULES.md). D1 adds the configurations in
> [`DECK_VARIANTS.md`](DECK_VARIANTS.md) and corrects initial-street legality without changing the
> remaining two-to-four-player state machine. It specifies rules only; implementation is not implied.

## 1. Scope and compatibility

Canonical game size is **2–4 players**. The first future implementation target is private human PvP
for two, three, or four players. Matchmaking, public lobbies, ratings, and three- or four-player bots
are outside this canon.

Unless this document explicitly generalizes a role, order, refill, or outcome rule, all rules from
`GAME_RULES.md` remain unchanged:

- one selected canonical profile/deck-count configuration and seven-card initial hands;
- rank values and effective values;
- exposed-suit-or-rank dual trump and the ×2 trump multiplier;
- single-card, same-rank, arithmetic, and contiguous-street initial attacks;
- strictly greater, selection-local irredundant defense;
- exact and same-rank-extension transfers with snowball accumulation;
- latest-defense ranks and values, latest-defense total, table total, arithmetic mean, and rank-run
  throw-ins;
- the shared dynamic attack-card limit;
- TAKE, BITO, and final-card automatic BITO;
- refill after table movement and finish evaluation only after refill;
- no trump after the draw pile is exhausted.

Every calculation uses the bout's fixed trump snapshot. Cards, packets, table statistics, and
legality retain their meanings from the two-player canon.

## 2. Normative terminology

| Term                            | Canonical meaning                                                                                                                                               |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **seat**                        | A stable position in the match's fixed clockwise ring. A seat is never renumbered because another player finishes.                                              |
| **active player**               | A player still participating in play. An active player may temporarily have no cards during a bout.                                                             |
| **finished player**             | A player who, after complete bout resolution and refill with an empty draw pile, has zero cards. Finished players are skipped thereafter.                       |
| **bout starter**                | The original lead attacker at bout start. This identity is immutable for the bout and anchors refill order even if transfers later change the lead or defender. |
| **lead attacker**               | The anchor of attacking-phase order for the current bout. The lead may change only when a transfer makes the existing lead the new defender.                    |
| **current attacker**            | The active non-defender whose attacking phase currently owns the decision.                                                                                      |
| **defender**                    | The one active player responsible for the unresolved packet. Exactly one defender exists during an active bout.                                                 |
| **attacker order**              | The lead attacker followed clockwise by every other active non-defender exactly once, skipping the defender and finished seats.                                 |
| **attacking phase**             | One attacker's non-cycling opportunity after successful defense. The attacker may create multiple sequential legal batches before passing.                      |
| **closed attacking phase**      | A phase ended by pass, choice not to continue, no legal addition, no held cards, or exhausted capacity. It never reopens during that bout.                      |
| **initial attack window**       | The lead attacker's one opportunity to commit the complete initial-attack batch before the defender first responds.                                             |
| **attack batch**                | All cards committed together by one attacker action. The batch is complete before the defender begins responding.                                               |
| **unresolved packet**           | The one attack batch currently awaiting defense, transfer, or TAKE. At most one packet is unresolved.                                                           |
| **defender tenure**             | The period for which one player remains defender. A transfer ends one tenure and starts another.                                                                |
| **`bout_attack_cap`**           | The defender's hand size at the start of their current defender tenure. It is one shared attacking-card budget.                                                 |
| **`max_add_now`**               | The maximum number of attacking cards permitted in the next batch: `min(remaining_bout_capacity, defender_current_hand_size)`.                                  |
| **intended next lead attacker** | The player nominated by TAKE or BITO before refill and finish evaluation; finished seats may cause the final lead to advance.                                   |
| **refill order**                | An immutable bout-start snapshot: bout starter first, other players who began the bout as attackers clockwise, initial defender last.                           |
| **finish group**                | One ordered outcome tier. Players who become empty at the same resolution share one group; a sole remaining player is appended as the terminal loser group.     |

“Current attacker” is not a synonym for “lead attacker.” The lead anchors the bout, while current
attacker advances through the attacker order after the first successful defense.

## 3. Seat ring and active traversal

Players occupy one immutable clockwise ring. Every rule that moves between players uses:

> next active player clockwise

Finished seats are skipped transparently and never receive gameplay actions. For seats
`A → B → C → D → A`, if C has finished, every later traversal is `A → B → D → A`. This primitive
governs the next defender, transfer destination, attacker order, post-bout initiative, and later
play after finish groups are recorded.

Seat identity remains stable when the active count falls from four to three to two. There is no
rules-level reseating.

## 4. Match setup and first roles

### 4.1 Initial deal

Deal seven cards to each player round-robin in clockwise seat order from the selected 36-, 54-,
72-, or 108-card configuration. The remaining draw pile and exposed top card retain their existing
meanings.

### 4.2 Initial lead attacker

Inspect every player's initial hand for trump cards and compare those cards by effective value.

1. The holder of the unique lowest effective trump is initial lead attacker.
2. If multiple players share the lowest effective value, choose randomly among only those tied
   players.
3. If no player holds a trump, choose randomly among all active players.

This is the existing two-player selection rule generalized from two hands to all hands.

### 4.3 Initial defender and attackers

The initial defender is the next active player clockwise after the lead attacker. Every other
active non-defender is an additional attacker, but attackers act through ordered phases rather than
simultaneously.

For `A → B → C → D`, if A leads, B defends and attacker order is `A → C → D`.

### 4.4 Immutable refill order

At bout start, capture refill order from the initial roles:

1. the bout starter;
2. every other player who begins the bout as an attacker, clockwise from the bout starter;
3. the initial defender last.

For `A → B → C → D`, if A starts and B initially defends, refill order is
`A → C → D → B`. The snapshot is fixed for the whole bout. Transfers may change the current
defender, current lead attacker, and attacking-phase order, but never refill order.

## 5. Bout opening, batches, and attacker phases

### 5.1 Lead-only initial attack

Only the lead attacker owns the initial attack window. They commit one complete batch satisfying
the existing initial-attack rules, including the recovered contiguous-street basis defined in
`DECK_VARIANTS.md`. No additional attacker may add a card before the defender's first response.

When the defender begins responding, the initial attack window closes permanently for that bout.
An unplayed card cannot later be justified by saying it belonged to the initial arithmetic,
same-rank, or street relationship.

The card is not banned for the bout. It may be used later if it independently satisfies a current
post-defense reason: latest-defense rank or value, latest-defense total, table total, arithmetic
mean, rank run, or another existing canonical throw-in reason.

Example: A holds `9, 9, K, K`, initially commits `9 + 9 + K`, and retains one K. After the defender
responds, the retained K is outside the closed initial relationship. It becomes playable only if a
new current table reason makes it legal.

### 5.2 Atomic attack batches

An attacker selects and commits the complete batch before the defender responds. Once response
begins, no card may be appended to that batch. A later successful defense may create a new
throw-in opportunity, but that is a new packet and new batch.

### 5.3 Non-cycling attacking phases

After the first successful defense, the lead attacker owns the first attacking phase. During one
phase the same attacker may repeat:

1. commit one legal throw-in batch;
2. allow the defender to cover that packet;
3. use the newly recalculated table state to commit another legal batch.

The phase closes when the attacker passes, chooses not to continue, has no legal addition, holds no
cards, the shared cap is exhausted, or the bout terminates. No meaningless manual pass is required
when no legal action exists; rules-level priority simply advances.

After a phase closes, priority moves to the next active non-defender clockwise whose phase has not
closed. Priority never cycles back. A relationship created later by C or D cannot restore A's
closed phase.

When the last attacker phase closes, or every remaining phase has no legal action, the fully
covered table becomes ordinary BITO. In a multiplayer UI, one attacker's pass is therefore not
itself BITO while later attackers remain eligible.

## 6. Shared dynamic attack limit

At the beginning of each defender tenure:

```text
bout_attack_cap = defender hand size at the role change
```

All attackers share that single cap. Defense cards never count as attacking cards.

Before every new attacking batch:

```text
remaining_bout_capacity = bout_attack_cap - attack_cards_already_played
max_add_now = min(remaining_bout_capacity, defender_current_hand_size)
```

The batch size must not exceed `max_add_now`. `attack_cards_already_played` includes the initial
attack and every transfer or throw-in card counted in the current defender context. After the first
successful defense, the same cap continues across all attackers and all later packets while that
defender remains.

Example: B begins with seven cards, so the cap is seven. A, C, and D legally add three, two, and one
attacking cards across their phases. Six shared slots are used; only one remains. They do not each
receive seven slots.

If B has only one card when three shared slots remain, `max_add_now = 1` for every attacker.

## 7. Defender response

For every unresolved packet the defender may use only actions available under the existing canon.

### 7.1 Defense

Selected defense cards must satisfy:

```text
defense total > packet attack target
```

and every selected card must be necessary:

```text
defense total - effective value of each selected card <= packet attack target
```

Packets remain independent. The number of attackers does not weaken strict-greater or irredundant
defense.

### 7.2 Final-card defense

If a successful defense uses the defender's final card or cards, the bout immediately becomes
BITO. Every current or later attacking phase is cancelled; no throw-in is permitted. Match finish
is still evaluated only after table movement, refill, and final deck state.

### 7.3 TAKE

TAKE is immediately terminal for the whole bout:

- the attack window closes;
- every unplayed attacker phase is cancelled;
- no “throw cards in on the way home” action exists;
- every physical table card moves to the defender;
- refill and finish evaluation follow.

Cards an attacker wanted to add had to be legally committed before TAKE.

## 8. Transfers

Transfer is available only before the first successful defense, exactly as in the current canon.
Ordinary transfer cards total the current accumulated target exactly; the existing same-rank
extension is unchanged. Every accepted transfer joins the same unresolved packet and increases its
snowball target.

### 8.1 Destination and uninterrupted chain

The destination is the next active player clockwise after the current defender. The destination
becomes the new defender. A legal new defender may transfer again to the next active player.

No unrelated attacker phase occurs between transfers. The unresolved packet must continue through
transfer, defense, or TAKE until the chain ends.

### 8.2 New defender limit

When transfer changes defender:

```text
new bout_attack_cap = new defender current hand size
```

The entire current unresolved packet, including the proposed transfer cards, must fit this new
cap. Otherwise the transfer is rejected atomically and the existing defender and packet remain.
Later additions use the normal `max_add_now` formula against the new tenure.

### 8.3 Lead attacker through a chain

The existing lead attacker remains lead while still a non-defender. If the chain makes that player
the new defender, the player who performed that transfer becomes the new lead attacker.

Example:

```text
seats: A → B → C → D
A attacks B
B transfers to C
C transfers to D
D transfers to A
```

The final defender is A and the new lead attacker is D.

Once the final defender successfully defends, attacker order is built from the final lead. In the
example it is `D → B → C`; A is skipped as defender. If the original lead never became defender,
the original lead still acts first, followed clockwise by all other non-defenders.

## 9. Shared table mathematics

Every physical card accumulated during a bout belongs to one public shared table, regardless of
which attacker played it. Attacker handoff never resets the table.

- table total includes all physical table cards;
- arithmetic mean includes all physical table cards;
- rank-run analysis includes all physical table ranks and uses the selected profile's linear order;
- latest-defense anchors are the latest successful defense cards;
- latest-defense total is the total of that latest defense packet.

The next attacker may use any relationship currently authorized by this shared state. Closed
initial-attack relationships and closed attacker phases do not reopen.

Future multiplayer Hint Mode must derive suggestions from this same canonical state, including
current attacker, waiting attackers, closed phases, shared cap, defender hand count, transfer
destination, and finish state. M1 does not implement hints.

## 10. Bout resolution and next initiative

### 10.1 TAKE

After TAKE, the intended next lead attacker is the next active player clockwise after the final
defender. With two players this is the other player—the existing attacker.

### 10.2 BITO

After ordinary or final-card BITO, the intended next lead attacker is the final defender. Their
next defender would be the next active player clockwise.

### 10.3 Post-finish correction

The intended lead is only a pre-refill nomination. After refill and finish evaluation, if that
player has finished, advance clockwise to the next active player. If the match has ended, there is
no next lead.

## 11. Refill

Refill occurs only after the bout is terminal and TAKE/BITO table movement is complete.

### 11.1 Immutable refill order

Use the refill-order snapshot captured at bout start:

1. original bout-starting attacker first;
2. the other players who began the bout as attackers, clockwise;
3. the initial defender last.

Every player who was active at bout start appears once whether or not they played a card. Players
at seven or more cards have zero need and draw nothing. A temporarily empty player remains active
and eligible because finishing has not yet been evaluated.

With `A → B → C → D`, bout starter A and initial defender B produce refill order
`A → C → D → B`. If a full transfer chain makes D the current lead and A the final defender, refill
remains `A → C → D → B`. Transfers never mutate or recompute the snapshot.

### 11.2 Sufficient deck

If the draw pile can satisfy every deficit to seven, each eligible player receives their full
deficit in refill order.

### 11.3 Insufficient-deck balanced quotas

If the pile is insufficient, determine quotas before drawing physical cards:

1. Record every active player's current hand size and deficit to seven.
2. Allocate one quota card to the currently smallest eligible hand still below seven.
3. When several smallest hands tie, choose the earliest player in refill order.
4. Repeat until every remaining card has a quota or every eligible hand reaches seven.
5. Draw actual cards from the front of the pile in refill order, giving each player their entire
   quota before advancing.

This distributes all available cards, never refills above seven, minimizes final hand-size spread,
breaks every tie deterministically, and preserves attacker-first physical draw priority. A hand
already above seven is not reduced.

### 11.4 Exact two-player reduction

The same iterative algorithm produces the existing examples when refill order is the original
attacker followed by the initial defender:

- `3 / 5`, four cards → quotas `3 / 1` → `6 / 6`;
- `4 / 5`, four cards → quotas `3 / 1` → `7 / 6` because refill-first wins the final tie;
- `6 / 3`, three cards → quotas `0 / 3` → `6 / 6`.

The newly exposed card after refill defines the next bout's trump. If refill empties the pile, the
next bout has no trump.

## 12. Finish evaluation and match outcome

### 12.1 Timing and finish condition

No player leaves during an unresolved bout. Evaluate finish only after:

1. TAKE or BITO resolution;
2. table-card movement;
3. complete refill;
4. final draw-pile state.

An active player becomes finished only when the draw pile is empty and their hand is empty at that
evaluation. Temporary zero cards during attack or defense do not finish the player.

### 12.2 Simultaneous finishers

All players satisfying the condition at one evaluation form one finish group and leave active
rotation together. The group is appended after all earlier groups; seat order does not split the
tie.

Example: A and B become empty together while C and D retain cards. The first group is `[A, B]`,
and play continues with C and D.

### 12.3 Match end and terminal loser group

After recording simultaneous finishers:

- if two or more active players remain, play continues;
- if no active players remain, the match ends with the simultaneous group just recorded;
- if exactly one active player remains with cards, the match ends without solo play and that player
  is appended as the terminal loser group.

The terminal remaining player did not “finish” by shedding; the final group is an outcome
assignment needed to complete placement. This distinction keeps the finish condition exact.

If all remaining active players become empty together, they share the same final group and there is
no unique loser. Do not invent a tie-break from attacker role, seat order, action timing, or refill
priority.

Finish groups are ordered semantic tiers, not UI wording. For example:

```text
[[A, B], [C], [D]]
```

means A and B share the first tier, C is next, and D is the terminal loser. Conversely,
`[[A], [B], [C, D]]` has no unique final loser because C and D emptied simultaneously.

## 13. Two-player reduction

When only two active players remain, the generalized state machine is the current two-player game:

- attacker order contains one attacker and one defender;
- there are no additional-attacker phases;
- one attacker's pass ends a fully covered bout as BITO;
- TAKE nominates the other player, which is the existing attacker;
- BITO nominates the defender;
- a transfer sends the packet to the only other active player, swapping defender roles;
- refill order is the immutable original bout-starting attacker then initial defender, including
  after a transfer reverses the current roles;
- balanced refill produces the current quotas exactly;
- one empty hand produces winner and terminal loser groups;
- two empty hands produce one tied final group, equivalent to the existing DRAW.

Active-count reduction from three to two does not select a second ruleset. It continues through the
same clockwise traversal and state machine.

## 14. Formal bout state machine

```text
BOUT START
  establish lead attacker
  defender = next active clockwise
  capture immutable refill order from initial roles
  establish defender tenure and shared cap
        ↓
INITIAL ATTACK WINDOW (lead only, one complete batch)
        ↓
DEFENDER RESPONSE (one unresolved packet)
  ├─ TRANSFER (only before first successful defense)
  │    destination = next active clockwise
  │    validate/reset new defender cap
  │    preserve lead, unless lead becomes defender
  │          ↓
  │    DEFENDER RESPONSE (same accumulated packet)
  │
  ├─ TAKE
  │          ↓
  │    TERMINAL TAKE RESOLUTION
  │
  └─ DEFEND
       ├─ defender used final card(s)
       │          ↓
       │    TERMINAL BITO RESOLUTION
       │
       └─ packet closes; transfer closes permanently
                  ↓
CURRENT ATTACKER PHASE (starts at final lead)
  ├─ legal THROW-IN BATCH
  │          ↓
  │    DEFENDER RESPONSE
  │      ├─ TAKE → TERMINAL TAKE RESOLUTION
  │      └─ DEFEND
  │           ├─ final-card defense → TERMINAL BITO RESOLUTION
  │           └─ return to SAME current attacker phase
  │
  └─ PASS / NO LEGAL MOVE / NO CAPACITY / NO CARDS
             close this phase permanently
                  ↓
       NEXT UNFINISHED ATTACKER PHASE
          ├─ exists → CURRENT ATTACKER PHASE
          └─ none   → TERMINAL BITO RESOLUTION

TERMINAL RESOLUTION
        ↓
TABLE MOVEMENT
        ↓
REFILL QUOTAS AND PHYSICAL DRAW
        ↓
FINISH-GROUP EVALUATION
        ↓
CORRECT INTENDED NEXT LEAD FOR FINISHED SEATS
        ↓
NEXT BOUT OR MATCH END
```

## 15. Domain invariants for M2

1. An active bout has exactly one defender.
2. Lead attacker and defender are different active seats.
3. Current attacker is active, is not defender, and owns the only attacking decision.
4. Finished players never receive actions and every clockwise traversal skips them.
5. The initial attack belongs only to the lead and is one complete batch.
   A qualifying initial street is one allowed basis for that batch.
6. At most one packet is unresolved.
7. A batch cannot change after defender response begins.
8. A closed attacking phase never reopens or cycles back.
9. Total attacking cards never exceed the current `bout_attack_cap`.
10. A new batch never exceeds `max_add_now`.
11. All attackers share the current defender tenure's cap.
12. Defense is strictly greater and selection-local irredundant.
13. Transfer remains closed after the first successful defense.
14. Transfer destination is the next active seat clockwise and the new defender cap is validated
    atomically against the full unresolved packet.
15. TAKE closes the entire bout immediately.
16. Final-card defense closes the entire bout immediately as BITO.
17. Table arithmetic is global to the bout and latest-defense metadata has exactly one current
    source packet.
18. Refill quotas consume no more cards than exist, never raise a hand above seven, and physical
    cards are dealt in refill order.
19. Refill order is captured once from bout-start roles and transfers never mutate it.
20. Finish evaluation occurs only after resolution, movement, refill, and final deck state.
21. Shedding finish requires both an empty draw pile and empty hand.
22. Simultaneous finishers form one group and leave together.
23. The match ends after all remaining players finish together, or when at most one active player
    remains; a sole remaining player is appended as the terminal loser group.

## 16. Compatibility matrix

| Rule                 | 2 players                                  | 3 players                                                                 | 4 players                                                                  |
| -------------------- | ------------------------------------------ | ------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Seat traversal       | Other active seat                          | Clockwise, skip finished                                                  | Clockwise, skip finished                                                   |
| Initial lead         | Lowest effective trump across two          | Across three                                                              | Across four                                                                |
| Initial defender     | Other player                               | Next active clockwise                                                     | Next active clockwise                                                      |
| Initial attack       | Lead only; all canonical bases             | Lead only; all canonical bases                                            | Lead only; all canonical bases                                             |
| Attacker order       | One attacker                               | Lead plus one additional attacker                                         | Lead plus two additional attackers                                         |
| Attacking phases     | One non-cycling phase                      | Each non-defender once                                                    | Each non-defender once                                                     |
| Batch boundary       | Fixed before response                      | Same                                                                      | Same                                                                       |
| Dynamic cap          | One shared defender cap                    | Same cap shared by two attackers                                          | Same cap shared by three attackers                                         |
| Defense              | Strictly greater, irredundant              | Unchanged                                                                 | Unchanged                                                                  |
| Transfer destination | Other active seat                          | Next active clockwise                                                     | Next active clockwise                                                      |
| Transfer lead change | Transfer swaps the two roles               | Only if lead becomes defender                                             | Only if lead becomes defender                                              |
| TAKE                 | Cancels bout; existing attacker leads next | Cancels every later phase; next after defender leads                      | Same                                                                       |
| BITO                 | Defender leads next                        | Defender leads next, unless finished                                      | Same                                                                       |
| Final-card defense   | Immediate BITO                             | Immediate BITO, cancels later attackers                                   | Same                                                                       |
| Refill order         | Original bout starter, initial defender    | Original bout starter, other initial attacker clockwise, initial defender | Original bout starter, other initial attackers clockwise, initial defender |
| Insufficient refill  | Balanced two-hand result                   | Same smallest-hand algorithm                                              | Same smallest-hand algorithm                                               |
| Finish               | Winner or simultaneous draw                | Ordered finish groups                                                     | Ordered finish groups                                                      |
| Final tie            | Both empty = DRAW                          | All remaining empty share group                                           | All remaining empty share group                                            |

## 17. D1 deck-variant amendment

The D1 freeze generalizes card population and rank order through `profile × physical deck copies`
without introducing another multiplayer state machine. CLASSIC/EXTENDED and one/two copies all use
the roles, transfers, phases, shared cap, immutable refill order, and finish rules above.

D1 also records the original author's recovered correction that a contiguous street is a legal
initial attack. M1's earlier post-response-only wording is superseded on that point. Initial streets
remain lead-only, atomic, non-wrapping, profile-aware, and subject to the same physical-card cap.
All other M1 rules remain intact.

## 18. Future Product Decisions

These are deliberately non-canonical and do not block M2 domain work:

- room-size selector and lobby flow;
- exact seat and placement labels;
- pass-button presentation versus automatic no-move advancement;
- card and phase animation timing;
- compact-table layout on different screen sizes;
- whether bots later support three or four players;
- matchmaking, public lobbies, ratings, and placement-statistics presentation;
- persistence and rematch UX for future multi-participant rooms;
- exact deck-profile/deck-count controls, defaults, and release gating;
- whether 54 cards are recommended for three- or four-player sessions.

## 19. Open Gameplay Questions

**NONE.**
