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
`IOrderHistoryReader`, `ITradeHistoryReader` (ABC) with Futures (`futures_get_all_orders`, `futures_account_trades`) and Spot (`get_all_orders`, `get_my_trades`) adapters; `TradeRecord` value type; average-entry-price as a pure policy over trade records.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_order_history_reader.py`, `i_trade_history_reader.py`, `trade_record.py` | new |
| `src/modules/trading/adapters/binance/…` | four adapters |
| `src/modules/trading/application/queries/get_open_orders|get_order_history|get_trade_history/` | new queries |
| `tests/.../fakes/binance_fake_server.py` | serve the four endpoints |

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
- **Fake exchange.** `tests/sanity/fake_exchange/history_log.py` remembers every accepted order and fill with a real timestamp; both fakes serve `allOrders` and their trade endpoint, honour `startTime`/`endTime`, and the Spot one refuses a span over 24 h with Binance's `-1127`.
- No screen shows these yet: the desk tabs are `EPIC-028J`. No SPEC changes, since no user flow changed.
