# EPIC-035D — Retry, backoff and Retry-After for exchange calls

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M3 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 2 of [EPIC-035](../README.md).
**Risk:** 🟡 — a retry on a submit can duplicate an order; only reads and cancels may retry
**Complexity:** L — a retry policy and venue gate below every adapter, a reused session, a new bot outcome with a temporary halt that resumes itself
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit M3: a single transient failure (timeout, reset, DNS) puts the bot in ERROR, which needs a manual Stop/Start; `-1003` / `-1015` / HTTP 429 / 418 are classified but also lead to ERROR; `Retry-After` and the used-weight headers are ignored; each order costs extra requests.

**Verified on `be67b47` (every claim re-checked before the first test).**
- ✅ *A transient failure ends in ERROR.* `BotOrderGateway.cancel` and `_submit` turn any exception into `FAULT` (`bot_order_gateway.py`, lines moved; the audit cites 150-162), and `fail_with` sends `FAULT` to ERROR. Reproduced on the wire: a dropped request on a Spot cancel raised `ConnectionError` out of `SpotTradingClient.cancel_order` (red-before below).
- ✅ *`-1003` / `-1015` are classified and lead to ERROR.* `binance_error_translator.py:33-37` maps both to `RATE_LIMIT`; the reason became an `OrderRejectedByExchangeError`, which the gateway made a `FAULT`. **The audit's range `:327-330` does not exist** (the file is 78 lines); the mapping holds on the lines above. **HTTP 429 / 418 were not classified at all**, which is worse than the audit said: a 429 gateway page (`code=0`, non-JSON) was read by `is_unreadable_answer` as *an unreadable answer*, so a rate-limited **submit** became `OrderOutcomeUnknownError` ("it may be live") although the exchange had refused it before reading it.
- ✅ *`Retry-After` and the used-weight headers are ignored.* No header is read anywhere in `src/` before this task.
- ✅ *The gate read per order.* `ExecuteOrderCommandHandler._first_blocked_safety_gate` calls `account_reader.check_connection()` for every order (`handler.py:296-322` holds). **The cost is larger than the audit's "about three extra requests": measured on the fake exchange, a steady-state Spot LIMIT order cost 10 requests, nine of them extras** (3 sessions opened per order: the account reader's, its own connection check's second ping and clock, and the trading client's; plus the account read and two prices).

## 2. Acceptance criteria
- [x] Reads and cancels retry with exponential backoff and a cap; an order **submit** never retries on an unknown outcome. — `ExchangeCallPolicy.run_read` retries a transient failure after 0.5, 1 and 2 s (`READ_RETRY_DELAYS_SECONDS`, 3.5 s at most); `run_once` sends a submit once. The method name decides (`call_mode_of`): `get_*`, `futures_get_*`, the named reads and `*cancel*` retry; a name nobody classified is sent once. `test_a_timeout_on_a_cancel_retries_and_succeeds`, `test_a_read_that_was_reset_retries_and_succeeds`, `test_a_submit_with_an_unknown_outcome_is_looked_up_never_resent` (one POST, one lookup), `test_a_submit_that_timed_out_is_sent_once_and_the_failure_surfaces`.
- [x] `Retry-After` and the rate-limit headers are honoured; a 429 / `-1003` pauses the whole gateway for the stated time, and a 418 backs off for its ban window. — one `RateLimitGate` per venue session factory, shared by the account reader, the trading client, the history readers and the metadata reads; a 429 closes it for `Retry-After` (else 60 s; `-1015` else 10 s), a 418 for `Retry-After`, else "banned until <ms>", else 120 s; while it is closed **no request is sent by any call, reads and submits alike**. The used-weight header is read after each answer: at 90 % of the venue's per-minute weight (6000 Spot, 2400 Futures) the gate closes to the end of the minute. `test_retry_after_is_honoured`, `test_a_rate_limit_closes_the_venue_for_a_submit_too`, `test_a_418_closes_the_venue_for_the_ban_window_and_says_it_is_a_ban`, `test_used_weight_near_the_limit_pauses_to_the_end_of_the_minute`.
- [x] Rate-limit exhaustion HALTs the bot temporarily with a named reason and resumes by itself when the window ends; it is not ERROR. — `OrderOutcomeKind.RATE_LIMITED` (the gateway) → `GridReason.RATE_LIMITED` HALT; `GridRateLimitPause` schedules the resume on `IBotRetryScheduler` for the pause plus 2 s and runs the same propose-and-confirm a user's Resume runs. A stop that meets a limit stays STOPPING and retries after the pause. `test_grid_executor_rate_limit.py` (18 tests).
- [x] One client per venue session is reused; the per-order extra requests drop to the documented minimum, measured and recorded. — `VenueSessions` keeps one signed session per venue and key (up to 4 keys; re-opened after 10 min, never kept if the open failed; the open runs outside the lock). **Measured on the fake exchange, a steady-state Spot order: 10 requests before, 6 after** (ping, clock, account, two prices, the order); the first order of a venue also pays the session's open and `exchangeInfo`. `test_a_steady_state_order_costs_the_documented_minimum_of_requests`.

