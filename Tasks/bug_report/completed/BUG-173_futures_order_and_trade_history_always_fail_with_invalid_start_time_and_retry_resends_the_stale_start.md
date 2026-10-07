# BUG-173 — Futures order and trade history always fail with -4181 "Invalid start time", and Retry can never succeed

- **Reported:** 2026-10-07 (the owner's Windows dev log, master `6aa3586`, 19:22 local, via the coordinator session)
- **Severity:** 🟡 P2 — the Futures desk's Orders and Trades history tabs never load; Retry makes it look recoverable.
- **Status:** ✅ Fixed (2026-10-07)
- **Board:** Futures history answered -4181 for every read: the desk asked for "now − 7 days", which is older than 7 days when the request arrives, and Retry re-sent that same start. Fixed: `fetch_span` clamps the start inside the endpoint's age limit (`max_age_ms`, 5 min margin) and Retry takes a fresh `since`.
- **Context:** SPEC account tabs history → `src/modules/trading/` → `adapters/binance/` (`history_window.py`, `futures_history_reader.py`) and `ui/desk/account_tabs/` (`history_tabs_loader.py`)
- **Environment:** Windows, Futures Testnet, master `6aa3586`. python-binance 1.0.37.

## Reproduction
Open the Futures Testnet desk; read the Orders or Trades history. Every read fails; Retry in the message bar fails again, about 15 presses in the owner's log.

## Symptom
```
GetOrderHistoryQuery(venue=futures_testnet, symbol=None, since=2026-09-30 12:22:43.737828+00:00, ...)
GetOrderHistoryQuery failed: Futures order history could not be read: APIError(code=-4181): Invalid start time.
GetTradeHistoryQuery failed: Futures trade history could not be read: APIError(code=-4181): Invalid start time.
```
Retry reused `since` 12:23:15.708677 for a minute.

## Root cause
Binance's documentation says the span between `startTime` and `endTime` is at most 7 days; it does not list -4181 and states no age limit (docs read 2026-10-07: All Orders and Account Trade List pages, error-code page). The reader already split spans into windows of at most 7 days, so the span rule was not what failed. What the owner's log supports, and the fake now encodes, is that a `startTime` older than 7 days at the exchange is refused with -4181. That rule is observed, not documented, and was not verified against a live call (egress to `*.binance.*` is blocked here).
- `history_tabs_loader.py` `open()` sets `since = now − DESK_HISTORY_SPAN` (7 days). The request reaches the exchange some milliseconds later, and a desk that stays open keeps the same `since` for paging and re-reads, so its start is older than 7 days by then. The reader passed it through unchanged (`history_window.py` `fetch_span`).
- Retry (`history_tabs_loader.py`, the notice's `retry`) re-sent `self._requests[kind]`, the failed request with its old `since`, so it could not succeed and every press made it older.
- Spot is not in this family: its windows are 24 hours and no age limit applies (`spot_history_reader.py`); every Spot window's start is the oldest and stays inside the lookback `require_within_lookback` already checks.

## Fix
- `history_window.py`: `HistoryWindowRules.max_age_ms`; `fetch_span` moves a start older than `until − max_age` forward. One mechanism for every caller of the endpoint.
- `futures_history_reader.py`: all four Futures history endpoints (`allOrders`, `allAlgoOrders`, `userTrades`, `income`) use `max_age_ms` of 7 days minus 5 minutes. The five-minute margin costs the oldest five minutes of the tab.
- `history_tabs_loader.py`: Retry builds its request with `since = clock() − DESK_HISTORY_SPAN`. Paging and re-reads after a fill keep the fixed `since` the cache relies on (`EPIC-028Q`); the adapter clamp covers their age.
- `tests/sanity/fake_exchange/futures_routes.py`: the fake refuses a `startTime` older than 7 days on `allOrders` and `userTrades` with -4181.

## Regression test
- `tests/integration/infrastructure/binance/test_history_readers_against_fake_server.py::test_a_futures_week_read_is_not_refused_for_a_start_older_than_seven_days`: red on master with `APIError(code=-4181): Invalid start time.` (the owner's message), green after.
- `tests/unit/modules/trading/ui/desk/test_account_tabs_presenter.py::test_retrying_a_failed_history_takes_its_span_from_now_not_from_the_failed_read`: red with the stale `since` (2026-09-24 vs 2026-10-01), green after.
- `tests/unit/modules/trading/adapters/binance/test_history_window.py::test_a_start_older_than_the_endpoints_age_limit_is_moved_forward`, and `test_history_reader_active_symbols.py` now expects the start five minutes inside the limit.

## Verification
Touched suites `tests/unit/modules/trading` and `tests/integration/infrastructure/binance` pass (2150 tests); commit tier and architecture guards: see the PR. The live exchange rule is unverified.
