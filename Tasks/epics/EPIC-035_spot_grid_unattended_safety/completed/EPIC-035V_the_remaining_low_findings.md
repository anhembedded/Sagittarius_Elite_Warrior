# EPIC-035V — The remaining low findings

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding L4, L6, L7, L8, L9 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 4 of [EPIC-035](../README.md).
**Risk:** 🟢 — five small, independent items; slice into child PRs if any grows
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None
**Board:** L4 documented as intended and locked, L6 the Start use case refuses an unconfirmed mainnet start, L7 orders already open on the symbol are advised against the open-order limit, L8 shutdown joins a worker for at most 10 s, L9 a Stop ends a running Start between its orders; and the periodic `SpotAccountReader equity: priced …` line is DEBUG and read once per tick, not twice.

---

## 1. Context and problem
Audit L4: a top-level BUY fill gets no counter SELL (`src/modules/bots/domain/grid/grid_reactions.py:336`). L6: the real-money confirmation is enforced only in the UI (`src/modules/bots/ui/bots_screen/bot_commands.py:77`). L7: foreign open orders on the symbol are not refused or warned about (`src/modules/trading/application/session/session_readiness.py:113-121`). L8: shutdown joins workers without a timeout (`src/modules/bots/adapters/thread_bot_work_queue.py:190-194`). L9: Stop is queued behind a long Start (`src/modules/bots/application/services/grid_executor.py:201-202`). Verify each path first: some are in files other than the audit's names.

**Each claim re-verified on `d563c0f` (`master-warrior`, 2026-10-08).** None was already fixed; two cite a place that has since moved.
| Finding | Verified | Where it is now |
| :--- | :--- | :--- |
| L4 | Holds, and is by design: `_counter` returns `None` for a target past the last level (`grid_reactions.py:321`), locked since before this task by `test_a_buy_at_the_top_and_a_sell_at_the_bottom_owe_no_counter`. A SELL "at the upper bound" would sell at the price the top BUY paid and lose both fees | `grid_reactions.py:315-340` |
| L6 | Holds: `command_for` asked `allow_real_money` (`bot_commands.py:77`) and `StartBotCommandHandler` asked nothing, so any other caller started a mainnet bot unasked | as cited |
| L7 | Holds, **not** at the cited lines: `session_readiness.py:113-121` reconciles *positions*; the open orders it reads (`get_open_orders`) only travel back in the result. No code counted foreign open orders against any limit | `planner_numbers.py`, `grid_checks.py` |
| L8 | Holds, **file moved**: `thread_bot_work_queue.py` has 55 lines; the unbounded `Thread.join()` is in `close()` (line 43) | `thread_bot_work_queue.py:39` |
| L9 | Holds: `GridExecutor.stop` only posted behind the running `_run_start` (the one writer), which laid every paced order first | `grid_executor.py:200` |

Also in this task, at the owner's request: **the periodic INFO line `SpotAccountReader equity: priced … via … ticker`**, twice every 5 s in the mainnet log. Cause, established by reading the scheduler wiring (`trading/module.py:300-316`): a Spot venue has two recurring jobs on one interval, `HoldingsRefreshService` and `AccountSummaryRefreshService`, and each runs its own query, and **each query makes the whole account read** (`check_connection`: ping, server time, account, a ticker per non-dust holding). So the line, and the request weight behind it, was doubled by design, and the level (INFO per holding per poll) broke `logging-rule.md` §6.