## 3. Design
Retry belongs in one place below the gateway, as a policy (retry with backoff, a vetted pattern), not at each call site. Python-binance's `Client` is the one object every adapter of a venue talks to, so `ResilientSession` wraps it **once**: the bots gateway and the manual-order path share it, and so do the account and history readers.

Decisions (P5/P6/P7, recorded here, not asked):
1. **The retry is in the call, with an injected sleep; the bot's wait is on `IBotRetryScheduler`.** A transient failure retries for at most 3.5 s inside the worker's call (no timer, no second clock); a rate limit is never slept in a call (a call holding a bot's worker for a minute is worse than a halt) — it raises, and the bot waits on the scheduler `035C` built.
2. **The pause is a `BinanceAPIException` subclass (`RateLimitedApiException`) below the clients, and the contract `ExchangeRateLimitedError` (an `OrderRejectedByExchangeError`, reason `RATE_LIMIT`) at them.** About fifteen adapters catch `BinanceAPIException` to word their own result; a domain error raised from the session would have escaped them. The trading clients convert (`raise_rejection`, `raise_for_failed_send`, `raise_for_failed_read`), so a bot, the desk and the CLI get one named error and a reader keeps its own words.
3. **Auto-resume is propose-and-confirm, not "put back what was".** A rate-limit halt does not park (the cancels would be refused in the pause); the resume registers the budget, cancels every tagged order, re-derives the inventory and lays a fresh ladder at the current price (`035J`'s re-pricing applies). **This lets a bot resume without the owner's confirmation, which D13 reserved for every other halt; the criterion asks for it for this cause only**, and it is bounded: a pause over one hour (a ban) is not held by a timer, and 5 consecutive automatic resumes that meet the limit again leave the bot HALTED with "resume by hand". A stop, a user's resume or any later halt cancels the pending one (a round counter).
4. **The gate is per `SpotSessionFactory` / `FuturesSessionFactory`, i.e. per venue** (`VenueAssembly` builds one each), shared by everything that factory serves.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/adapters/binance/exchange_call_failure.py` (new) | Classify a failure: transient, rate-limited (+ pause), banned (+ window), other |
| `.../rate_limit_gate.py`, `.../exchange_call_policy.py`, `.../rate_limited_api_exception.py` (new) | The venue's gate; the retry policy and used-weight rule; the pause as a `BinanceAPIException` |
| `.../resilient_session.py`, `.../venue_sessions.py` (new) | The policy on every method of the client; one reused signed session per venue and key |
| `.../spot/spot_session_factory.py`, `.../futures_session_factory.py` | Hand out the venue's `VenueSessions` |
| `.../order_send_failure.py`, `.../spot/spot_trading_client.py`, `.../futures_trading_client.py` | `raise_rejection` and the send/read words turn a pause into `ExchangeRateLimitedError` |
| `src/modules/trading/contracts/exchange_rate_limited_error.py` (new) | The contract error, with `retry_after` and `banned` |
| `src/modules/bots/application/services/bot_order_gateway.py` | `RATE_LIMITED` outcome with its pause; `take_rate_limit` |
| `.../grid_rate_limit_pause.py` (new), `domain/grid/rate_limit_pause.py` (new), `grid_runtime.py` | The temporary halt, the scheduled resume, its three named limits, `GridReason.RATE_LIMITED` |
| `.../grid_task_guard.py`, `grid_executor.py`, `grid_order_failure.py` | The guard halts for a pause raised by a read and schedules the resume; no parking for this reason; `fail_with` maps the outcome |
| `.../grid_stop_sequence.py`, `grid_stopper.py`, `grid_stop_retry.py`, `grid_resume_sequence.py` | A stop waits out a pause (cancel, slice or read) and retries no earlier than its end; a resume's refused cancel halts for the pause |
| `tests/sanity/fake_exchange/` | `FaultPlan` (queue a 429 with headers, a 418, a dropped connection) and Spot `GET /order` |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | Two journeys and their test rows |

## 5. Testing
Red before (the code at `be67b47`): the nine new unit and integration files failed at collection (the policy, the gate and the session did not exist); the request-count test failed on behaviour (`ping` ×3, `time` ×3, 10 requests against the 6 expected); a Spot cancel through a dropped connection raised `ConnectionError` instead of retrying. Green after.
- Unit: `test_exchange_call_failure.py`, `test_rate_limit_gate.py`, `test_exchange_call_policy.py`, `test_resilient_session.py`, `test_venue_sessions.py`, `test_session_factories_reuse.py`, `test_rate_limited_error_of.py`; bots: `test_grid_executor_rate_limit.py`, `test_bot_order_gateway_rate_limit.py`.
- Fake exchange over HTTP: `test_exchange_resilience_against_fake_server.py`, `test_order_request_cost_against_fake_server.py`; the fake's own `test_fault_plan_http.py`.
- Planned names, as delivered: `test_a_timeout_on_a_cancel_retries_and_succeeds`, `test_a_submit_with_an_unknown_outcome_is_looked_up_never_resent`, `test_retry_after_is_honoured`, and for the halt `test_a_rate_limited_order_halts_the_bot_with_a_named_reason_not_error` + `test_the_bot_resumes_by_itself_when_the_pause_ends`.

## Implementation notes
- **Not built, on purpose: a lighter readiness probe.** Five of the six requests of a steady order are the safety gate's `check_connection()` (ping, clock, account, two prices). A readiness-only probe (one signed read) would cut an order to two requests, but it changes `IVenueAccountReader` and its fakes and contract suite, and the gate's read is what refuses an order when the exchange cannot be reached. Follow-up, not in this epic's list.
- **Not verified against a live exchange** (egress to Binance is blocked here): the header names (`Retry-After`, `X-MBX-USED-WEIGHT-1M`), the "banned until <ms>" message, and the assumption that the weight window is the wall-clock minute. The fake exchange answers what the library documents.
- **Shared client across threads.** One python-binance `Client` now serves every thread of a venue (it relies on `requests.Session` being safe for concurrent plain requests); its `response` attribute (the last answer) is racy, and only the used-weight header is read from it.
- **Another factory.** `adapter_bindings.py` still binds one default `FuturesSessionFactory()` to `ITradingSessionFactory` (own session and gate). Nothing resolves that binding (grep: only `VenueAssembly`'s per-venue factories reach an adapter), so it carries no traffic; removing the dead binding is left to a cleanup.
- **Readers keep their words.** A pause reaches the account reader as a connection failure (`NETWORK`) and the history readers as `AccountHistoryUnavailableError`, as a 429 did before; a dedicated "rate limited" connection kind is a UI change this task leaves.
- **Residual.** `GridExecutor` gained no member; `BotOrderGateway` has one more outcome kind and two methods.

**Review round 2.** A rate-limit pause met while a bot reads a price (a tick too old to use, so the book is read through `IFreshPriceReader`) lost its type and ended a stop in ERROR or turned a confirmation into `PROPOSAL_PRICE_MOVED`: `MarketPriceRateLimitedError` now carries the pause from the book readers, `FreshPriceUnavailableError.retry_after` through the reader, and `GridReferencePrice` raises `ExchangeRateLimitedError`, handled like every other pause (3 tests, red without the conversion).

**Review round 1 (PR #439).** Fixed: a pause met while a trading client *obtains its session* (absent, expired, key changed) escaped as `RateLimitedApiException` and a bot took it for a fault (`test_*_trading_client_tells_a_pause_met_opening_its_session_as_a_pause`, red without the fix); the session open no longer holds the lock; sessions are kept per key (a second account no longer reopens the first's); the retried cancels are an exact list, not the substring `cancel`; commit-lint (an empty commit body).

## Resume
Done. Delivered in the EPIC-035D/035J pull request.
