# EPIC-028E — Each desk loads its open orders, order history and trade history from the exchange

**Status:** 🟡 Implemented — awaiting review
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — history endpoints are weight-heavy; paging and symbol filter must be right first time
**Complexity:** M — one reader port × two venues, four queries, one policy (see Implementation notes)
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028B](../completed/EPIC-028B_venue_addressed_commands.md), ADR O5

---

## 1. Context and problem
- Nothing reads `allOrders`, `myTrades` (Spot) or `userTrades` (Futures); `EPIC-027` ADR O6 deferred
  `myTrades` (Spot average entry price).
- Open orders reach the UI only through Enable/Emergency Stop results and stream events — a desk
  opened after an order was placed elsewhere shows nothing.

## 2. Acceptance criteria
- [x] `GetOpenOrdersQuery(venue, symbol | None)` returns the live open orders on screen open.
- [x] `GetOrderHistoryQuery` and `GetTradeHistoryQuery(venue, symbol | None, since, page)` return the last 7 days paged 50 rows (ADR O5), newest first; trade rows carry price, qty, fee and fee asset.
- [x] Spot trade history gives an average entry price per held asset (closes EPIC-027 ADR O6).
- [x] A request that exceeds the exchange's lookback window is split, never silently truncated.

## 3. Design
*As built — superseding the draft's two ports (`IOrderHistoryReader`, `ITradeHistoryReader`); see ADR D6's 2026-09-30 amendment and the implementation notes below.* One `IAccountHistoryReader` (ABC: `order_history`, `trade_history`, `active_symbols`) with a Futures adapter (`futures_get_all_orders`, `futures_account_trades`) and a Spot adapter (`get_all_orders`, `get_my_trades`); `OrderRecord` and `TradeRecord` value types; the average entry price as a pure policy over trade records.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_account_history_reader.py`, `order_record.py`, `trade_record.py`, `history_page.py`, `average_entry_price.py`, `account_history_unavailable_error.py` | new |
| `src/modules/trading/adapters/binance/` `history_window.py`, `history_reads.py`, `listed_symbols.py`, `futures_history_reader.py`, `futures_history_payload_mapper.py`, `spot/spot_history_reader.py`, `spot/spot_history_payload_mapper.py` | new |
| `src/modules/trading/application/queries/get_open_orders`, `get_order_history`, `get_trade_history`, `get_average_entry_price/`; `application/history_paging.py`; `domain/policies/average_entry_price.py` | new |
| `src/modules/trading/contracts/venue_context.py`, `composition/venue_assembly.py`, `composition/query_bindings.py` | `history_reader` field, built and bound |
| `tests/sanity/fake_exchange/history_log.py` and the Futures and Spot routes and states | serve the four endpoints |

## 5. Testing
Unit per adapter; fake-exchange integration; policy test for average entry price (mutation-verified).
- Window splitting: `adapters/binance/test_history_window.py` — windows no longer than the limit, inclusive edges with no overlap or gap, a full window split until every row is read, a full millisecond raises, an empty span asks nothing.
- Mapping: `test_history_payload_mappers.py` — Futures fill figures and `realizedPnl`, no average when nothing filled, Spot average = quote spent ÷ quantity, Spot side from `isBuyer`.
- Readers: `test_history_readers.py` — active symbols (Futures: open positions + open orders; Spot: listed pairs of held assets + open orders), the requested span ends at the clock, every SDK failure becomes `AccountHistoryUnavailableError` with the cause chained, no credentials → no request.
- Contract: `contracts/test_account_history_reader_contract.py` — the verified fake keeps one symbol, starts at `since`, oldest first, active symbols sorted and covering its rows.
- Policy: `domain/policies/test_average_entry_price.py` — base and quote fees, a third-asset fee left out, sells keep the average, replay order, unexplained coins, oversell (also when a later buy re-balances it), sold out, dust tolerance.
- Queries: `test_get_open_orders.py`, `test_get_history_pages.py` (newest first, fifty a page, totals, past-the-end, every symbol = active symbols, `since`, validation), `test_get_average_entry_price.py`.
- Wiring: `test_module_venue_contexts_binding.py` asserts each venue's history reader type; the sanity tier resolves every bound query.
- Integration: `test_history_readers_against_fake_server.py` — a week of Spot orders (filled and canceled) and a fill with its base-asset fee read back through real HTTP; the fake refuses a span over 24 h with `-1127`, so the read proves the split; a canceled Futures order reads back with no fills.
- Mutation: 35 mutations over the window splitter, mappers, readers, policy, paging, handlers, query validation, assembly, the fake and the bindings; every one killed after closing three gaps the first pass found (an oversell healed by a later buy, a named symbol among other active ones, a dust holding that fills explain).

## Implementation notes (written when done)
- **One port, not two (ADR D6 amended).** `IAccountHistoryReader` carries `order_history`, `trade_history` and `active_symbols`: both histories share the signed session, the symbol requirement and the lookback rule, and every consumer so far wants both from the same venue. `VenueContext` gains one field, `history_reader`, built by `VenueAssembly` (`FuturesHistoryReader`, `SpotHistoryReader`; the venue-adapter guard now names both).
- **Types.** `OrderRecord` wraps the existing `Order` with executed quantity, average price (`None` when nothing filled) and creation time rather than growing `Order`, which is also what the app sends. `TradeRecord` keeps the fee in the asset it was charged in; `realized_pnl` is Futures only. `HistoryPage[T]` carries `scanned_symbols` so a screen can say which pairs it shows.
- **Never truncated.** `history_window.fetch_span` cuts a span into windows the endpoint accepts (Futures 7 days, Spot 24 hours) and splits a window that comes back holding the row limit (1 000) until each part is under it; a single millisecond holding a full page raises `HistoryWindowTooDenseError` (an `AccountHistoryUnavailableError`). Every SDK or network failure is translated to that one error with the cause chained, so `application/` never imports `python-binance`.
- **"Every symbol" is the active symbols.** Binance's history endpoints need a symbol. With `symbol=None` the queries read each of `active_symbols()` — Futures: open positions and open orders; Spot: the listed USDT pair of each held asset, and open orders. A pair fully closed with nothing open is not among them; `scanned_symbols` says so on every page rather than implying completeness.
- **Paging.** `newest_first_page` sorts by a stable key (time, then client order id or trade id) and slices fifty rows; the total is kept. Each page request re-reads the span — accepted: a caching decorator behind the port is the listed extension if it proves slow.
- **Average entry price (closes `EPIC-027` ADR O6).** The pure policy `domain/policies/average_entry_price.py` replays fills oldest first by the average-cost method (base-asset fee reduces what was received, quote-asset fee adds to what was paid, a sell keeps the average). It answers only when the replayed quantity matches the holding within its dust threshold; an oversell, coins bought before `since`, deposits or transfers answer `None`. A fee paid in BNB is left out of the cost (it cannot be priced from the fills) and the docstring says so. `GetAverageEntryPriceQuery` reads the holding from the venue's connection check and the fills from the history reader; a Futures venue answers `None` (its positions carry the exchange's entry price).
- **Review follow-ups (PR #297, NEEDS_REVISION: one blocking finding, three should-fix, one optional, one note).**
  - *Catalog downloads and a leaking SDK error (blocking).* `SpotHistoryReader.active_symbols` asked `get_or_fetch` for each held asset's pair, and every unlisted pair — `USDTUSDT` always among them — downloaded the whole `exchangeInfo` catalog; a failed download escaped as `BinanceAPIException`. `ListedSymbols` now refreshes the shared metadata cache at most once for all unknown candidates and remembers the pairs found unlisted, the quote asset is excluded before any lookup, and the lookup runs inside the reader's one failure translation. Tests with a catalog double that downloads on a miss like `SpotMetadataProvider`: one download across three calls, none when the only non-quote holding is cached, the failure translated with its cause. Restoring the old loop turns them red.
  - *Unbounded `since` (should-fix).* A read further back than `MAX_HISTORY_LOOKBACK` (30 days) is refused with `ValueError` before any request: 30 days is 600 weight per Spot symbol and endpoint, a year would be about 7 300, over Binance's 6 000 a minute. Recorded on the port; the average entry price gets a month of fills.
  - *028J shows `scanned_symbols` (should-fix).* `EPIC-028J` gained the acceptance criterion.
  - *§3/§4 named the draft ports (should-fix).* Rewritten as built.
  - *Duplicated reader machinery (optional, taken).* `history_reads.py` holds the lookback check, timestamps, the credential check and the one failure translation both readers and both mappers use.
  - *`sold > quantity` vs `> quantity + tolerance` (note).* Within one satoshi; left as is.
- **Fake exchange.** `tests/sanity/fake_exchange/history_log.py` remembers every accepted order and fill with a real timestamp; both fakes serve `allOrders` and their trade endpoint, honour `startTime`/`endTime`, and the Spot one refuses a span over 24 h with Binance's `-1127`.
- No screen shows these yet: the desk tabs are `EPIC-028J`, which must name the scanned pairs. No SPEC changes, since no user flow changed.
