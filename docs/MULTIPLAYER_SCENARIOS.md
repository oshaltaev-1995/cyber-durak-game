# KIBA 2–4 Player Canonical Scenarios

> These 48 M1 scenarios plus 40 D1 deck-variant scenarios are deterministic acceptance
> specifications for [`MULTIPLAYER_RULES.md`](MULTIPLAYER_RULES.md) and
> [`DECK_VARIANTS.md`](DECK_VARIANTS.md). They are documentation, not executable tests.

## Conventions

- Clockwise seats are written `A → B → C → D → A`; shorter games retain the same notation.
- All named players are active unless a scenario explicitly marks one finished.
- Rank values use the canonical base values unless a trump state is stated.
- Unless a D1 scenario states otherwise, repeated ranks in S01–S48 denote distinct suits from
  Single Classic.
- D1 scenarios name rank profile and deck count explicitly. Copy labels identify physical instances
  only and are not required player-facing labels.
- “Count” means total attacking cards counted against the current defender tenure.
- Unmentioned card choices are irrelevant to the asserted rule; every stated defense is
  strictly greater and irredundant.
- Refill and finish groups are “not applicable” when a scenario stops before bout resolution.

## Coverage

| Category                    | Scenarios    |
| --------------------------- | ------------ |
| Starting order              | S01–S04      |
| Initial attack              | S05–S07      |
| Attacker phases and batches | S08–S13      |
| Dynamic cap                 | S14–S17      |
| Transfer                    | S18–S22      |
| TAKE and BITO               | S23–S26      |
| Shared arithmetic table     | S27–S31      |
| Refill                      | S32–S37, S48 |
| Finish and endgame          | S38–S47      |
| Deck configuration/identity | D01–D06      |
| Trump and Joker behavior    | D07–D20      |
| Initial/profile streets     | D21–D31      |
| Street capacity             | D32–D34      |
| Integration/compatibility   | D35–D40      |

## Starting order

### S01 — Three-player lowest trump

- **Active seats:** `A → B → C`.
- **Setup:** exposed `10♠`; A's lowest trump is `8♠ = 16`, B's is `6♠ = 12`, and C's is
  `10♥ = 20`.
- **Sequence:** compare the lowest effective trump held by every player.
- **Cap/count:** no bout has started.
- **Expected result:** B has the unique lowest value and becomes lead attacker; C is defender;
  attacker order is `B → A`.
- **Post-bout:** refill and finish groups are not applicable.

### S02 — Four-player lowest trump

- **Active seats:** `A → B → C → D`.
- **Setup:** exposed `Q♦`; lowest held trumps are A `8♦ = 16`, B `Q♣ = 30`, C `6♦ = 12`, and D
  none.
- **Sequence:** compare all four initial hands.
- **Cap/count:** no bout has started.
- **Expected result:** C leads, D defends, and attacker order is `C → A → B`.
- **Post-bout:** not applicable.

### S03 — Tied lowest trump

- **Active seats:** `A → B → C → D`.
- **Setup:** exposed `7♥`; A holds `7♣ = 14`, C holds `7♦ = 14`, B's lowest trump is
  `8♥ = 16`, and D holds none. The deterministic test RNG selects C from the tie set `{A, C}`.
- **Sequence:** find the shared minimum, then randomize only among tied holders.
- **Cap/count:** no bout has started.
- **Expected result:** C leads and D defends; B and D are not eligible for the tie selection.
- **Post-bout:** attacker order is `C → A → B`; refill is not applicable.

### S04 — No initial hand contains trump

- **Active seats:** `A → B → C → D`.
- **Setup:** exposed `K♠`; no initial hand contains a Spade or King. The deterministic test RNG
  selects D from all four active players.
- **Sequence:** the no-trump-in-hand fallback uses all active seats.
- **Cap/count:** no bout has started.
- **Expected result:** D leads, A defends, and attacker order is `D → B → C`.
- **Post-bout:** not applicable.

## Initial attack

### S05 — Lead-only initial attack

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** A leads, B defends with seven cards, C and D are additional attackers.
- **Sequence:** A commits `J + 6 + K` because `12 + 6 = 18 = K`. Before B responds, C and D
  attempt to add cards.
- **Cap/count:** cap `7`; A's batch uses `3`; count `3`; `max_add_now` is evaluated only after B's
  response.
- **Expected result:** A's batch is accepted; C and D have no action during the initial window.
- **Post-bout:** attacker phases after the first defense begin with A, then C, then D.

### S06 — Omitted card loses the initial relationship

- **Active seats:** `A → B → C`.
- **Setup/roles:** A leads, B defends with seven cards. A holds `9, 9, K, K`.
- **Sequence:** A initially commits `9 + 9 + K = 36`, retaining the other K. B covers with
  `A + A = 40`. The retained K is not a latest-defense rank/value, defense-total target, table-total
  target, arithmetic mean, or rank-run completion.
- **Cap/count:** cap `7`; count `3`; B has five cards, so `max_add_now = 4`.
- **Expected result:** the retained K cannot be appended or justified by the closed initial
  `9 + 9 = K` relationship. A must pass unless another current reason exists.
- **Post-bout:** priority then advances to C; refill/finish are not yet applicable.

### S07 — Omitted card becomes legal for a new reason

- **Active seats:** `A → B → C`.
- **Setup/roles:** same initial hand and roles as S06.
- **Sequence:** A commits `9 + 9 + K = 36` and retains a different K. B covers with
  `A + K = 38`; K is now a latest-defense rank. A plays the retained K as a new one-card batch.
- **Cap/count:** cap `7`; count moves `3 → 4`; B has five cards before the new batch, so one card
  is permitted.
- **Expected result:** the new K is legal because of the current latest-defense rank, not because
  the initial relationship reopened.