## 2. Acceptance criteria
- [x] L4: documented as intended in the SPEC (§5 row "A BUY fills on the highest level"), the existing test named as its lock. Decided here: no SELL at the upper bound, for the reason above.
- [x] L6: the Start use case requires the real-money confirmation; the UI only collects it: `StartBotCommand.real_money_confirmed`, refusal `REAL_MONEY_NOT_CONFIRMED`, checked before the account is read. Evidence: `test_a_mainnet_start_nobody_confirmed_is_refused_before_anything_is_read` (red before: the enum member did not exist; a bot was started) and the screen tests that now expect `real_money_confirmed=True`. **Not covered:** Resume and Confirm resume, which the screen also asks about, are still enforced by the screen alone: a bot that is resumed has already passed Start.
- [x] L7: foreign open orders on the symbol produce a warning that counts them against the order cap: the planner reads the symbol's open orders into `MarketView.foreign_open_orders`; `check_foreign_orders` is advice (never a block) with "N other orders are already open on this symbol; with the plan's M that is N+M against a limit of L"; an unread count (a failed read) says the check did not run. Evidence: `test_grid_foreign_orders_check.py`, `test_planner_foreign_orders.py`.
- [x] L8: shutdown joins each worker with a timeout (`CLOSE_JOIN_SECONDS = 10`), then logs a WARNING. Evidence: `test_close_gives_up_on_a_worker_stuck_in_a_task_and_says_so` (red before: `close()` waited for the stuck task; reproduced by mutating the join back).
- [x] L9: a Stop cancels a running Start cooperatively between slices: `GridExecutor.stop` sets `GridRunContext.stop_requested` from the caller's thread; the start sequence checks it before each opening slice and each ladder order and gives up; the queued Stop then ends the bot. Evidence: `test_grid_stop_during_start.py` (red before: all six orders were laid).
- [x] The noisy log: the line is DEBUG (`test_pricing_a_holding_is_a_debug_line_not_an_info_one_per_poll`, red by mutation back to INFO) and the two jobs share one read per tick (`SharedAccountStatus`, `test_shared_account_status.py`); the read after a fill is never shared.

## 3. Design
Five independent changes plus the log; none needed its own child. The one design decision of weight is the log's cause: the shared read is an application service (`trading/application/shared_account_status.py`) used only by the two refresh query handlers, with a one-second window and an injected monotonic clock. A failed status is never kept. `GetAccountSummaryQuery.fresh` is set by the read that follows a fill (`AccountSummaryRefreshService._refresh_after_fill`), so a fill's balances are never served from the tick's read. Every other caller of `check_connection()` (order gate, readiness, Emergency Stop) is untouched and reads the exchange itself.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/use_cases/start_bot/{command,handler}.py`, `contracts/bot_command_result.py`, `ui/bots_screen/bot_commands.py` | L6 |
| `src/modules/bots/domain/{bot_kind_inputs.py,grid/grid_checks.py,grid/grid_constraints.py}`, `application/services/planner_numbers.py`, `ui/kinds/grid/grid_field_errors.py` | L7 |
| `src/modules/bots/adapters/thread_bot_work_queue.py` | L8 |
| `src/modules/bots/application/services/{grid_executor,grid_run_context,grid_start_sequence}.py` | L9 |
| `src/modules/trading/application/shared_account_status.py` (new), `queries/get_holdings/handler.py`, `queries/get_account_summary/{query,handler}.py`, `account_summary_refresh_service.py`, `composition/state_bindings.py` | the log's cause |
| `src/modules/trading/adapters/binance/spot/spot_account_reader.py` | INFO to DEBUG |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | four rows in §5, six in §8 |

## 5. Testing
Unit tier throughout; each regression test was run red before its change. New: `test_start_bot_readiness.py` (three), `test_planner_foreign_orders.py`, `test_grid_foreign_orders_check.py`, `test_thread_bot_work_queue.py` (one), `test_grid_stop_during_start.py`, `test_shared_account_status.py`, `test_spot_account_reader.py` (one), `test_account_summary_refresh_service.py` (one). Changed on purpose: `test_advice_never_blocks` (the advice set gained `FOREIGN_OPEN_ORDERS`), the screen tests for Start (the command now carries the answer), `test_after_boot_a_fill_refreshes…` (`fresh=True`). Not run: a mainnet start, and a real two-job tick against a live exchange (the owner's log is the check: the line should now be absent at INFO).

## Implementation notes
- L7 counts every open order on the symbol at design time, whoever placed it; a bot that has not started has placed none, so each is foreign to it. It is read at each planner refresh (one signed request per refresh).
- L9 also covers a confirmed resume's ladder (the same `_place_ladder`).
- The shared read halves the periodic account request weight on a Spot venue; Futures venues have no holdings job and are unchanged.

## Resume
Done. Nothing owed.
