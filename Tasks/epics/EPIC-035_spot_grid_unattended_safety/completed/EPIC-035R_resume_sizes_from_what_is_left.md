# EPIC-035R — Resume sizes from what is left

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M9 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 4 of [EPIC-035](../README.md).
**Risk:** 🟡 — the audit marks this finding as inferred
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit M9 (inferred): on resume from HALTED, inventory beyond the SELL levels is left unplaced and the BUY side is still sized from the original `capital_quote` after losses. Cited: `src/modules/bots/domain/grid/grid_ladder.py:75-90`. First step: reproduce it with a test; if it does not hold, say so in this task and close it.

**Re-verified on `d563c0f` (2026-10-08): both halves hold.** `resized_for_inventory` (`grid_ladder.py`, the cited lines are right) sized only the SELL side; the BUY levels kept the share of the whole `capital_quote` that `plan()` gave them. Reproduced red before the change by `test_resume_after_a_loss_does_not_oversize_the_buy_side`: 800 USDT of inventory at cost under a 1 000 USDT capital still got 499.92 USDT of BUYs proposed. Trading refuses open BUYs plus the inventory at cost beyond `max_exposure_quote` (= `capital_quote`, `grid_budget`), so the surplus BUY asked for what the budget would refuse. The second half is also real: an inventory above the SELL levels' total (the price is high on the ladder, few SELL levels remain) was left held with no word to the user.

One refinement of the audit's wording: "the actual remaining equity" is not a figure the bot has (it knows no per-bot quote balance). What is known, from exchange evidence, is the inventory and its **cost**, and trading's own exposure rule is "open BUY quote plus the inventory at cost". So "what is left" is `capital_quote − inventory cost`: the same quantity the gate refuses against, never a second opinion.

## 2. Acceptance criteria
- [x] Resume sizes the BUY side from what is left of the capital after the inventory at cost (`buys_within_capital`): the BUY levels share it equally, never more than their planned share; a share under the exchange's NOTIONAL minimum leaves that level EMPTY; nothing left leaves no BUY. Evidence: `test_resume_after_a_loss_does_not_oversize_the_buy_side`, `test_resume_with_the_whole_capital_in_inventory_proposes_no_buy`, `test_a_buy_share_under_the_minimum_notional_leaves_that_level_empty`, `test_the_confirmed_ladder_asks_only_for_what_is_left` (the orders that go out, not only the proposal), and the four domain tests in `test_grid_ladder.py`. A resume that lost nothing proposes the BUY side it always did (`test_a_resume_that_lost_nothing_keeps_the_buy_side_it_always_had`).
- [x] Inventory in excess of the SELL levels is reported, not silently kept: `ResumeProposal.unplaced_inventory`, and one sentence on the HALTED bot's reason ("resume proposal: 1.868 BTC of the inventory has no SELL level to go on and stays unplaced"), replaced by the next resume's and removed when nothing is left over. Evidence: `test_inventory_beyond_the_sell_levels_is_named_not_kept_in_silence`, `test_a_second_resume_names_the_excess_once`, `test_an_inventory_the_sell_levels_cover_is_not_reported`. *Reported, not placed:* a SELL level the plan does not have would be a new rung, which is a different ladder; Stop sells or keeps the base as the user chooses.

## 3. Design
Two pure domain functions beside `resized_for_inventory`, which keeps its signature (its tests are untouched): `buys_within_capital(plan, left, rules)` and `unplaced_inventory(plan, inventory)`. `GridResumeSequence._proposal_for` composes the three and `_name_unplaced` writes the sentence; `LadderRules` (step, minimum notional) is the existing domain type the reactions already use.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/grid_ladder.py` | `buys_within_capital`, `unplaced_inventory` |
| `src/modules/bots/application/services/grid_resume_sequence.py` | composes them; `ResumeProposal.unplaced_inventory`; the sentence on the bot |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | the resume journey and the behaviour row |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test was shown red before the change (7 of the 8 in `test_grid_resume_sizing.py` failed on the assertion, the eighth is the unchanged-behaviour guard that was green already). Unit tier, against the real executor through the real factory: `tests/unit/modules/bots/application/services/test_grid_resume_sizing.py`, plus the domain tests in `tests/unit/modules/bots/domain/grid/test_grid_ladder.py`.

Green after: the above, the whole `tests/unit/modules/bots` and `tests/unit/modules/trading`, `tests/unit/architecture` (703); the commit tier PASS.

## Implementation notes
- The BUY side is sized from `capital_quote − inventory.cost`, not from the realised profit: trading's exposure gate does not count profit either, and a larger BUY side than the gate admits is the defect.
- Not done: a profit above the capital does not grow the BUY side (the exposure cap is `capital_quote`).

## Resume
Done. Nothing owed.