- **Post-bout:** B must respond to the new packet; C is still waiting.

## Attacker phases and batch boundaries

### S08 — Lead attacker adds repeatedly before passing

- **Active seats:** `A → B → C`.
- **Setup/roles:** A leads, B defends with seven cards.
- **Sequence:** A attacks `6`; B covers with `7`. A throws `7`; B covers with `8`. A throws `8`;
  B covers with `9`. A then passes.
- **Cap/count:** cap `7`; count progresses `1 → 2 → 3`; B retains four cards.
- **Expected result:** all three batches belong to A's one attacking phase; A's pass closes it.
- **Post-bout:** C becomes current attacker; refill/finish are not yet applicable.

### S09 — A passes and C acts

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** A leads, B defends.
- **Sequence:** A attacks `6`; B covers with `7`; A passes. C uses the latest-defense rank to
  throw another `7`; B covers with `8`.
- **Cap/count:** cap `7`; count `1 → 2`.
- **Expected result:** C acts immediately after A's phase closes; D remains waiting.
- **Post-bout:** C may continue or pass; A cannot act again.

### S10 — No legal move advances automatically

- **Active seats:** `A → B → C`.
- **Setup/roles:** A leads, B defends; after defense the current table authorizes value/rank `7`.
- **Sequence:** A has no legal combination for any current target; C holds another `7`.
- **Cap/count:** cap `7`; count `1`; capacity remains.
- **Expected result:** A has no action and A's phase closes without a required manual Pass; C
  becomes current attacker and may play `7`.
- **Post-bout:** no refill or finish yet.

### S11 — C passes and D receives priority

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** A's phase is already closed; C is current attacker; B is defender.
- **Sequence:** C chooses not to use an available legal addition and passes. D holds a legal card
  for the current latest-defense rank.
- **Cap/count:** shared capacity remains positive.
- **Expected result:** C's phase closes and D becomes current attacker.
- **Post-bout:** A and C stay closed even if D changes the table.

### S12 — Later table changes never return priority to A

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** B defends; A has passed; C is current attacker.
- **Sequence:** C plays and B defends, producing a new latest-defense rank that A could match. C
  passes; D plays and B defends.
- **Cap/count:** every accepted card uses the one shared cap.
- **Expected result:** priority moves `C → D`; it never returns to A despite A's newly legal card.
- **Post-bout:** after D closes, the table becomes BITO.

### S13 — A batch cannot grow after defense starts

- **Active seats:** `A → B → C`.
- **Setup/roles:** A attacked `K = 18`; B covered with `7 + J = 19`; A passed. C holds
  `7, J, 7, K`.
- **Sequence:** C commits `7 + J` as one latest-defense-ranks batch. B begins covering it. C then
  tries to append the extra `7`; after B covers with `K + 6 = 24`, C uses its K as a separate new
  batch authorized by the latest defense.
- **Cap/count:** cap `7`; count is `1` before C, `3` after C's two-card batch, and `4` after the
  later K.
- **Expected result:** the mid-defense `7` append is rejected; the later K is a distinct packet and
  may be legal.
- **Post-bout:** C retains the phase until passing or losing all legal actions.

## Dynamic shared cap

### S14 — Cap shared across A, C, and D

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** B becomes defender with seven cards; each stated batch is independently legal.
- **Sequence:** A adds three attacking cards, C later adds two, and D later adds one.
- **Cap/count:** cap `7`; count `3 → 5 → 6`; one slot remains.
- **Expected result:** all attackers share `6 / 7`; no attacker receives a separate allowance.
- **Post-bout:** any later legal batch may contain at most one card.

### S15 — Defender current hand is limiting

- **Active seats:** `A → B → C`.
- **Setup/roles:** B's cap is seven; four attack cards have been played; defenses leave B with one
  card.
- **Sequence:** C attempts a legal-by-relation two-card batch, then a one-card batch.
- **Cap/count:** remaining capacity `3`; defender hand `1`; `max_add_now = 1`.
- **Expected result:** two cards are rejected by size; one card may be accepted.
- **Post-bout:** if B covers with its final card, automatic BITO follows.

### S16 — Global remaining cap is limiting

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** B's tenure began with five cards; four attacking cards are already counted; B
  still holds four cards.
- **Sequence:** D attempts a two-card legal-by-relation batch.
- **Cap/count:** remaining capacity `1`; defender hand `4`; `max_add_now = 1`.
- **Expected result:** the two-card batch is rejected because the global cap, not B's hand, limits
  the addition.
- **Post-bout:** D may instead select one legal card.

### S17 — Cap exhaustion closes later opportunities

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** B's cap is five and five attacking cards have already been played and covered.
- **Sequence:** A closes its phase; C and D each reach priority with `max_add_now = 0`.
- **Cap/count:** cap/count `5 / 5`.
- **Expected result:** C and D have no attacking action; their phases close and the covered table
  becomes BITO.
- **Post-bout:** intended next lead is B; refill order is `A → C → D → B`.

## Transfer

### S18 — One transfer B to C

- **Active seats:** `A → B → C`.
- **Setup/roles:** A leads and attacks B with `K = 18`; C currently has five cards.
- **Sequence:** B transfers with `9 + 9 = 18`; the packet becomes `36` and moves to C. C defends
  with `A + A = 40`.
- **Cap/count:** proposed packet has three attacking cards; C's new cap is five, so it fits.
- **Expected result:** C is defender, A remains lead, transfer closes after C's defense, and
  attacker order is `A → B`.
- **Post-bout:** immutable bout-start refill order is `A → C → B`.

### S19 — Chain B to C to D

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** no stated card is trump; A attacks B with `6`.
- **Sequence:** B transfers a different `6`, making target `12`; C transfers `6 + 6 = 12`, making
  target `24`; D covers with `Q + 10 = 25`.
