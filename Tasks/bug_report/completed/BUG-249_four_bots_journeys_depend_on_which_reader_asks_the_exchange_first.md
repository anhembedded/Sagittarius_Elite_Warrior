# BUG-249 — Four bots journeys depend on which reader of the app asks the exchange first

- **Reported:** 2026-10-21 (gate (Rest) of PR #673 was red twice on two tests the PR cannot reach; the delivery coordinator asked for the record)
- **Severity:** 🟡 P2 — the full gate is red on a machine slower than the author's, on any pull request
- **Status:** Fixed (2026-10-21)
- **Board:** `test_an_order_met_by_the_pause…` (RUNNING, no reason) and `test_n_idle_bots_read_the_accounts_positions_once_a_beat…[20]` (70 weight, 65 allowed) failed on CI only: the answer queued for the connection check, and the minute's `positionRisk` count, were met by whichever of the app's other readers asked first (a fill's account summary on the worker pool, the trading module's 5 s refresh jobs, the order gate's own 5 s reuse of a passing check). The journeys now stand those down; two sister journeys had the same exposure.
- **Context:** `tests/integration/modules/bots/` (the pause journeys and the idle-bots weight test), `OrderConnectionMemory` (`BUG-247`), the trading module's refresh jobs (`BUG-117`, `EPIC-028D`)
- **Environment:** GitHub Actions `gate (Rest)`, PR #673 head `3eb663a2` (master `adfababa` plus UI-only commits), two attempts; not reproduced serially, reproduced as extra reads under six busy loops locally.

## Reproduction
CI: `gate (Rest)` of PR #673 at `3eb663a2`: the pause journey failed in both attempts (`AssertionError: (None, '')`, the bot `RUNNING`), the 20-bot weight test in the second (`assert 70 <= 65`). Locally the weight test passes unloaded; with six busy-loop processes the minute shows 13 and 14 `positionRisk` reads (12 expected), the extra ones beside a `/api/v3/ping`.
Frequency: depends on the machine's speed; both tests had passed in the pull requests that introduced them (#664, #669), which first ran together on master after both merged.

## Symptom
```
test_an_order_met_by_the_pause_holds_the_bot_for_the_pause_and_not_as_a_switch_off
E   AssertionError: (None, '')   # state RUNNING, not AWAITING_RECOVERY
test_n_idle_bots_read_the_accounts_positions_once_a_beat_between_them[20]
E   AssertionError: 20 idle bots spent 70 weight a minute reading the account's positions   (assert 70 <= 65)
```
and the Log Scan step (`FAILED_STEPS: Tests,Log Scan`). The two WARNING records it fails on (`rate-limit pause`, `account summary stale`) were seen in a local reproduction under load, not in the CI job logs, which show only the assertions: which reader took the 429 is inferred from the code, and the fix covers both mechanisms below.

## Root cause
Not one defect but one mistake in four journeys: each asks the exchange something and takes the answer from "the next matching request", while several readers ask on their own clocks.
1. The pause journey (`test_a_futures_grid_met_by_…pause…`, at `adfababa`) queues a 429 for the next `/fapi/v1/ping` and then moves the price. The fill that follows makes two readers ask: the account summary a fill asks for on the worker pool (`account_summary_refresh_service.py` → `on_order_filled`, which reads the exchange fresh) and the bot's own counter order, whose connection check `order_connection_block` may not ask at all for `ORDER_CONNECTION_REUSE_SECONDS` = 5 s of real time after any passing check (`order_connection_memory.py`, `BUG-247`). When the summary's ping takes the 429 and the order passes its gate before that answer closes it, or the order is inside the 5 s window and sends without asking, the order is accepted and the bot stays `RUNNING`; the summary then warns `stale` after the journey's assertion.
2. The idle-bots weight test counts the minute's `positionRisk` requests: the bots' one read a beat, plus the trading module's `PositionRefreshService` poll (`module.py` schedules it every 5 s of real time), so how many of its reads fall in the minute depends on how long the machine takes to run the minute. The `+ 1` the test allowed was that poll on a fast machine, not a bot's order dropping the shared reading (no order is sent in the minute: the ladders are laid when `run_bots` returns, 120 posts).
3. The sisters `test_a_rate_limit_met_by_one_bot_halts_its_neighbours…` and `test_a_rate_limit_resumes_by_itself…` queue the same kind of answer after bots placed ladders, and had not failed yet only by timing.

## Fix
`OrderConnectionMemory.forget()` (the next order asks the exchange) and `tests/integration/modules/bots/quiet_exchange_readers.py`: the worlds of the four journeys boot with `NO_PERIODIC_REFRESH` (`trading.position_refresh_interval_seconds` = 3600), so the trading module's refresh jobs never come due and none has to be cancelled after boot (cancelling raced the Scheduler's own unlocked `jobs` swap and could not stop a run already spawned: review of #676, F1). `quiet_the_fill_summaries` unsubscribes the account summary's fill handler and fails when it finds none, so a rename cannot make it a silent no-op; `forget_the_kept_connection` drops the kept check. The three pause journeys call both before queuing their fault; the weight test now allows exactly one read a beat (60), not 65.

## Regression test
No test can be red deterministically for a race; the evidence is the failing CI runs (above), the extra reads reproduced under load (13 and 14 against 12), and the same journeys green three times in a row under six busy loops after the change. `test_a_forgotten_check_is_made_again_inside_the_beat` pins `forget()`; the weight test's bound is now exact, so any extra reader in the minute fails it by name.

## Verification
Local: the four files green, 23 passed; under six busy-loop processes the three pause journeys and the 20-bot weight test passed three runs in a row. CI: the pull request's `-Full` run.

## Suggested next steps
`SharedAccountStatus.read_now` after a fill and the order gate's own memo each read the account: a fill's summary and the order it triggers could share one flight is a latent saving, not a defect: the real exchange refuses every request during a pause, not only the next one, so the order sent in the window is itself met by the pause; the one-shot answer is a property of the fake.
