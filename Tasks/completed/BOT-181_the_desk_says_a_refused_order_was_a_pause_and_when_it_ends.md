# BOT-181 — The desk's headline for an order the exchange's pause refused says it was a pause and when it ends

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** A manual order the exchange's pause refused reads "The order could not be sent…"; the pause and the instant it ends are only in the notice's Details. Say it in the headline.
**Source:** Review of PR #531 (`BUG-217`) and the coordinator, 2026-10-15: "the desk's headline for an order the pause refused should say it was a pause and when it ends."
**Risk:** 🟢 — wording of one notice and one panel line; no behaviour change.
**Complexity:** S — one failure kind to map, one sentence, its test.
**SPEC (optional):** [SPEC-014](../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** None (`BUG-217` is merged)

---

## 1. Context and problem
`BUG-217` demoted the Engine dispatcher's per-call ERROR for a call the pause refused, on the argument that the desk already shows a refused manual order. It does (`order_entry_presenter.py:362` logs a WARNING; `order_entry_failures.py:81` `submit_failed` writes the panel's error line and raises a COMMAND notice), but the headline is the generic "The order could not be sent…". The pause text (`ExchangeRateLimitedError`, tagged `[exchange-pause]`) and the instant it ends (`retry_after`) are only in the Details. A user who clicks Buy during a pause is told the order failed, not that nothing can be sent for N s.

## 2. Acceptance criteria
- [ ] A submit refused by `ExchangeRateLimitedError` gives the panel line and the notice headline a sentence that says the exchange asked for a pause and until when (local time), and that the order was not sent.
- [ ] A banned pause says it is a ban.
- [ ] Every other failure keeps its words.

## 3. Design
Map the exception in `submit_failure_of` (`order_entry_failures.py`) to its own failure kind with its own headline, as the other typed failures are; do not parse the message. `retry_after` is already on the error.

## 3a. Reuse
`INotifier`, `FailureNotice`, `FailureKind` (`.claude/rules/capabilities.md`): used. `APP_VALUE_FORMATTER` for the instant: used.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/desk/order_entry_failures.py` | the pause's headline and panel line |
| `tests/unit/modules/trading/ui/desk/test_order_entry_failures.py` | extend the test `BUG-217` added |

## 5. Testing
Unit: the existing `test_an_order_the_exchanges_pause_refused_is_shown_to_the_user_and_logged_at_warning` asserts the new headline; a ban; an unrelated failure unchanged.

## 6. Docs touched
none, because the sentence is a UI string; `Docs/SPEC/SPEC-014` row for the pause names the desk's wording if it quotes it.