- **Cap/count:** four attacking cards enter D's tenure; D has seven cards, so cap `7` accepts them.
- **Expected result:** D is final defender; A remains lead; attacker order is `A → B → C`.
- **Post-bout:** immutable bout-start refill order is `A → C → D → B`.

### S20 — Full chain returns to A and changes lead to D

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** A has 13 cards after an earlier TAKE and leads. Base values apply.
- **Sequence:** A attacks B with `K = 18`; B transfers `9 + 9 = 18` to C, making `36`; C
  transfers `J + J + 6 + 6 = 36` to D, making `72`; D transfers
  `A + A + K + 7 + 7 = 72` to A, making `144`. A covers with
  `Q + Q + Q + Q + K + K + A + A + 7 + 7 = 150`.
- **Cap/count:** the unresolved packet contains 12 attack cards. After playing the initial K, A has
  12 cards, so its new cap is `12`; the transfer fits exactly. A's 150 defense is irredundant
  because removing even a 7 leaves `143 <= 144`.
- **Expected result:** final defender A; new lead D; first attacking phase D, then B, then C. A is
  skipped as defender.
- **Post-bout:** current roles do not affect the immutable bout-start refill order, which remains
  `A → C → D → B`.

### S21 — Transfer rejected by new-defender limit

- **Active seats:** `A → B → C`.
- **Setup/roles:** A attacks B with `K = 18`; C has only two cards.
- **Sequence:** B proposes `9 + 9 = 18` as a transfer to C.
- **Cap/count:** the resulting unresolved packet would contain three attack cards, but C's proposed
  cap would be two.
- **Expected result:** transfer is rejected atomically; C never becomes defender; B keeps both 9s,
  remains defender, and still faces the original target `18`.
- **Post-bout:** immutable bout-start refill order is `A → C → B` regardless of how B resolves the
  packet.

### S22 — Attacker order after a chain when lead remains eligible

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** A leads and attacks B; B legally transfers to C; A never becomes defender.
- **Sequence:** C makes the first successful defense.
- **Cap/count:** C's cap was reset and validated when the transfer arrived.
- **Expected result:** A remains lead. Non-defender phase order is `A → B → D`; C is skipped.
- **Post-bout:** attacking-phase order changed, but immutable bout-start refill order remains
  `A → C → D → B`.

## TAKE and BITO

### S23 — TAKE cancels attackers who have not acted

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** A leads, B defends; C and D have not received phases.
- **Sequence:** A commits the initial batch; B confirms TAKE.
- **Cap/count:** the accepted initial cards count only until terminal resolution.
- **Expected result:** C and D receive no phases, no extra card may be added, and the whole table
  moves immediately to B.
- **Post-bout:** refill order `A → C → D → B`; intended next lead is C, the next active after B.

### S24 — Ordinary BITO after every phase

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** A leads, B defends with enough cards.
- **Sequence:** A attacks `6`, B covers `7`, and A passes; C throws `7`, B covers `8`, and C
  passes; D throws `8`, B covers `9`, and D passes.
- **Cap/count:** cap `7`; count `1 → 2 → 3`.
- **Expected result:** only D's final pass exhausts attacker order; the table becomes BITO and is
  discarded.
- **Post-bout:** intended next lead B; refill order `A → C → D → B`.

### S25 — Final-card defense cancels later phases

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** A attacks B with `K = 18`; B's final two cards are `J + 7 = 19`.
- **Sequence:** B uses both cards for a legal irredundant defense.
- **Cap/count:** count `1`; B's hand becomes zero during the bout.
- **Expected result:** automatic BITO occurs immediately. A receives no further throw-in and C/D
  receive no phase.
- **Post-bout:** refill order `A → C → D → B`; B's match finish is evaluated only afterward.

### S26 — Intended BITO leader finishes and is skipped

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** draw pile is empty; B defends A's packet using its final card, triggering BITO.
- **Sequence:** discard table; no refill; evaluate empty hands.
- **Cap/count:** no later addition is permitted.
- **Expected result:** B forms the next finish group. B was intended next lead but is now finished.
- **Post-bout:** C, the next active player clockwise after B, becomes lead and D becomes defender.

## Shared arithmetic table across attackers

### S27 — Latest-defense rank survives attacker handoff

- **Active seats:** `A → B → C`.
- **Setup/roles:** A attacks `6`; B covers with `7`; A passes.
- **Sequence:** C throws another 7 using the latest-defense rank; B covers it with `8`.
- **Cap/count:** cap `7`; count `1 → 2`.
- **Expected result:** latest-defense anchors are shared public state, not private to A.
- **Post-bout:** C may continue from the new latest defense or pass.

### S28 — Latest-defense total survives attacker handoff

- **Active seats:** `A → B → C`.
- **Setup/roles:** A attacks `K = 18`; B covers with `J + 8 = 20`; A passes.
- **Sequence:** C throws `A = 20` using the latest-defense total. B covers with `Q + 6 = 21`.
- **Cap/count:** count `1 → 2`; both defenses are irredundant.
- **Expected result:** C may use the defense packet total created during A's phase.
- **Post-bout:** latest-defense state becomes `Q + 6`, replacing `J + 8` as direct anchors.

### S29 — Table total survives attacker handoff

- **Active seats:** `A → B → C`.
- **Setup/roles:** A attacks `J = 12`; B covers with `K = 18`; shared table total is `30`; A
  passes.
- **Sequence:** C throws `Q + Q = 30`; B covers with `A + J = 32`.
- **Cap/count:** count `1 → 3`; capacity and B's hand permit the two-card batch.
- **Expected result:** table total includes A's and B's earlier physical cards and is available to C.
- **Post-bout:** all physical cards remain in the same table history.

