# BUG-217 — A pause the exchange asked for was written to the log as four ERROR lines every five seconds, for ninety seconds

- **Reported:** 2026-10-15 (the owner's desktop log, Futures Testnet; split out of `BUG-216` on the independent review of PR #528)
- **Severity:** 🟡 P2. No money at risk; the log is the owner's only evidence during an incident and 72 identical ERROR lines buried it. Its first version also introduced a regression on the rate-limit gate (below), which is why it is a PR of its own.
- **Status:** ✅ Fixed (2026-10-15)
- **Board:** During a rate-limit pause every poll of the desktop failed and the Engine's dispatcher wrote `<Query> failed: …` at ERROR for each, 4 lines every 5 s for 90 s, besides an "unclassified exception" ERROR per connection check. Fix: the pause is told twice (a WARNING with the instant it ends, an INFO at the first request after it); a call the pause refused is written at DEBUG by a filter on the shared `App` logger, keyed on a tag the pause's own exception carries.
- **Context:** [SPEC-003](../../../Docs/SPEC/SPEC-003_check_the_exchange_connection.md), [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → `trading` (`adapters/binance/exchange_call_policy.py`, `connection_failure.py`) and `shell` (`dispatch_log_filter.py`)
- **Environment:** `master-warrior` at `7fabb918` (after #528); unit tier. Not run on a live exchange.

## Reproduction
1. The exchange answers a request with 429 / `-1003` (or the soft limit closes the gate).
2. The desktop's polls (open positions, account summary, mark price) keep arriving every few seconds.

Expected: the pause is announced once and ended once. Actual: one ERROR per refused poll.

## Symptom
```text
19:34:32 .. 19:36:02: every 5 s, 4 ERROR lines (GetOpenPositionsQuery, connection check "unclassified exception", GetAccountSummaryQuery "network", GetMarkPriceQuery) during a pause the app itself enforces
```
After `BUG-216` the connection check no longer logs the "unclassified exception" ERROR (the pause is a named kind); the dispatcher's `<Query> failed:` lines remained.

## Root cause
The Engine's `Dispatcher.dispatch` logs `<Handler> failed: {e}` at ERROR for every handler that raises, and a closed gate (`ExchangeCallPolicy._raise_if_closed`) makes every call of the venue raise at once. Nothing told the pause once, so each refused call was the only record of it. The Engine is not changed from this repository (`ONBOARDING.md` §2); the app already shapes the Engine's dispatcher lines with a filter on the `App` logger (`BOT-178`).

## Fix
- `exchange_call_policy.py`: a pause is told by a WARNING with the instant it ends (`[rate-limit-soft]`, `-pause`, `-ban`) when it begins, **again when it moves the announced end later or turns the running pause into a ban** (a burst's answers in flight escalate that way: a soft pause, a 429, a 418; found by the review of PR #531), never twice for the same end, and ended once by an INFO at the first request after it (`[rate-limit-end]`), a lazy check with no timer. The decision is made under one lock against the announced end (`_tell_pause`), which also closes the race of two threads meeting the same first 429. `note_used_weight` **always** calls `block(pause)` (to the minute's end, even while a shorter pause such as a 10 s `-1015` runs; `block` keeps the longer); only the announcement is skipped when a pause is already told. The first version of this work skipped `block` as well and let the gate reopen inside a minute already at 70 % (found by the review of PR #528); `test_the_soft_limit_extends_a_shorter_pause_to_the_minutes_end.py` pins it.
- `binance_error_codes.EXCHANGE_PAUSE_TAG` ends the text of every call the pause refused (`RateLimitedApiException`, the order gate's `ExchangeRateLimitedError`, `AccountSummaryUnavailableError` for `RATE_LIMITED`).
- `dispatch_log_filter.PausedCallFailureFilter`: an Engine ERROR of the form `<name> failed: …` carrying the tag is written at DEBUG (still in a `--dev` log, off a normal run's). Installed whatever the developer mode. `Retire when:` the Engine lets a handler's exception choose its log level.
- `connection_failure.classify_connection_failure`: a pause is logged at DEBUG, not at the INFO `connection check rejected … [connection-failure]` that a poll would repeat every few seconds.

## Regression test
- `tests/unit/shell/test_query_dispatch_is_quiet_outside_dev_mode.py`: a call the pause refused is not an ERROR outside developer mode (one DEBUG record); a failure whose text does not carry the tag stays an ERROR; both filters are installed once however often the graph is built. On `master-warrior` the filter does not exist and the ERROR is written.
- `tests/unit/modules/trading/adapters/binance/test_exchange_call_policy.py`: one WARNING at the start with the instant it ends and one INFO at the end, nothing between (red when the announcement repeats).
- `…/test_the_soft_limit_extends_a_shorter_pause_to_the_minutes_end.py`: a 10 s pause running, 40 s left of the minute: the gate closes to 41 s and the gate still closes to the minute's end (red when `block` is skipped inside a pause), and the extension is told once because it moves the announced end.
- `…/test_a_ban_or_a_longer_pause_during_a_pause_is_told.py`: a 418 during a soft pause is told with the ban's end; a longer 429 during a short pause moves the announced end; a shorter or equal pause is not told again; a ban is told even when it ends first; an ended pause is told again when the next begins (red when the extension rule or the ban rule is removed).
- `…/test_the_exchanges_pause_is_a_connection_failure_of_its_own.py`: a pause logs nothing at INFO; an unknown code is still an ERROR.

## Verification
Commit tier and the tests above (see the pull request). Positive proof the mechanisms ran: the two records of the pause (WARNING then INFO) in the policy test, and the DEBUG record of the refused dispatch in the shell test.
