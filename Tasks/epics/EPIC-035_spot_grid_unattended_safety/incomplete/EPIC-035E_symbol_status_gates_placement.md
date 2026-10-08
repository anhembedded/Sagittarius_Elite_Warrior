# EPIC-035E — Symbol status gates placement

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M5 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 2 of [EPIC-035](../README.md).
**Risk:** 🟡 — placing on a halted symbol fails into ERROR instead of a named pause
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit M5: the symbol status (TRADING, BREAK, HALT, CANCEL_ONLY, and a delisting) is parsed but nothing reads it; `src/modules/trading/adapters/binance/spot/spot_metadata_parser.py:160` has no consumer. The bot keeps submitting, is rejected and goes to ERROR; `CANCEL_ONLY` was introduced on 2026-07-07 (audit's source). Verify the parser line and the absence of a consumer by `grep` first.

This task is specified briefly: it is Phase 2 — Infrastructure resilience. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] Exchange terms carry the symbol status through the bots module's exchange-terms seam.
- [ ] Placement is gated on status TRADING: any other status PAUSEs (or HALTs for a delisting) the bot with a named reason before a submit is attempted.
- [ ] A bot paused for status resumes only by the user, after the status is TRADING again; the status is shown on the bot.
- [ ] In CANCEL_ONLY the bot still cancels on Stop.

## 3. Design
The terms refresh of `EPIC-035U` is the feed that keeps the status current; until it lands, the status is read at Start and when an order is rejected with a status-class error.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/bot_exchange_terms.py` | as the criteria require |
| `src/modules/trading/adapters/binance/spot/spot_metadata_parser.py` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_a_symbol_in_break_pauses_the_bot_with_a_named_reason` (red before: ERROR)
- `test_cancel_only_still_allows_stop`
- `test_a_delisting_halts_the_bot`

Not run yet.

## Resume
Not started.