### S30 — Arithmetic mean survives attacker handoff

- **Active seats:** `A → B → C`.
- **Setup/roles:** A attacks `J = 12`; B covers with `K = 18`; total `30` over two cards gives
  mean `15`; A passes.
- **Sequence:** C throws `Q = 15`; B covers it legally.
- **Cap/count:** count `1 → 2`.
- **Expected result:** C can use the exact shared arithmetic mean.
- **Post-bout:** the mean is recalculated after C's Q and B's new defense.

### S31 — Rank-run state survives attacker handoff

- **Active seats:** `A → B → C`.
- **Setup/roles:** A attacks `10`, B covers `J`; A throws J, B covers K; A throws K, B covers A;
  then A passes. Physical represented ranks are `10, J, K, A`.
- **Sequence:** C throws Q, producing the contiguous five-rank run `10–A`.
- **Cap/count:** cap `7`; count `3 → 4`; B retains enough cards.
- **Expected result:** historical physical ranks remain global across the handoff and make C's Q
  legal.
- **Post-bout:** A's closed phase remains closed despite the new run.

## Refill

### S32 — Sufficient deck for every player

- **Active seats:** `A → B → C`; bout starter A, initial defender B, refill order `A → C → B`.
- **Setup:** post-movement hands are A `4`, C `6`, B `3`; at least eight cards remain.
- **Sequence:** compute full deficits, then physically draw in order `A → C → B`.
- **Cap/count:** completed bout; no active cap.
- **Expected result:** quotas A `3`, C `1`, B `4`; final hands `7 / 7 / 7`; eight cards consumed.
- **Post-bout:** finish groups none while the deck remains nonempty; intended initiative applies.

### S33 — Three-player insufficient balanced refill

- **Active seats:** `A → B → C`; bout starter A, initial defender B, refill order `A → C → B`.
- **Setup:** hand sizes A `3`, C `4`, B `5`; four cards remain.
- **Sequence:** allocate to smallest: A `3→4`; tie A/C at 4 goes to A `4→5`; C `4→5`; tie
  A/C/B at 5 goes to A `5→6`. Then deal physical cards A's three first, C's one, B's none.
- **Cap/count:** completed bout.
- **Expected result:** quotas A `3`, C `1`, B `0`; final sizes A `6`, C `5`, B `5`; deck empty.
- **Post-bout:** evaluate zero-card finishers; none in this setup.

### S34 — Four-player insufficient balanced refill

- **Active seats:** `A → B → C → D`; bout starter C, initial defender D, immutable refill order
  `C → A → B → D`.
- **Setup:** hand sizes C `2`, A `3`, B `5`, D `6`; eight cards remain.
- **Sequence:** smallest-hand allocation yields C four cards, A three, B one, D zero; physical draw
  follows `C(4) → A(3) → B(1) → D(0)`.
- **Cap/count:** completed bout.
- **Expected result:** quotas C `4`, A `3`, B `1`, D `0`; all four finish refill at six; deck
  empty.
- **Post-bout:** no one finishes because every hand is nonempty.

### S35 — Two-player compatibility: `3 / 5` plus four

- **Active seats:** `A → B`; refill order A then B.
- **Setup:** hands A `3`, B `5`; four cards remain.
- **Sequence:** smallest allocation: A to 4, A to 5, tied A first to 6, then B to 6; deal A's
  three cards before B's one.
- **Cap/count:** completed bout.
- **Expected result:** quotas `3 / 1`; final `6 / 6`, exactly the current canon.
- **Post-bout:** deck empty; neither finishes.

### S36 — Two-player compatibility: `4 / 5` plus four

- **Active seats:** `A → B`; refill order A then B.
- **Setup:** hands A `4`, B `5`; four cards remain.
- **Sequence:** A to 5; tied A first to 6; B to 6; tied A first to 7.
- **Cap/count:** completed bout.
- **Expected result:** quotas `3 / 1`; final `7 / 6`; refill-first wins the last tie exactly as
  current canon.
- **Post-bout:** deck empty; neither finishes.

### S37 — Two-player compatibility: `6 / 3` plus three

- **Active seats:** `A → B`; refill order A then B.
- **Setup:** hands A `6`, B `3`; three cards remain.
- **Sequence:** B is uniquely smallest for all three quota cards and rises `3→4→5→6`; physical
  draw gives B all three.
- **Cap/count:** completed bout.
- **Expected result:** quotas `0 / 3`; final `6 / 6`, exactly the current canon.
- **Post-bout:** deck empty; neither finishes.

## Finish groups and endgame

### S38 — One player finishes

- **Active seats:** `A → B → C`.
- **Setup/roles:** after terminal resolution and refill the deck is empty; hands A `0`, B `3`, C
  `4`; intended next lead is A.
- **Sequence:** evaluate finish only now.
- **Cap/count:** bout complete.
- **Expected result:** append finish group `[A]`; remove A from active traversal.
- **Post-bout:** intended A is skipped; B leads and C defends.

### S39 — Two players finish simultaneously

- **Active seats:** `A → B → C → D`.
- **Setup/roles:** after resolution/refill with empty deck, hands A `0`, B `0`, C `3`, D `5`.
- **Sequence:** evaluate all seats in one resolution.
- **Cap/count:** bout complete.
- **Expected result:** append one shared finish group `[A, B]`, not two ordered groups.
- **Post-bout:** active ring becomes `C → D`; if intended lead was A, advance to C.

### S40 — Natural `4 → 3 → 2` reduction

- **Active seats:** initially `A → B → C → D`.
- **Setup/roles:** first empty-deck resolution leaves A `0`, B `2`, C `3`, D `4`; a later
  resolution leaves C `0`, B `1`, D `3`.
