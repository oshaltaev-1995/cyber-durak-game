# Cyber Durak / Kiba — Game Rules v0.1

> Status: reconstructed ruleset based on the original homemade card game remembered from childhood.
>
> This document is the **authoritative gameplay specification** for implementation unless a rule is explicitly marked as provisional or open.

## 1. Game concept

Cyber Durak (working historical name: **Kiba**) is a shedding card game inspired by Durak, but with a custom arithmetic system.

The goal is simple:

> **Be the first player to get rid of all cards.**

The main difference from ordinary Durak is that attacks, defenses, throw-ins and transfers are based on **card point values and arithmetic relations**, rather than suit matching.

The game also uses a dynamic trump system: after each completed bout, the exposed top card of the deck determines the trump rank and trump suit for the next bout.

---

## 2. Decks

Supported deck sizes:

- **36 cards**
- **54 cards** including two Jokers

Future variants may support two physical decks, but that is not required for the first MVP.

---

## 3. Initial deal

- Each player receives **7 cards**.
- The remaining deck stays face-up with its top card visible.
- The visible top card determines the trump state for the bout.

---

## 4. Card point values

| Card | Base value |
|---|---:|
| 6 | 6 |
| 7 | 7 |
| 8 | 8 |
| 9 | 9 |
| 10 | 10 |
| Jack (J) | 12 |
| Queen (Q) | 15 |
| King (K) | 18 |
| Ace (A) | 20 |
| Joker | 25 |

All arithmetic rules use the **effective card value**, not necessarily the base value.

---

## 5. Trump system

### 5.1 Normal exposed card

If the exposed top card is, for example:

`K♠`

then **all Spades and all Kings are trump cards**.

So trump status is determined by:

- matching the exposed card's **suit**, OR
- matching the exposed card's **rank**

A trump card has:

`effectiveValue = baseValue × 2`

Example:

`K♦ = 18 × 2 = 36`

if Kings are trump.

Example:

`9♥ = 9 × 2 = 18`

if Hearts are trump.

### 5.2 Joker exposed on top

If a Joker is the exposed top card:

- all cards of the **same color** as that Joker are trump;
- the second Joker is also trump.

Examples:

- red Joker → all Hearts and Diamonds are trump, plus the other Joker;
- black Joker → all Clubs and Spades are trump, plus the other Joker.

A trump Joker is worth:

`25 × 2 = 50`

### 5.3 Exact duplicate of the exposed card

This matters only in future variants using more than one physical deck.

If a player holds an exact duplicate of the exposed card — same rank and same suit — the current reconstructed rule is:

`effectiveValue = baseValue × 3`

Example:

exposed card: `K♠`

duplicate `K♠` in hand:

`18 × 3 = 54`

**Status: provisional / balance decision.**

This rule should not block the MVP and may be omitted until multi-deck play exists.

### 5.4 Trump after the deck is exhausted

When the draw pile is empty:

- there is no exposed deck card;
- there are **no trump cards**;
- all cards use their base values.

---

## 6. Bout terminology

A **bout** is one complete attack/defense sequence until:

- the defender successfully beats the attack, or
- the defender takes the cards.

A bout may contain:

- an initial attack;
- defense;
- throw-ins;
- transfers;
- further defense;
- repeated recalculation of arithmetic relations.

---

## 7. Legal attack

A player may start an attack with:

- any single card;
- multiple cards of the same rank;
- a set of cards connected by a valid arithmetic relation.

Cards may not simply be placed together without a relation.

### 7.1 Initial-attack relation scope

An initial attack may use a single card, same-rank relationships, or one connected structure made
from two or more non-empty card groups with equal effective totals. Either side of an arithmetic
equality may contain multiple physical cards.

Initial attack construction does **not** expose the selected cards' total or arithmetic mean as new
targets. Table-total and arithmetic-mean targets become available only for post-response throw-ins
after a defender has responded and a table state exists.

Examples:

`9 + 7` ❌

No relation exists.

`9 + K` ❌

No relation exists under normal values.

`9 + 9` ✅

Same rank.

`9 + 9 + K` ✅

Because:

`9 + 9 = 18 = K`

`J + 6 + K` ✅

Because:

`12 + 6 = 18 = K`

### 7.2 Trump values participate in attack relations

Example:

