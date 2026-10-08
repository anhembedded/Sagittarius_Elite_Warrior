# EPIC-035J — The reference price has an age

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M1 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 2 of [EPIC-035](../README.md).
**Risk:** 🟡 — resume, stop slicing and the dust check can use a price hours old
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035A (merged)

---

## 1. Context and problem
Audit M1: `_price()` prefers the last tick over a fresh book read, so resume proposals, stop slicing and the dust check can use a stale price, and a confirmed proposal is never re-priced.

**Verified ✅ on `be67b47` (claims re-checked before the first test).**
- `GridExecutor._price()` was `self._prices.last_price or self._context.gateway.market_price()` (`grid_executor.py:352-353`; the audit cites 384-385, the file is shorter in this tree). `last_price` was set by every tick and never aged: a bot HALTED or PAUSED overnight proposed a resume from the last tick of the night before, and `GridStopper` (`grid_stopper.py:86`) sliced a stop and `grid_stop_sequence.py:138-144` judged dust at the same number.
- `GridResumeSequence.confirm` (`grid_resume_sequence.py`) laid `proposal.plan` unchanged: a proposal confirmed minutes or hours later was never re-priced. **Reproduced red** by the tests below.
- The audit's range `grid_resume_sequence.py:495-532` does not exist: that file is 114 lines. The finding holds on the lines above; only the citation was wrong.

## 2. Acceptance criteria
- [x] The reference price carries its timestamp. — `GridReferencePrice` (`grid_reference_price.py`) holds the price and the monotonic moment it was heard, from a tick or from the book. `test_the_refreshed_price_carries_its_own_age`.
- [x] When older than a named limit it is refreshed from the book ticker before use. — `REFERENCE_PRICE_MAX_AGE_SECONDS` (10 s, five missed pushes of a two-second stream) in `domain/grid/reference_price.py`; every use that went through `_price()` (opening plan, resume proposal, stop slices, dust check) gets it. `test_a_stale_price_is_refreshed_before_a_resume_proposal`, `test_a_stop_sells_at_a_refreshed_price_not_an_hours_old_tick`, `test_a_fresh_tick_is_used_without_reading_the_book`.
- [x] A confirmed resume proposal is re-priced just before placing and refused with a named reason if it moved beyond a named tolerance. — `RESUME_PRICE_TOLERANCE` (1 % of the proposed price); the refusal is `GridReason.PROPOSAL_PRICE_MOVED`, the bot stays HALTED, nothing is laid, the proposal is dropped and a fresh Resume proposes again. `test_a_proposal_that_moved_is_refused`, `test_a_proposal_is_repriced_from_the_book_even_when_a_tick_is_fresh`, `test_a_proposal_inside_the_tolerance_is_laid`, `test_after_a_refusal_resuming_again_proposes_at_the_new_price`.

## 3. Design
Builds on the monotonic clock of `EPIC-035A` (`IMonotonicClock`); no new clock or timer. The price is a collaborator of the run context, not state in `GridPriceReaction`, so the executor gains no member (`GridExecutor` is over its public-surface limit; `_price` only changes body). The confirmation always reads the book (`fresh()`), not the tick: a tick says what the market did a moment ago, the book what a limit order would sit against. A book that cannot be read at confirmation refuses the ladder with the same reason rather than raising: an unreadable price must not turn a deliberate resume into ERROR.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/reference_price.py` (new) | The two named limits and their pure rules |
| `src/modules/bots/application/services/grid_reference_price.py` (new) | The price with its moment; `current()` and `fresh()` |
| `src/modules/bots/application/services/grid_run_context.py`, `grid_executor_factory.py` | `reference_price` in the run context, built over the monotonic clock and the gateway's book read |
| `src/modules/bots/application/services/grid_price_reaction.py` | A tick notes the price there; the unaged `last_price` is gone |
| `src/modules/bots/application/services/grid_executor.py` | `_price()` reads `reference_price.current()` |
| `src/modules/bots/application/services/grid_resume_sequence.py` | `confirm` re-prices and refuses |
| `src/modules/bots/domain/grid/grid_runtime.py` | `GridReason.PROPOSAL_PRICE_MOVED` |
| `src/modules/trading/contracts/testing/fake_order_entry_terms.py` | Test helpers `quote`, `unquote`, `book_reads` (verified in `tests/unit/modules/trading/contracts/test_fake_order_entry_terms.py`) |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | The journey and its test row |

## 5. Testing
Red at `be67b47`'s behaviour, then green (6 of 8 new executor tests failed first: the stale price proposed `121` against a book at `135`; the stop sold at `121` against `125`; the moved proposal was laid, RUNNING; the two guards `test_a_fresh_tick_is_used_without_reading_the_book` and the tolerance-inside test passed before and after, pinning that a healthy feed never reads the book).
- `tests/unit/modules/bots/application/services/test_grid_executor_reference_price.py` (9 tests), `tests/unit/modules/bots/domain/grid/test_reference_price.py` (boundaries).
- Mutation measured: removing the `fresh()` call in `confirm` fails `test_a_proposal_that_moved_is_refused` and `..._even_when_a_tick_is_fresh`.

## Implementation notes
- **Dust check and stop slicing** are covered by the one change to `_price()`; they take no separate edit.
- **Not changed:** the price an order's own limit is built from (the ladder's levels), which the plan fixes; the price the opening *market buy* quotes (`plan.last_price`) is the plan's, which is now at most 10 s old or the book's.
- **Residual:** the 10 s limit is a constant, not a setting; a thin pair with a quiet stream reads the book once per use after 10 s, which is a handful of reads per hour at most.

## Resume
Done. Delivered in the EPIC-035D/035J pull request.