- **Sequence:** record `[A]`, continue with `B → C → D`; later record `[C]` and continue `B → D`.
- **Cap/count:** each finish decision follows a completed bout.
- **Expected result:** finished seats are skipped without reseating; the last two use the same
  generalized rules.
- **Post-bout:** B and D continue through the ordinary two-player reduction of the same state
  machine.

### S41 — One final player remains and becomes terminal loser

- **Active seats:** C and D remain; earlier groups are `[A]`, `[B]`.
- **Setup/roles:** empty deck; after resolution C has `0`, D has `4`.
- **Sequence:** append C as a shedding finisher, leaving only D active.
- **Cap/count:** bout complete.
- **Expected result:** append `[C]`, then append terminal loser group `[D]`; match ends without D
  playing alone.
- **Post-bout:** outcome is `[[A], [B], [C], [D]]`; there is no next lead.

### S42 — Final two finish together, so there is no unique loser

- **Active seats:** C and D remain; earlier groups are `[A]`, `[B]`.
- **Setup/roles:** empty deck; after one resolution C `0`, D `0`.
- **Sequence:** evaluate both together.
- **Cap/count:** bout complete.
- **Expected result:** append shared final group `[C, D]`; do not fabricate a loser.
- **Post-bout:** outcome `[[A], [B], [C, D]]`; match ends.

### S43 — All currently remaining players finish simultaneously

- **Active seats:** `B → C → D`; A finished earlier.
- **Setup/roles:** empty deck; after resolution B `0`, C `0`, D `0`.
- **Sequence:** evaluate the entire remaining active set.
- **Cap/count:** bout complete.
- **Expected result:** append `[B, C, D]` as one final group; attacker role and seat order do not
  split it.
- **Post-bout:** no active players and no unique final loser.

### S44 — Attacker empties hand mid-bout but refills

- **Active seats:** `A → B → C`.
- **Setup/roles:** A leads with one card; draw pile is nonempty.
- **Sequence:** A plays its last card as initial attack and has zero while the packet is unresolved.
  B defends; later phases resolve the bout; refill gives A cards.
- **Cap/count:** A's one card counts normally; A remains active throughout.
- **Expected result:** A cannot add more cards while empty but does not finish mid-bout.
- **Post-bout:** A continues with its refilled hand; no finish group contains A.

### S45 — Defender empties through final-card BITO and finishes

- **Active seats:** `A → B → C`.
- **Setup/roles:** draw pile is empty; B's final cards legally cover A's packet.
- **Sequence:** final-card defense triggers immediate BITO; discard table; no refill; evaluate.
- **Cap/count:** later attacker C is cancelled.
- **Expected result:** B becomes empty only at the proper evaluation and forms finish group `[B]`.
- **Post-bout:** intended lead B is skipped; C leads against A.

### S46 — Ordered finish groups with a tied first tier

- **Active seats:** `A → B → C → D` at match start.
- **Setup/roles:** empty-deck resolution one produces A `0`, B `0`, C `3`, D `5`; resolution two
  produces C `0`, D `2`.
- **Sequence:** append simultaneous `[A, B]`; continue C/D; append `[C]`; D is sole remainder.
- **Cap/count:** every group is created only after its complete resolution/refill.
- **Expected result:** final outcome groups are `[[A, B], [C], [D]]`.
- **Post-bout:** A/B share first tier, C is next, D is terminal loser; no next lead.

### S47 — Ordered finish groups with a tied final tier

- **Active seats:** `A → B → C → D` at match start.
- **Setup/roles:** successive empty-deck resolutions finish A alone, then B alone; the final
  resolution leaves C `0` and D `0`.
- **Sequence:** append `[A]`, then `[B]`, then simultaneous `[C, D]`.
- **Cap/count:** all evaluations follow terminal bouts.
- **Expected result:** outcome groups are `[[A], [B], [C, D]]`.
- **Post-bout:** C/D share the final tier and there is no unique loser.

## Two-player transfer compatibility

### S48 — Two-player transfer preserves bout-start refill priority

- **Active seats:** `A → B`.
- **Setup/roles:** A starts with `K, A, A, 6` and B with `9, 9, 6, 7`; A is bout starter and B is
  initial defender; no stated card is trump; enough draw-pile cards remain to refill both hands.
- **Sequence:** A attacks with `K = 18`; B transfers `9 + 9 = 18`; A becomes final defender and B
  becomes final lead; A covers the accumulated `36` with `A + A = 40`; B passes, producing BITO.
- **Cap/count:** the transferred packet has three attack cards and fits A's three-card hand at the
  start of A's defender tenure. A's defense is strictly greater and irredundant.
- **Expected result:** refill is `A → B` because A started the bout as attacker. Final defender A
  and final lead B do not change the immutable snapshot. This exactly matches `GAME_RULES.md`
  §15.1, the current engine, and its regression test.
- **Post-bout:** balanced-quota ties also use `A → B`; no two-player exception or second state
  machine is involved.

## D1 deck-variant scenarios

### D01 — Single Classic population

- **Configuration:** CLASSIC ×1; two players.
- **Exposed top:** irrelevant to population; no cards are selected for an action.
- **Cards/values:** nine suited ranks `6..A`, four suits, no Jokers; 36 unique physical instances.
- **Capacity:** not applicable before a bout.
- **Expected result:** the configuration is valid with exactly 36 cards; any construction with a
  Joker or duplicate physical instance is invalid.

### D02 — Single Extended population

- **Configuration:** EXTENDED ×1; four players.
- **Exposed top:** irrelevant to population; no action selection.
- **Cards/values:** thirteen suited ranks `2..A` in four suits plus one red and one black Joker;
  `52 + 2 = 54` physical instances.