exposed trump makes Hearts trump.

`K♣ = 18`

`9♥ = 9 × 2 = 18`

Therefore:

`K♣ + 9♥` ✅

The cards are connected because their effective values are equal.

### 7.3 Same rank remains a valid relation

If one or more cards of a rank are already part of a legal attack, additional cards of that same rank may be added, subject to the card-count limit.

Example:

`K + 9 + 9`

is legal because `9 + 9 = K`.

Another `9` may then be added because it matches an already-present rank.

---

## 8. Card-count limit

There is no explicit point-value ceiling for an attack.

However:

> The total number of attacking / thrown-in cards may not exceed the number of cards the defender had in hand at the start of the bout.

This limit is fixed when the bout starts and is not recalculated after cards are played.

---

## 9. Defense

The defender may beat an attack with **any card or combination of cards**, regardless of suit.

The only required condition is:

`defenseValue > attackValue`

where both values are the sums of effective card values.

Example:

Attack:

`J + J + 6 + 6`

`12 + 12 + 6 + 6 = 36`

Defense:

`Q + Q + 10`

`15 + 15 + 10 = 40`

Since:

`40 > 36`

the defense is legal.

### 9.1 Exact equality is not enough

If the attack totals 36, a defense totaling exactly 36 is not sufficient.

Defense must be **strictly greater**.

---

## 10. Throw-ins after defense

After cards have been played onto the table, further legal throw-ins can be generated from the current table state.

The table is recalculated after every legal addition.

Three major arithmetic mechanisms are currently confirmed:

1. **Existing rank / existing card-value relations**
2. **Total table sum**
3. **Arithmetic mean of all physical cards on the table**

A legal target value may be satisfied by:

- one card with that effective value;
- a multi-card combination whose total effective value equals that target.

### 10.1 Existing rank / equivalent value

Suppose:

Attack:

`7 + 7 = 14`

Defense:

`K = 18`

Because 18 is now represented on the table, another card or combination totaling 18 may be thrown in.

Example:

`10 + 8 = 18` ✅

### 10.2 Total table sum

Using the same example:

`7 + 7 + K`

effective total:

`7 + 7 + 18 = 32`

A card or combination totaling **32** may therefore be thrown in.

### 10.3 Arithmetic mean

The arithmetic mean is:

`sum of effective values of every physical card on the table / number of physical cards on the table`

Example:

Attack:

`J = 12`

Defense:

`K = 18`

Table total:

`12 + 18 = 30`

Physical cards:

`2`

Mean:

`30 / 2 = 15`

Therefore a Queen may be thrown in:

`Q = 15` ✅

A combination totaling 15 is also valid:

`7 + 8 = 15` ✅

### 10.4 Mean is recalculated continuously

After every legal throw-in, the table total and arithmetic mean are recalculated.

Example:

`J(12) + K(18) + Q(15)`

Total:

`45`

Physical cards:

`3`

Mean:

`45 / 3 = 15`

Therefore another legal 15-value card or combination may be possible, subject to the card-count limit.

### 10.5 Non-integer arithmetic mean

If the mean is not an integer or cannot be represented by a legal card/combination, it produces no useful throw-in target.

Example:

`7 + 7 + K(18) = 32`

`32 / 3 = 10.666...`

No exact integer target is produced.

---

## 11. Transfer

Instead of defending, a player may transfer the attack to the next player if they can play cards whose total effective value is **exactly equal to the current accumulated attack value**.

Rule:

`transferValue == currentAttackValue`

Not greater than.

Not approximately equal.

Exactly equal.

Example:

Attack:

`K = 18`

Transfer:

`9 + 9 = 18`

✅ Legal transfer.

---

## 12. Snowball transfer

Transfers accumulate.

This is a core mechanic.

Example with multiple players:

Player A attacks:

`K = 18`

Player B transfers:

`9 + 9 = 18`

The table now contains:

`18 + 18 = 36`

Therefore Player C must transfer **exactly 36**.

Player C transfers:

`J + J + 6 + 6 = 36`

Now the accumulated table value is:

`72`

Therefore Player D must transfer **exactly 72**.

The transfer requirement grows like a snowball.

The receiving player may instead defend or take according to the normal rules if a transfer is not possible or not desirable.

---

## 13. Taking cards

