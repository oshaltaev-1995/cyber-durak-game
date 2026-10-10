# KIBA Deck Variants Canon

> Status: **D1 canonical freeze**. This document defines the deck-configuration dimension of KIBA
> and amends the initial-attack street rule. It supplements [`GAME_RULES.md`](GAME_RULES.md) and
> [`MULTIPLAYER_RULES.md`](MULTIPLAYER_RULES.md); all gameplay not explicitly amended here remains
> unchanged. D1 is documentation only and does not imply implementation or production activation.

## 1. Canon amendment record

The original game author recovered that a contiguous rank street is legal as an **initial attack**.
Earlier M1 wording treated rank runs only as post-response throw-in reasons. That restriction is
superseded. The correction applies to every canonical deck configuration and to two, three, and
four players. All other M1 rules remain intact.

## 2. Configuration model

A deck configuration has two independent dimensions:

```text
rank profile × physical deck count
```

| Rank profile | Copies | Physical cards | Canonical name  |
| ------------ | -----: | -------------: | --------------- |
| CLASSIC      |      1 |             36 | Single Classic  |
| EXTENDED     |      1 |             54 | Single Extended |
| CLASSIC      |      2 |             72 | Double Classic  |
| EXTENDED     |      2 |            108 | Double Extended |

These are four configurations of one ruleset, not four unrelated games. Every configuration
supports two, three, or four players and seven-card initial hands.

## 3. Rank profiles and physical populations

### 3.1 CLASSIC

CLASSIC contains ranks:

```text
6, 7, 8, 9, 10, J, Q, K, A
```

Each physical copy contains all nine ranks in Clubs, Diamonds, Hearts, and Spades, with no Jokers:

```text
9 ranks × 4 suits = 36 cards
```

Two copies contain 72 cards.

### 3.2 EXTENDED

EXTENDED contains suited ranks:

```text
2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A
```

Each physical copy contains all thirteen ranks in four suits plus one red Joker and one black
Joker:

```text
13 ranks × 4 suits + 2 Jokers = 54 cards
```

Two copies contain 108 cards: 104 suited cards, two red Jokers, and two black Jokers.

## 4. Physical identity and display identity

Every card instance has a stable physical identity independent of its gameplay/display attributes:

```text
physical identity
rank
suit, when suited
Joker color, when a Joker
physical deck copy
display identity
```

In a double deck, `K♥` from copy one and `K♥` from copy two are distinct physical cards even though
both normally display as `K♥`. They must remain independently traceable through deck, hand, table,
discard, TAKE, and refill. Normal player-facing presentation does not require `#1`/`#2` copy labels.

Rank equality never collapses physical instances. Two exact duplicates may both participate in any
same-rank relation allowed by the existing canon, and every physical card counts separately against
the attack-card limit.

## 5. Base and effective values

| Rank  | Base value |
| ----- | ---------: |
| 2     |          2 |
| 3     |          3 |
| 4     |          4 |
| 5     |          5 |
| 6     |          6 |
| 7     |          7 |
| 8     |          8 |
| 9     |          9 |
| 10    |         10 |
| J     |         12 |
| Q     |         15 |
| K     |         18 |
| A     |         20 |
| Joker |         25 |

A trump card has twice its base value. Trump is a Boolean property for one bout, so a card that
matches several trump relationships is doubled exactly once. There is no exact-duplicate ×3 rule.

Examples: trump `3 = 6`, trump `10 = 20`, trump `K = 36`, trump `A = 40`, and trump
`Joker = 50`.

## 6. Trump relationships

Trump is derived from the exposed top card at bout start and remains fixed for that bout.

### 6.1 Ordinary suited exposed card

For exposed suited rank `R` and suit `S`, every suited card matching suit `S` **or** rank `R` is
trump. In EXTENDED, the Joker matching the exposed suit's color is also trump:

- exposed Heart or Diamond: every red Joker is trump;
- exposed Club or Spade: every black Joker is trump.

The opposite-color Joker remains non-trump. In a double deck, exact duplicate suited cards satisfy
the same relationships but are still doubled only once.

Example: exposed `7♥` makes every Heart, every suited Seven, and every red Joker trump. A black
Joker remains 25.

### 6.2 Exposed Joker

An exposed red Joker makes all Hearts, all Diamonds, and every red Joker physical instance trump.
A black Joker remains non-trump.

An exposed black Joker makes all Clubs, all Spades, and every black Joker physical instance trump.
A red Joker remains non-trump.

Joker color therefore controls this special trump family. A generic cross-color “same Joker rank”
trump rule does not exist.

### 6.3 Empty draw pile

When the draw pile is empty, no exposed card and no trump exist. Every card uses its base value;
each Joker is worth 25.

## 7. Joker outside trump resolution

A Joker is an ordinary value-bearing card worth 25, or 50 when trump. It may participate wherever
its exact effective value is relevant, including arithmetic equality, defense totals, transfer
targets, table total, arithmetic mean, and value comparison. It is not wild and never substitutes
for an arbitrary rank or value.