- **Capacity:** not applicable.
- **Expected result:** the configuration is valid with exactly 54 cards; omitting either Joker or a
  suited card is invalid.

### D03 — Double Classic identity and conservation

- **Configuration:** CLASSIC ×2; three players.
- **Exposed top:** `6♣` from copy 1; no action selection.
- **Cards/values:** every Classic display card has copy-1 and copy-2 instances; total 72.
- **Capacity:** not applicable.
- **Expected result:** both `K♥` instances coexist as distinct physical cards and conservation at
  72 is valid; collapsing them to one object is invalid.

### D04 — Double Extended Joker population

- **Configuration:** EXTENDED ×2; four players.
- **Exposed top:** red Joker from copy 1; no action selection.
- **Cards/values:** 104 suited instances, two red Jokers, and two black Jokers; total 108.
- **Capacity:** not applicable.
- **Expected result:** conservation at 108 with exactly two Jokers of each color is valid; treating
  same-color copies as one physical card is invalid.

### D05 — Exact duplicates in a same-rank batch

- **Configuration:** CLASSIC ×2; two players.
- **Exposed top:** `6♣`; neither selected King is trump.
- **Selected cards/values:** copy-1 `K♥ = 18` and copy-2 `K♥ = 18`; both have logical rank K.
- **Capacity:** defender hand 7, so `max_add_now = 7`; batch length 2.
- **Expected result:** the two-card same-rank initial batch is legal and retains two physical IDs.

### D06 — Duplicate identity survives movement

- **Configuration:** CLASSIC ×2; three players.
- **Exposed top:** `8♣`; selected cards are the two physical `K♥` instances, each 18.
- **Sequence/capacity:** with cap 7, both Kings legally enter one same-rank packet; after TAKE both
  move to the defender's hand, and a later refill moves neither existing card.
- **Expected result:** both IDs remain independently present through hand → table → hand/refill;
  replacing or merging either instance is invalid.

### D07 — Classic ordinary suit trump

- **Configuration:** CLASSIC ×1; two players.
- **Exposed top:** `7♥`.
- **Selected cards/values:** `8♥ = 16` and `8♠ = 8`.
- **Capacity:** defender hand 7; each one-card action fits.
- **Expected result:** the Heart is trump by suit and the Spade is not; those effective values are
  canonical.

### D08 — Classic ordinary rank trump

- **Configuration:** CLASSIC ×1; four players.
- **Exposed top:** `7♥`.
- **Selected cards/values:** `7♠ = 14` and `8♠ = 8`.
- **Capacity:** defender hand 7; selected one-card actions fit.
- **Expected result:** the Seven is trump by rank while the unrelated Eight is not.

### D09 — Extended Heart top trumps red Joker

- **Configuration:** EXTENDED ×1; two players.
- **Exposed top:** `7♥`.
- **Selected cards/values:** red Joker `50`; black Joker `25`.
- **Capacity:** defender hand 7; one selected Joker fits.
- **Expected result:** selecting the red Joker uses trump value 50; treating the black Joker as
  trump is invalid.

### D10 — Extended Diamond top trumps red Joker

- **Configuration:** EXTENDED ×1; three players.
- **Exposed top:** `4♦`.
- **Selected cards/values:** red Joker `50`; black Joker `25`; `4♣ = 8` by rank.
- **Capacity:** defender hand 7; each stated one-card action fits.
- **Expected result:** red Joker and every suited Four are trump; black Joker remains non-trump.

### D11 — Extended Spade top trumps black Joker

- **Configuration:** EXTENDED ×1; four players.
- **Exposed top:** `10♠`.
- **Selected cards/values:** black Joker `50`; red Joker `25`; `3♠ = 6`.
- **Capacity:** defender hand 7; one-card actions fit.
- **Expected result:** black Joker and every Spade are trump; red Joker is not.

### D12 — Extended Club top trumps black Joker

- **Configuration:** EXTENDED ×1; two players.
- **Exposed top:** `Q♣`.
- **Selected cards/values:** black Joker `50`; red Joker `25`; `Q♥ = 30` by rank.
- **Capacity:** defender hand 7; each one-card action fits.
- **Expected result:** black Joker and every suited Queen are trump; red Joker remains 25.

### D13 — Ordinary top affects both same-color Joker copies

- **Configuration:** EXTENDED ×2; four players.
- **Exposed top:** `9♦` from copy 1.
- **Selected cards/values:** both red Joker instances are 50; both black Joker instances are 25.
- **Capacity:** defender hand 7; a two-red-Joker same-rank batch has length 2 and fits.
- **Expected result:** both red Joker copies are trump and remain distinct; no black Joker is trump.

### D14 — Exposed red Joker trumps red suits

- **Configuration:** EXTENDED ×1; three players.
- **Exposed top:** red Joker.
- **Selected cards/values:** `5♥ = 10`, `6♦ = 12`, `5♣ = 5`.
- **Capacity:** defender hand 7; each stated selection fits.
- **Expected result:** Hearts and Diamonds are trump; Clubs are not.

### D15 — Exposed red Joker trumps every red Joker copy

- **Configuration:** EXTENDED ×2; two players.
- **Exposed top:** red Joker from copy 1.
- **Selected cards/values:** the playable red Joker from copy 2 is `50`; the exposed copy-1 red
  Joker is also classified as trump while it remains at the draw-pile front.
- **Capacity:** defender hand 7; selecting the playable copy-2 red Joker as one card fits.
- **Expected result:** every red Joker physical instance is trump, including the other copy; each
  remains independently identified.

### D16 — Exposed red Joker leaves black Joker normal

