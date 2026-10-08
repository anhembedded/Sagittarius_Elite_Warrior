# EPIC-035M — PnL is complete: total, BNB fees, HODL benchmark

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding L2 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 3 of [EPIC-035](../README.md).
**Risk:** 🟢 — display and accounting only; no order path
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit L2: BNB-paid fees are ignored so profit is overstated; sells of the opening inventory and exit slices book no realised PnL; unrealised PnL comes from the chart price. This is the field complaint that grid profit and total PnL disagree. Cited: `src/modules/bots/domain/grid/grid_reactions.py:287-317`, `src/modules/bots/ui/bots_screen/bot_facts.py:99-106`. Verify.

This task is specified briefly: it is Phase 3 — Alerting and transparency. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] Total PnL (realised + unrealised) is the first figure shown; grid profit is labelled as one part of it.
- [ ] Fees paid in BNB are converted to the quote asset at the fill time and included.
- [ ] Opening-inventory sells and exit slices book realised PnL.
- [ ] Unrealised PnL uses the bot's own price (`EPIC-035A`), not the chart's.
- [ ] A HODL benchmark (what the same capital would be worth held) is shown beside the total.

## 3. Design
Domain arithmetic stays `Decimal`; no float enters.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/grid_reactions.py` | as the criteria require |
| `src/modules/bots/ui/bots_screen/bot_facts.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_bnb_fees_reduce_the_profit` (red before)
- `test_exit_slices_book_realised_pnl`
- `test_total_pnl_is_realised_plus_unrealised`
- `test_hodl_benchmark`

Not run yet.

## Resume
Not started.
