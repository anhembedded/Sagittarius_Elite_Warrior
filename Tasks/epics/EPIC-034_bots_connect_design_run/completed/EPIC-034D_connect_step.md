# EPIC-034D — Connect: one account snapshot per venue gates the chart and the plan

**Status:** ✅ Done (2026-10-07)
**Source:** the owner, 2026-10-07 — *"bot không start được tui cũng không biết nó đang thiếu gì"* (the bot does not start and I cannot tell what it lacks); the epic's origin has the rest.
**Risk:** 🟡 — a new port read by the whole Bots mode
**Complexity:** M — a port, a snapshot value object, a failure kind, the identity strip
**Epic:** [EPIC-034](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-034A](../incomplete/EPIC-034A_bots_mode_says_what_it_knows.md)

---

## 1. Context and problem
Decision D1: a bot's first step is Connect. Today the chart and the plan open whether or not the account can be read, and a Spot Testnet maintenance page reaches the log as an "unclassified exception" (the owner's `-TestnetOnly` run, 2026-10-07: `APIError(code=0): Invalid JSON error message from Binance: <html>`).

## 2. Acceptance criteria
- [x] Selecting a bot reads its venue's account once (balances, commission, the key's permission to trade, the symbol's filters and price) into an immutable `VenueAccountSnapshot` with its read time; bots on the same venue share it; it is re-read on a timer and on Refresh (D6).
- [x] Until the snapshot succeeds, the chart and the Plan are disabled and say why in the user's words: no key, key rejected (`KEY_REJECTED`), exchange under maintenance (a new `MAINTENANCE` kind for an HTML answer), network; with Retry.
- [x] An identity strip above the bot shows its name, kind, venue title with the Connect result and the available balances, and its saved state; the status bar shows the selected bot's venue.
- [x] Reading never needs trading and never places anything.

## 3. Design
An application port `IVenueAccountReader` returning a `VenueAccountSnapshot` or a `ConnectFailure`; the Binance adapter reuses the readers that exist. The step state starts the readiness FSM that `EPIC-034H` completes; this task adds only the Connect states, in a `*_fsm_matrix.py`. Decisions: [DECISION_2026-10-07_bots_mode_flow.md](../DECISION_2026-10-07_bots_mode_flow.md).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/` | the port and the snapshot |
| `src/modules/trading/adapters/binance/` | the adapter, the `MAINTENANCE` classification |
| `src/modules/bots/ui/bots_screen/` | identity strip, gating |

## 5. Testing
Unit: the classification of an HTML answer, red first; the gate on the real presenter. Integration on the composed app with the fake Binance server. A reviewer is required. Not run.

## Implementation notes (written when done)
**Delivered** on branch `claude/epic-034-pr3-connect-mainnet-readonly` (PR-3, with `EPIC-034E`).

| Criterion | Evidence |
| :--- | :--- |
| One immutable snapshot per read, shared by bots on a venue and symbol, re-read on a timer and on Refresh | `VenueAccountSnapshot` (`trading/contracts/venue_account_snapshot.py`); `ConnectStep` shares a read younger than 30 s and re-reads every 60 s; `test_bots_connect_step.py::test_bots_on_the_same_venue_and_symbol_share_one_read`, `::test_a_read_that_is_no_longer_fresh_is_made_again`, `::test_the_timer_re_reads_and_a_failed_re_read_locks_the_chart` |
| Chart and Plan disabled with the reason, Retry | `::test_until_the_account_is_read_the_chart_and_the_plan_wait`, `::test_an_exchange_under_maintenance_locks_both_and_says_so_with_a_retry`, `::test_retrying_reads_again_and_opens_what_was_locked`; Retry is the Bots menu command "Retry venue account" because the mode holds no push button (`ui-presentation-rule.md` §6) |
| `MAINTENANCE` for an HTML answer | `test_html_answer_is_maintenance.py` (red first: the HTML answer classified `NETWORK` and logged "unclassified exception"); end to end on the fake Binance server with its new maintenance switch: `test_a_maintenance_page_is_named_not_left_unclassified` |
| Identity strip; the status bar shows the bot's venue | `identity_strip.py`; `::test_once_read_the_chart_and_the_plan_open_and_the_strip_says_who_and_where`, `::test_the_status_bar_names_the_selected_bots_venue_by_its_title`. The strip uses the venue's title, never `spot_testnet`; the window's status bar word is the Bots mode's own `IStatusSource` label |
| Reading never needs trading and places nothing | the port `IVenueAccountReader` holds read ports only (`ComposedVenueAccountReader` takes a `VenueContext` and calls `check_connection`, `commission_rate`, `get_or_fetch`, `best_bid_ask`); `test_the_connect_step_reads_the_account_through_the_composed_app` asserts no order route was called on the fake server while trading is off |

**Decisions.**
- **A key that cannot trade** opens the chart and keeps Start refused (`KEY_CANNOT_TRADE`); an unknown flag (`can_trade is None`) never blocks. `canTrade` is the account's own flag from `GET /api/v3/account` and `GET /fapi/v2/account`, new on `ExchangeConnectionStatus` with a default; the key's permission list is `EPIC-034E`.
- **Reasons that name the venue use its title.** `AccountSource` (new, `support/binance_gateway/contracts/account_source.py`) carries `venue_title`; `EPIC-034E` adds the read-only mainnet member there, and nowhere near `TradingVenue`.
- **The failure vocabulary is the existing `ConnectionFailureKind`** plus `MAINTENANCE`; the bots words (`connect_words.py`) are an `EnumLabels` so a new kind cannot reach the screen without a sentence.
- **Reuse of `PR-1`'s classifier.** It had not landed when this was written; `MAINTENANCE` and its one-line rule are added to `connection_failure.py` in a small, separate block (`_is_not_json_answer`), so `BUG-168` can merge into it.
- **The presenter stayed under 400 lines** by moving its pacing constants to `presenter_pacing.py` and keeping the step's lifecycle, effects and words in their own files.
- **Not delivered here:** the Design step's balance checks (`EPIC-034F` reads the snapshot); the identity strip's balance line shows what a new order can spend, not the equity.

**Verification.** Commit tier `ci-local.ps1 -SkipTests` PASS (`logs/ci-local-20261007-065321.log`, before the last renames; rerun in the commit below); architecture guards; `tests/unit` and `tests/integration` run by hand: 8,811 passed, one pre-existing failure (`test_workbench_conformance[True-1024x700]`, backtest mode, identical on `master-warrior` in this container). The full gate is GitHub Actions'.