If the defender cannot or does not want to defend:

- the defender takes the cards from the table;
- that player does **not** become the next attacker;
- the previous attacker keeps initiative;
- after refill, the previous attacker attacks again.

The player who took the cards effectively loses the next attacking turn.

---

## 14. Successful defense

If the defender successfully beats the complete attack:

- the table becomes **bito** / discarded;
- the defender becomes the attacker for the next bout.

This follows the normal Durak-style initiative rule.

---

## 15. Drawing back to seven cards

After a bout, players refill their hands from the deck up to **7 cards**, while cards remain in the deck.

If a player has:

- 3 cards → draw 4;
- 5 cards → draw 2;
- 7 or more cards → draw none.

### 15.1 Draw order

The player who **started the bout as attacker** draws first.

Then the remaining players draw in turn order.

### 15.2 New trump timing

The trump state is fixed for the entire current bout.

Drawing cards must not change the effective values of cards already played during that bout.

After the bout is fully resolved and refill has occurred, the newly exposed top card defines the trump state for the next bout.

---

## 16. End of deck

When the deck is empty:

- no cards are drawn;
- no trump exists;
- play continues with the cards remaining in players' hands.

---

## 17. Winning

The first player to legally get rid of all cards wins.

The exact timing of victory must be handled by the rules engine so that a player cannot be declared winner prematurely while they are still required to take cards or while a bout is unresolved.

---

## 18. Effective-value examples

### Example A — normal cards

`9 + 9 = 18`

therefore they may relate to:

`K = 18`

### Example B — trump arithmetic

Hearts are trump.

`9♥ = 18`

Therefore:

`9♥` may relate directly to `K♣ = 18`.

### Example C — trump face card

Kings are trump.

`K♦ = 36`

### Example D — trump Joker

Red Joker is exposed.

Other Joker:

`25 × 2 = 50`

---

## 19. Important engine invariants

The implementation should preserve these invariants:

1. Card calculations always use **effective values**.
2. Trump state is immutable during one bout.
3. Defense requires `>` attack value.
4. Transfer requires exact `==` accumulated attack value.
5. Transfer value accumulates after every transfer.
6. Throw-in total and mean are recalculated after every legal addition.
7. Same-rank relations are legal independently of arithmetic.
8. Multi-card combinations may satisfy an arithmetic target.
9. Attack card count never exceeds the defender's starting hand size.
10. After successful defense, defender attacks next.
11. After taking, previous attacker attacks again.
12. Attacker refills first.
13. No trump exists after the deck is exhausted.

---

## 20. Rules that are still provisional or need playtesting

These are not blockers for implementation, but they should be easy to change:

### 20.1 Exact duplicate multiplier in multi-deck mode

Current reconstructed proposal:

`same suit + same rank as exposed card = ×3`

Not needed for MVP.

### 20.2 Joker visual color convention

A 54-card deck implementation must define how red and black Jokers are represented in the data model and UI.

### 20.3 Complex arithmetic chains

The rules engine should initially implement the confirmed arithmetic relations literally and be covered by tests.

If playtesting reveals degenerate loops or overly powerful chains, the game design may later add limits without rewriting the whole engine.

### 20.4 Player counts

The rules clearly support transfer chains and therefore naturally support 3+ players, but the first playable MVP intentionally starts with 2 participants total: one human and one bot.

---

## 21. Recommended MVP rules subset

First playable implementation:

- 36-card deck
- 2 players
- 7-card hands
- dynamic rank + suit trump
- ×2 trump values
- arithmetic attack relations
- defense by strictly higher total
- throw-ins using rank, total sum and arithmetic mean
- transfer by exact accumulated value
- draw to 7
- take / bito initiative rules
- no Joker
- no multi-deck mode
- bot opponent

After the core is stable:

- 3–4 players
- online rooms
- 54-card deck
- Jokers
- matchmaking
- rankings
- cosmetics

---

## 22. Design philosophy

This ruleset was reconstructed from a real homemade game rather than designed from scratch as a software mechanic.

The implementation should therefore prioritize:

1. preserving the recognizable original logic;
2. making arithmetic transparent to the player;
3. playtesting before adding artificial balance rules;
4. keeping game logic deterministic and independent from UI;
5. allowing rules to evolve without breaking saved architecture.