- **Configuration:** EXTENDED ×2; four players.
- **Exposed top:** red Joker from copy 2.
- **Selected cards/values:** both black Joker instances are 25.
- **Capacity:** defender hand 7; a two-card same-rank batch fits.
- **Expected result:** the black Jokers may relate by logical rank but are not trump; assigning 50
  to either is invalid.

### D17 — Exposed black Joker trumps black suits

- **Configuration:** EXTENDED ×1; three players.
- **Exposed top:** black Joker.
- **Selected cards/values:** `5♣ = 10`, `6♠ = 12`, `5♥ = 5`.
- **Capacity:** defender hand 7; each stated selection fits.
- **Expected result:** Clubs and Spades are trump; Hearts are not.

### D18 — Exposed black Joker affects only black Jokers

- **Configuration:** EXTENDED ×2; four players.
- **Exposed top:** black Joker from copy 1.
- **Selected cards/values:** the playable copy-2 black Joker is 50; the exposed copy-1 black Joker
  is also classified as trump; both red Joker instances are 25.
- **Capacity:** defender hand 7; either playable Joker as a one-card action fits.
- **Expected result:** both black copies are trump and both red copies are non-trump; cross-color
  Joker rank equality does not change trump color.

### D19 — Empty pile removes every trump

- **Configuration:** EXTENDED ×2; two players.
- **Exposed top:** none because the draw pile is empty.
- **Selected cards/values:** red Joker `25`, black Joker `25`, `A♥ = 20`, `7♥ = 7`.
- **Capacity:** defender hand 7; each stated one-card action fits.
- **Expected result:** no card is trump; using 50 for a Joker or doubling a suited card is invalid.

### D20 — Exact exposed-card duplicate doubles only once

- **Configuration:** CLASSIC ×2; two players.
- **Exposed top:** copy-1 `K♥`.
- **Selected cards/values:** copy-2 `K♥ = 36`, matching both exposed rank and suit.
- **Capacity:** defender hand 7; the one-card selection fits.
- **Expected result:** effective value 36 is canonical; an ×3 value of 54 is invalid.

### D21 — Classic low initial street

- **Configuration:** CLASSIC ×1; two players.
- **Exposed top:** `A♣`; selected non-trump ranks `6-7-8-9-10`.
- **Selected values/capacity:** base values `6+7+8+9+10`; defender hand 7; batch length 5.
- **Expected result:** five distinct consecutive Classic ranks form a legal initial attack.

### D22 — Classic high initial street

- **Configuration:** CLASSIC ×1; four players.
- **Exposed top:** `6♣`; selected non-trump ranks `10-J-Q-K-A`.
- **Selected values/capacity:** `10, 12, 15, 18, 20`; defender hand 7; batch length 5.
- **Expected result:** `10-J-Q-K-A` is a legal initial street for the lead attacker only.

### D23 — Classic wrap is illegal

- **Configuration:** CLASSIC ×1; three players.
- **Exposed top:** `10♣`; selected ranks `K-A-6-7-8`.
- **Selected values/capacity:** five physical cards; defender hand 7, so size alone fits.
- **Expected result:** the initial attack is illegal because Classic does not wrap from Ace to Six.

### D24 — Classic street with duplicates

- **Configuration:** CLASSIC ×2; two players.
- **Exposed top:** `6♣`; selected ranks `10-J-Q-K-A + J + Q` using separate instances.
- **Selected values/capacity:** five distinct consecutive ranks, seven physical cards; defender
  hand 7 gives cap and `max_add_now` 7.
- **Expected result:** the complete seven-card initial batch is legal; duplicate J/Q cards add no
  distinct street positions but belong to the run.

### D25 — Duplicate cannot create a fifth Classic position

- **Configuration:** CLASSIC ×2; four players.
- **Exposed top:** `6♣`; selected ranks `10-J-Q-K + Q`.
- **Selected values/capacity:** four distinct ranks, five physical cards; defender hand 7.
- **Expected result:** the initial attack is illegal as a street because the duplicate Queen does
  not raise distinct run length from four to five.

### D26 — Extended low initial street

- **Configuration:** EXTENDED ×1; two players.
- **Exposed top:** `A♠`; selected non-trump ranks `2-3-4-5-6`.
- **Selected values/capacity:** `2, 3, 4, 5, 6`; defender hand 7; batch length 5.
- **Expected result:** the five lowest Extended ranks form a legal initial attack.

### D27 — Extended Ace-high initial street

- **Configuration:** EXTENDED ×1; three players.
- **Exposed top:** `2♣`; selected non-trump ranks `10-J-Q-K-A`.
- **Selected values/capacity:** `10, 12, 15, 18, 20`; defender hand 7; batch length 5.
- **Expected result:** the batch is a legal initial street.

### D28 — Extended street reaches Joker

- **Configuration:** EXTENDED ×1; four players.
- **Exposed top:** `2♣`; selected ranks `10-J-Q-K-A-Joker`, using the red Joker at value 25.
- **Selected values/capacity:** six distinct consecutive ranks; defender hand 7; batch length 6.
- **Expected result:** the initial attack is legal because Joker follows Ace in Extended order.

### D29 — Extended wrap is illegal

- **Configuration:** EXTENDED ×1; two players.
- **Exposed top:** `10♣`; selected ranks `A-Joker-2-3-4`.
- **Selected values/capacity:** five physical cards; defender hand 7, so size alone fits.
- **Expected result:** the attack is illegal because Extended never wraps from Joker to Two.

### D30 — Two Jokers do not create two street positions

- **Configuration:** EXTENDED ×2; three players.
- **Exposed top:** `2♣`; selected ranks `Q-K-A-red Joker-black Joker`.
- **Selected values/capacity:** four distinct ranks (`Q, K, A, Joker`) across five physical cards;
  defender hand 7.
- **Expected result:** the initial attack is illegal as a street because both Joker colors occupy
  the same terminal rank.

