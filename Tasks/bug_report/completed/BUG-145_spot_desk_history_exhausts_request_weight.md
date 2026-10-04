# BUG-145 — Opening the Spot desk exhausts Binance's request weight, so a bot cannot start

- **Reported:** 2026-10-04 (the user, in chat, with a screenshot of Start refused and the dev-mode log of the session)
- **Severity:** 🔴 P1. On a Spot account with many held assets, opening the Spot desk spends Binance's request weight for minutes. Every other read is then refused with `-1003`. A Grid bot's Start needs the commission rate, so Start is refused too.
- **Status:** ✅ Fixed (2026-10-04)
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (start a Grid bot) and the Spot desk's Account tabs → `src/modules/trading/` → `application/queries/get_order_history`, `get_trade_history`; `adapters/binance/cached_history_reader.py`
- **Environment:** Windows, `master-warrior` `136508a6`, Spot Testnet only enabled. The testnet account holds about five hundred assets.

## Reproduction

1. Turn on Spot Testnet trading and open the Spot desk. "Hide other pairs" is off by default.
2. Open the Bots tab and press Start on a Draft Grid bot.

Expected: the bot starts.

Actual: Start is refused because the commission rate could not be read: `APIError(code=-1003): Too much request weight used`.

## Symptom

From the dev log:

- When the desk opened, it dispatched `GetOrderHistoryQuery` and `GetTradeHistoryQuery` with `symbol=None`.
- The handler logged about 500 symbols, `0GUSDT, 1000CATUSDT, …`.
- `App.HistoryCache` logged `[history-cache] orders … read` and `trades … read` for each symbol.
- This happened twice: once for `since 15:22:46` and again for `since 15:22:48`, after `EnableTradingCommand`.
- The `-1003` errors started within about ten seconds.

## Root cause

- **The every-pair read had no limit.** The Spot desk's history tabs ask for every pair (`symbol=None`) unless "Hide other pairs" is ticked.
  - `GetOrderHistoryQueryHandler` and `GetTradeHistoryQueryHandler` read one history per pair that `IAccountHistoryReader.active_symbols` names.
  - On Spot, those pairs are the USDT pair of every held asset (`SpotHistoryReader.active_symbols`). The Spot Testnet account holds about 500.
  - `allOrders` and `myTrades` accept at most 24 hours per request and cost weight 20 each. Seven days is therefore 8 requests per pair and per endpoint.
  - One desk opening asked for about 500 × 8 × 20 × 2 ≈ 160 000 weight, against Binance's 6 000 a minute.
- **Reads already running were repeated, not joined.** The desk reads its histories again when trading is turned on (`DeskPresenter._reread_account`), two seconds after it opened.
  - The first every-pair read was still running, so the second read missed `CachedAccountHistoryReader` for every pair and asked again.
  - `active_symbols` was read twice in the same way, once per tab.

## Fix

- `IAccountHistoryReader.every_symbol_scan_limit()` (new): how many of `active_symbols` one every-pair read may read, or `None` for all of them. The limit is the venue's, because the cost per pair is the venue's (the PR #344 review, finding 1).
  - `SpotHistoryReader`: `SPOT_EVERY_SYMBOL_SCAN_LIMIT` = 5. Five Spot pairs over seven days cost 800 weight per tab, 1 600 for both.
  - `FuturesHistoryReader`: `None`. Seven days is one window per pair, and only pairs actually held, traded or waiting are active.
  - `CachedAccountHistoryReader` passes through the limit of the reader it wraps. The verified fake takes one as a parameter. The port contract requires `None` or a positive count.
- `src/modules/trading/application/history_scope.py`: `history_scope` gives the pairs a page reads.
  - With a symbol, that symbol is the only pair.
  - Without one, it is at most the reader's limit of its active pairs, in the reader's order.
  - When pairs are left out, the page gets a notice saying how many were read out of how many, and that "Hide other pairs" reads the desk's pair.
  - Both history handlers use it.
- `CachedAccountHistoryReader`: `_ReadsInFlight` lets one read per key (a symbol's orders, a symbol's trades, or the active symbols for a `since`) go to the exchange at a time.
  - A read that arrives while that key is being read waits for it, then is judged against the entry it stored.
  - If that read failed, or its entry does not serve the waiting `since`, the waiting read goes to the exchange itself.
- `Docs/SPEC/SPEC-013_see_my_account_on_a_desk.md` step 4 states the Spot limit and its notice.

**Follow-up, not in this fix (the PR #344 review, finding 3).** Both readers name active pairs sorted, so on a 500-asset testnet account the five Spot pairs read are `0GUSDT, 1000CATUSDT, …`. The user's own pairs, such as one with an open order or the one a bot trades, are almost never among them. The notice says so truthfully, and "Hide other pairs" reads the desk's pair.

Reading the open-order pairs first changes the port's "Sorted" promise, which `AccountHistoryReaderContract` locks. It also needs the reader to tell open-order pairs from held ones. That is a contract change of its own, so it is left for a separate task rather than widening this fix.

## Regression test

- `tests/unit/modules/trading/application/queries/test_get_history_pages.py`:
  - `test_every_symbol_reads_at_most_the_scan_limit_and_says_so` (orders and trades) gives a 500-pair account. It was red before the fix: all 500 pairs were read.
  - `test_every_symbol_at_the_scan_limit_reads_them_all_without_a_notice` covers the boundary. It goes red when `<=` is mutated to `<`.
  - `test_a_venue_without_a_scan_limit_reads_every_active_pair` checks that a Futures account is not capped.
- `tests/unit/modules/trading/adapters/binance/test_history_reader_scan_limits.py`: Spot's limit and its weight arithmetic, Futures' `None`, and the cache passing the limit through.
- `tests/unit/modules/trading/adapters/binance/test_cached_history_reader_in_flight.py`: `test_a_read_arriving_while_the_same_read_is_in_flight_joins_it` (orders, trades, active symbols).
  - It holds the first read open and starts a second.
  - It was red before the fix: two reads reached the exchange.
  - After the fix, the `joins the read in flight` log line is the positive proof that the second read waited.

## Verification

- `tests/unit/modules/trading`: 1 900 passed on the fix.
- Commit tier: see the PR.
- **Not yet run:** a live Spot Testnet session that opens the desk and then starts a bot. The user's next run is the live check.