For normal rank-based mechanics, red and black Jokers share one logical rank, `Joker`. They may
therefore satisfy same-rank relationships. Their colors remain distinct only where the trump-color
rules require it.

## 8. Linear street order

Street legality uses rank identity, not effective value.

CLASSIC order is:

```text
6, 7, 8, 9, 10, J, Q, K, A
```

EXTENDED order is:

```text
2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A, Joker
```

Joker is one terminal rank immediately after Ace. Red and black Jokers occupy the same street
position. Neither profile wraps: `K-A-6-7-8` is not a CLASSIC street, and
`A-Joker-2-3-4` is not an EXTENDED street.

A qualifying street contains at least five **distinct** consecutive ranks within one contiguous
segment of the selected profile order. Duplicate physical cards do not increase distinct run
length. Additional selected duplicates are permitted only when their rank belongs to the same
qualifying run.

## 9. Recovered initial-street attack

An initial attack may be justified by one contiguous street in addition to the existing single,
same-rank, and arithmetic bases. The initial selected batch must satisfy all of these conditions:

1. it contains at least five distinct consecutive ranks in the selected profile;
2. every selected rank belongs to that one contiguous run;
3. duplicates, including exact physical duplicates, add no distinct positions;
4. every physical card fits the current defender-based attack capacity;
5. the complete batch is committed before the defender begins responding.

Examples:

- CLASSIC `6-7-8-9-10` is legal;
- CLASSIC `10-J-Q-K-A + J + Q` is legal when seven physical cards fit the cap;
- CLASSIC `10-J-Q-K-A + 6` is illegal because 6 is outside that run;
- EXTENDED `2-3-4-5-6` is legal;
- EXTENDED `10-J-Q-K-A-Joker` is legal;
- EXTENDED `A-Joker-2-3-4` is illegal because streets never wrap.

The initial attack window still closes when the defender begins responding. An omitted card cannot
later claim membership in the closed initial street; it requires a new current throw-in reason.

## 10. Street capacity

Street legality never bypasses the shared dynamic attack limit:

```text
bout_attack_cap = defender hand size at the start of the defender tenure
remaining_bout_capacity = bout_attack_cap - attack_cards_already_played
max_add_now = min(remaining_bout_capacity, defender_current_hand_size)
```

Every physical card, including every duplicate, consumes one slot. Against a seven-card defender,
`10-J-Q-K-A + J + Q` uses all seven slots and is legal if every other condition holds; adding an
eighth physical card is rejected. A defender with ten cards can permit up to ten physical cards.
There is no separate fixed seven-card street limit.

## 11. Post-response streets

The existing post-response street mechanism remains available. Use all physical table cards plus
the newly selected throw-in cards to test one contiguous run in the current profile. The run must
contain at least five distinct ranks, every selected rank must belong to it, duplicates do not add
positions, and no wrap is permitted. Historical covered cards remain eligible rank evidence.

All ordinary attacker-phase, `max_add_now`, shared-cap, packet, and response rules still apply.

## 12. Integration with existing canon

Deck configuration changes only card population, rank order, physical identity requirements, and
trump relationships. It does not create another game or multiplayer state machine.

The following remain unchanged across all four configurations:

- two to four stable clockwise seats;
- seven-card initial hands;
- lowest-effective-trump initial lead selection;
- strict-greater, selection-local irredundant defense;
- exact transfer and same-rank transfer extension;
- non-cycling attacker phases and shared dynamic attack cap;
- TAKE, BITO, immutable bout-start refill order, and balanced insufficient refill;
- finish groups and multiplayer endgame.

Current Single Classic behavior remains identical except that an initial street attack is now
canonically legal.

## 13. Future implementation invariants

D2 and later implementation must preserve these invariants:

1. Configuration is modeled as rank profile plus physical deck count, not four independent modes.
2. Total physical cards are exactly 36, 54, 72, or 108 for the corresponding configuration.
3. Every physical instance has a unique stable identity; visual duplicates never collapse.
4. Base values, profile rank order, and trump resolution come from authoritative configuration.
5. Trump multiplication is ×2 once, regardless of how many trump relationships a card matches.
6. Bots and Hint Mode consume authoritative configuration and do not hard-code 36 cards,
   `6..A`, or the absence of Jokers.
7. Card conservation holds across draw pile, hands, table, and discard: no loss and no duplication
   beyond the selected physical deck copies.

Deterministic acceptance examples are D01–D40 in
[`MULTIPLAYER_SCENARIOS.md`](MULTIPLAYER_SCENARIOS.md).

## 14. Future Product Decisions

These presentation/guidance choices are non-canonical and do not block D2:

- exact selector labels and layout for profile and deck count;
- whether the UI initially presents presets such as “36 Classic” and “54 Extended”;
- whether 54 cards are recommended for three or four players;
- whether normal play ever needs a visual copy marker for otherwise identical cards;
- release sequencing, defaults, onboarding, and availability gates for the new configurations.

Recommendations never change legality: EXTENDED and double-deck configurations remain valid with
two, three, or four players.

## 15. Open Gameplay Questions

**NONE.**