### D31 — Both Joker colors share the terminal run rank

- **Configuration:** EXTENDED ×1; four players.
- **Exposed top:** `2♣`; selected ranks `10-J-Q-K-A-red Joker-black Joker`.
- **Selected values/capacity:** six distinct ranks and seven physical cards; defender hand 7.
- **Expected result:** the batch is a legal initial street; both Jokers belong to the terminal
  Joker rank while contributing only one distinct position.

### D32 — Seven-card street fills a seven-card cap

- **Configuration:** CLASSIC ×2; two players.
- **Exposed top:** `6♣`; selected `10-J-Q-K-A + J + Q`.
- **Selected values/capacity:** five distinct run ranks, seven physical cards; defender has seven,
  so `bout_attack_cap = max_add_now = 7`.
- **Expected result:** the initial attack is legal and exhausts the shared cap.

### D33 — Eight physical street cards exceed a seven-card cap

- **Configuration:** CLASSIC ×2; three players.
- **Exposed top:** `6♣`; selected `10-J-Q-K-A + J + Q + K`.
- **Selected values/capacity:** five distinct run ranks, eight physical cards; defender has seven,
  so `max_add_now = 7`.
- **Expected result:** the complete batch is rejected atomically for size despite a valid rank run.

### D34 — Ten-card street may fit a ten-card defender

- **Configuration:** CLASSIC ×2; four players.
- **Exposed top:** `6♣`; selected both physical copies of each rank `10-J-Q-K-A`.
- **Selected values/capacity:** five distinct run ranks, ten physical cards; defender has ten, so
  `bout_attack_cap = max_add_now = 10`.
- **Expected result:** the complete initial batch is legal; there is no special seven-card street
  limit.

### D35 — Extended post-response street uses table history

- **Configuration:** EXTENDED ×1; three players.
- **Exposed top:** `2♣`; physical table ranks are `10, J, K, A`; current attacker selects
  `Q + red Joker`.
- **Selected values/capacity:** selected values 15 and 25; two shared-cap slots and at least two
  defender cards remain.
- **Expected result:** the throw-in batch is legal because table plus selection forms
  `10-J-Q-K-A-Joker`; historical table cards remain rank evidence.

### D36 — Closed initial street cannot justify an omitted duplicate

- **Configuration:** CLASSIC ×2; two players.
- **Exposed top:** `6♣`; attacker initially selects `10-J-Q-K-A` and retains a second Queen.
- **Selected values/capacity:** initial length 5 under cap 7; after defender response, capacity
  remains but no new table reason authorizes Q.
- **Expected result:** the retained Queen is illegal on the old initial-street rationale; the
  initial window is closed.

### D37 — Red and black Jokers satisfy same-rank mechanics

- **Configuration:** EXTENDED ×1; two players.
- **Exposed top:** `2♥`; red Joker is 50 and black Joker is 25, but both have logical rank Joker.
- **Selected cards/capacity:** red Joker + black Joker; defender hand 7; batch length 2.
- **Expected result:** the pair is legal under the ordinary same-rank initial-attack rule despite
  different effective values; color-dependent trump remains unchanged.

### D38 — Joker is a normal value-bearing transfer target

- **Configuration:** EXTENDED ×1; three players.
- **Exposed top:** `2♣`; a non-trump red Joker attacks for 25; defender selects
  `10♥ + Q♥ = 25`.
- **Selected values/capacity:** transfer selection totals exactly 25; receiving defender has at
  least three cards, so the resulting three-card packet fits.
- **Expected result:** the transfer is legal by exact value; the Joker is not wild and substitutes
  for no rank.

### D39 — Single Classic two-player compatibility

- **Configuration:** CLASSIC ×1; two players.
- **Exposed top:** `7♥`.
- **Selected cards/values:** attacker selects `K♣ = 18`; defender selects `J♣ + 7♣ = 26`
  because the Seven is trump at 14.
- **Capacity:** defender begins with seven; one attack card fits; the two-card defense is strictly
  greater and irredundant (`26-12=14`, `26-14=12`).
- **Expected result:** defense is legal under unchanged current rules; D1 changes this mode only by
  adding initial-street legality.

### D40 — Extended deck keeps the multiplayer state machine

- **Configuration:** EXTENDED ×2; four players `A → B → C → D`.
- **Exposed top:** red Joker from copy 1.
- **Selected cards/values:** A selects the initial street `10-J-Q-K-A-red Joker` using the copy-2
  red Joker at 50 against B.
- **Capacity:** six distinct ranks, six physical cards; B has seven, so the batch fits; A alone owns
  the initial window.
- **Expected result:** the initial attack is legal, B remains the one defender, attacker order stays
  `A → C → D`, and refill order stays `A → C → D → B`; no second multiplayer state machine exists.

## Scenario-level invariant summary

Together these scenarios require every conforming implementation to preserve the following
observable facts:

- roles and all traversal derive from one stable clockwise active-seat ring;
- only the lead owns the initial window, which may use the recovered profile-aware street basis;
- batches are atomic before defender response;
- attacker phases may repeat internally but never cycle back after closing;
- one defender-tenure cap is shared by every attacker;
- defense, transfer arithmetic, and table math remain the current canon;
- transfer chains run without unrelated attacker actions and may replace the lead only when the
  prior lead becomes defender;
- TAKE and final-card BITO cancel every pending phase;
- refill order is captured from bout-start roles, survives transfers unchanged, and supplies the
  deterministic tie-break for balanced quotas before physical draw;
- finish is evaluated only after complete resolution/refill, with simultaneous finish groups and
  no fabricated final loser.
- deck configuration is profile × copy count, physical instances never collapse, trump doubles
  once, and street order is profile-specific, distinct-rank based, and non-wrapping.
