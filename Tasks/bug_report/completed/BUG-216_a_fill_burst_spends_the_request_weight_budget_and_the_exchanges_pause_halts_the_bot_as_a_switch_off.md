# BUG-216 — A burst of fills on a Futures Grid spent the minute's request weight, the exchange banned the IP, and the pause halted the bot as a switch-off with a position open

- **Reported:** 2026-10-15 (the owner's desktop log on Futures Testnet, Long Grid `djwx0w` ETHUSDT, 0.149 per level)
- **Severity:** 🔴 P1. Real-money path: a leveraged position stayed open with no exchange-side stop (`EPIC-039L` is not built), the IP was limited for ~90 s (`-1003`), every poll of the desktop failed meanwhile, and the bot ended `HALTED` by `switch_off`, which only a person ends.
- **Status:** ✅ Fixed (2026-10-15)
- **Board:** A burst of fills spent ~2,170 of 2,400 request weight in a minute and the exchange limited the IP; the bot then halted as a switch-off. Causes: the connection check that gates every order and cancel read the position mode (30 of its 37 weight) each time; reconcile and re-read asked for every symbol's open orders (80 weight) to keep one; the soft limit closed at 90 %; `-1003` was filed under `NETWORK`; the pause killed the user-data stream session. Fix: position mode kept a minute (and dropped on `-4061`), open-orders reads name the symbol, soft limit at 70 %, a `RATE_LIMITED` connection kind that takes the existing pause path, and the stream defers the re-read. The log noise and the re-read starvation are split out (below).
- **Context:** [SPEC-003](../../../Docs/SPEC/SPEC-003_check_the_exchange_connection.md), [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → `trading` (`adapters/binance/`, `application/orders/`) and `bots` (`kinds/grid/watch/`, `services/orders/`)
- **Environment:** Futures Testnet. Reproduced on the Futures HTTP fake exchange at `7c6a27b1` (`master-warrior`), with a request-weight meter added to the fake. Not run on a live exchange.

## Reproduction
1. Futures Long Grid running on the fake exchange (62,000..66,000, four grids).
2. The price crosses the ladder back and forth: 12 fills (`LONG.entry_price` then `LONG.completion_price`, six times), the account's report delivered ahead of the order's, then in order.
3. Sum the weight the fake charges (Binance's published Futures weights, `tests/sanity/fake_exchange/request_weight.py`).

Expected: a small share of 2,400 a minute. Actual before the fix: **948 for 12 fills** (the figure from the first scratch run was 1,038: the difference is the stream's re-reads), 720 of it `GET /fapi/v1/positionSide/dual` at 30 each, 24 reads for 12 fills. A reconcile or a re-read added 80 for two unfiltered open-orders reads.

## Symptom
```text
19:34:29 TradingAdapter WARNING Used weight 2168 of 2400: no request for 32 s [rate-limit-soft]
19:34:29 GetFuturesSymbolSettingQuery / GetOpenPositionsQuery failed: -1003 ... the exchange asked for a pause
19:34:29 TradingAdapter ERROR Futures Testnet connection check failed with an unclassified exception: RateLimitedApiException: APIError(code=-1003)
19:34:29 GridExecutor INFO L2 BUY 0.149 @ 2357.85 -> connection_not_ready
19:34:29 GridExecutor WARNING RUNNING -> HALTED on switch_off (switch_off: L2 BUY: connection_not_ready) [bot-transition]
19:34:31 FuturesUserDataStream connection lost: ExchangeRateLimitedError ...
19:34:32 .. 19:36:02: every 5 s, 4 ERROR lines during a pause the app itself enforces
```
Reproduced on the fake with the classification removed, the same words: `GridReason.SWITCH_OFF: L2 SELL: connection_not_ready; any position stays open on the exchange: this bot cannot close it until trading is back`.

## Root cause
Five mechanisms, found by attributing each request of a burst to its caller (a spy on `Client._request` in a scratch run):

1. **The order gate re-reads an account setting that never changes.** `FuturesAccountReader.check_connection` (`futures_account_reader.py:230-256`) is ping 1 + time 1 + account 5 + `positionSide/dual` 30 = 37 weight, and runs for every order (`execute_order/handler.py:322`), every cancel (`cancel_order/handler.py:82`), every fill's summary refresh (`account_summary_refresh_service._refresh_after_fill`, `read_now`) and every poll. The Multi-Assets mode has had a five-minute cache since the PR #304 review for exactly this reason (`ASSET_MODE_TTL_SECONDS`); the position mode, the same weight, never did.
2. **Reads of one symbol's orders asked for the whole account.** `BotOrderGateway.tagged_open_orders` (`bot_order_gateway.py:299`) and `owner_resting_orders.resting_orders` (`owner_resting_orders.py:33`) called `openOrders` and `openAlgoOrders` with no symbol (40 + 40) and filtered afterwards. Every register (each divergence re-read, each gap reconcile, twice per confirmation run) paid it: ~105 per register, ~190 per gap reconcile. The port (`IAccountActivity.open_orders()`) took no symbol although the query behind it did. Three more callers filtered the same way.
3. **The soft limit closed too late.** `SOFT_WEIGHT_RATIO = 0.9` (`exchange_call_policy.py:55`) closes the gate after an answer reported 2,160 of 2,400, with a Grid's chains already in flight; the owner's gate closed at 2,168 and the exchange limited the IP in the same second.
4. **A pause was classified as a network failure.** `classify_connection_failure` (`connection_failure.py:156`) had no kind for `-1003`/`-1015`/429/418, so the connection check logged an ERROR "unclassified exception" and answered `NETWORK`; `connection_block` made that `CONNECTION_NOT_READY`, which `fail_with` turns into `SWITCH_OFF` (`grid_order_failure.py`). The existing pause path (`GridRateLimitPause`: halt for the pause, cancel nothing, resume by itself) was never reached by an order that met the pause at the gate.
5. **The pause killed the user-data stream session.** An `ACCOUNT_UPDATE` re-reads each changed symbol's position through the gated client (`futures_user_data_stream.py:347`); during a pause that raised `ExchangeRateLimitedError` out of `_handle_message`, the supervisor logged "connection lost" and reconnected, and the reconnect (`CONNECTED`) made every bot run a full gap reconcile (`user_stream_watch._reconcile`) when the pause ended.

Also found, **not a weight cause and not in this change** (split out on review: BUG-217 and BUG-218): the Engine's dispatcher writes `<Query> failed: …` at ERROR for each call a pause refuses (four lines every 5 s), and the pause is not told once; and `GridRiskWatch.on_divergence` (`grid_risk_watch.py:123`) replaced the pending re-read for every new pair of figures, so a stream that never went quiet postponed confirming a divergence indefinitely (and logged ~20 `re-reading in 5 s` lines).

Checked and **not** a defect: the missed fill "applied twice" (19:34:12 and 19:34:14). `GridReconciler.compare_with_exchange` is a query; the first run returned a mismatch (`duplicate_level_order`) and applied nothing, and `GridStreamGap` confirms with a second run by design, so the `[missed-fill]` line is logged by each run. The count-once rule (`BOT-173`) is unchanged.

## Fix
- `position_mode_memory.py` (shared by the venue's account reader and its trading clients, wired in `VenueAssembly`): a One-way answer is trusted for 60 s; a Hedge answer and a failed read never are, and an order the exchange refuses with `-4061` (sent as One-way to an account that is not) clears it, so the next check reads the mode at once. The app never changes the mode itself. Check cost 37 → 7.
- `i_account_activity.py` and its three implementers (`AccountActivityService`, `FakeAccountActivity`, `SimulatedActivity`): `open_orders(symbol=None)`; the five callers that filtered by symbol name it (`bot_order_gateway`, `futures_facts_reader`, `venue_settings_gate_futures` ×2, `exchange_facts_reader`, `planner_numbers`), and `owner_resting_orders` passes the registration's symbol. 80 → 2.
- `exchange_call_policy.py`: `SOFT_WEIGHT_RATIO = 0.7`; nothing else in the policy.
- `ConnectionFailureKind.RATE_LIMITED` (+ `retry_after`, `banned` on `ExchangeConnectionStatus`, invalid without a pause): the codes `-1003`/`-1015` and the statuses 429/418 are named once in `binance_error_codes.py` and read by the call policy and the connection check alike; both readers fill the pause from `rate_limit_pause_of`. Every table that words, exit-codes or retries a kind has its entry, with a golden CLI text for the new one.
- `connection_gate.order_connection_block`: a check that met the pause raises `ExchangeRateLimitedError`, as a rejected submit does, so the bot takes the existing `RATE_LIMITED` path (halt for the pause, nothing cancelled or closed because nothing can be sent, resume by itself) instead of `SWITCH_OFF`. A wait inside the order was rejected: it would hold the bot's worker, which also judges the stops (the reason `ExchangeCallPolicy` gives for not sleeping in a call).
- `futures_user_data_stream.py` + `deferred_rereads.py`: a re-read that meets the pause is deferred to the next update (kept symbols first, each once); the session survives.

Not in this change (split out on review): the pause log work (BUG-217: one WARNING and one INFO, the dispatcher's per-call ERROR at DEBUG) and the re-read cap (BUG-218).

Not touched, by design: the Spot readers' behaviour (a pause there already took this path through `contract_error_of`), and the ORDER/ACCOUNT ordering gap itself, which is the second part below.

## Regression test
- `tests/integration/modules/bots/test_a_fill_burst_stays_inside_the_request_weight_budget_on_the_fake_exchange.py`: 12 fills ≤ 25 weight each in both delivery orders (red: 948), position-mode reads fewer than fills (red: 24), a reconcile names its symbol and costs ≤ 60 (red: four unscoped reads, 71). Measured after: 228 (19 a fill).
- `tests/integration/modules/bots/test_a_futures_grid_met_by_the_exchanges_pause_halts_for_the_pause_on_the_fake_exchange.py`: a 429 on the connection check halts the bot with `RATE_LIMITED` ("resumes by itself"), sends no cancel and no order, leaves the position and the ladder. Red with the classification removed: `SWITCH_OFF` with the owner's words; red on the old tree: the stream session died first.
- `tests/unit/modules/trading/adapters/binance/test_the_exchanges_pause_is_a_connection_failure_of_its_own.py` (classification, no ERROR for a pause, the TTL's four edges, the invalid state), `…/test_a_pause_during_the_position_re_read_keeps_the_stream_session.py`, `…/test_exchange_call_policy.py` (the 70 % boundary), the gate tests for execute and cancel, `…/test_the_position_mode_is_forgotten_when_an_order_is_refused_for_it.py`.
- The fake exchange now charges Binance's weights and returns `X-MBX-USED-WEIGHT-1M` (`tests/sanity/fake_exchange/request_weight.py`), so the app's own policy sees the numbers a real run would.

## Verification
Regression tests red on the original `src/` and green after (above). Commit tier `ci-local.ps1 -SkipTests`: PASS (ruff, format, mypy, reference check). `tests/unit/architecture`: green. The broader unit and integration runs: see the pull request. Positive proof the new mechanisms ran: the green burst's request log (24 position-mode reads → 1), the halt's `RATE_LIMITED` reason in the journey, and the deferred re-read published on the next update in the stream test.

Unverified: the owner's exact ~2,170 (the fake reproduces the shape, not the figure: the owner's UI polls and the testnet's report order are not modelled), and anything on the real Futures Testnet. A soak on the testnet is `EPIC-039L`'s.

## Second part
Done in [BUG-220](BUG-220_the_watchs_re_read_registers_the_budget_again_for_a_gap_the_stream_had_already_closed.md): the watch's re-read compares the book with the stream's last figure before it registers the budget again, and a re-read the pause deferred leaves no stale belief for what the payload's amount settles.
