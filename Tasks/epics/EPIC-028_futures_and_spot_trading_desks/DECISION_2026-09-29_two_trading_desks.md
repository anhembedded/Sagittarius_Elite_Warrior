# ADR — Two trading desks, Futures and Spot, running side by side in one process

**Epic:** [EPIC-028](README.md)
**Date:** 2026-09-29
**Status:** Accepted (2026-09-29)
**Decided by:** 🟢 User decision, 2026-09-29 — *"đồng ý các khuyến nghị, bắt đầu làm 028A đi"* ("I agree with the recommendations, start on 028A"), replying to the report generated from this ADR. This accepts D1–D8 as written and answers O1–O5 with each question's recommended option (§4). The request, 2026-09-29: *"giờ màn hình trading đang có vấn đề, cần có 2
cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì
riêng, 2 màn hình đó phải có vào lệnh thủ công, và chọn strategy … khi kết nối tới binance thì
phải get các data về thông tin tài khoản, vị thế"* ("the trading screen has a problem: there must
be two, not one — one Futures, one Spot. Share what can be shared, separate what must be. Both
screens need manual order entry and strategy selection … once connected to Binance they must fetch
account information, positions, etc."), with four Binance screenshots as the reference layout.
**Supersedes / superseded by:** Revisits the "exactly one `TradingVenue` per process" assumption
recorded by `EPIC-027` (`adapter_bindings.py:146`, `i_symbol_order_metadata_cache.py`,
`i_trading_client_factory.py`, `SPEC-012` §2) and HLD 04 §4.5 / HLD 11 §11.3 ("manual order is
Dev Board only, ADR D15").

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🔵 Proposed | an option awaiting a decision; not accepted |
| ❓ Open | blocks the named phase until answered |

## 1. Context (✅ measured 2026-09-29, `master-warrior` `faf4a337`)

1. **One Trading screen, one venue per process.** `trading_screen.py` contributes a single route
   `"trading"`; `TradingView` branches once at construction on
   `container.resolve(TradingVenue).market_type` (Holdings panel on Spot, Positions on Futures).
   `TradingVenue` is read once from `exchange.trading_venue` at boot
   (`binance_endpoints.py:95`); Settings says changing it needs a restart.
2. **Every live port is bound once, branched on that one venue** — `adapter_bindings.py` (312
   lines) binds `IMarketMetadataProvider`, `IExchangeCredentialsProvider`, `ITradingClientFactory`,
   `ITradingAccountReader`, `IUserDataStream` to either the Spot or the Futures implementation.
   `TradingSessionState`, `EquityCurveRecorder`, `TradingLimitPolicy`, `ITradingSession` and the
   single armed-strategy slot are per-process singletons. Four docstrings state the assumption
   outright ("exactly one venue is ever active per process").
3. **The Trading screen has no manual order entry.** Only the Dev Board has one
   (`dev_board_widgets/manual_order_card.py`: Market/Limit, quantity, price, two buttons). No
   leverage, margin mode, TP/SL, reduce-only, TIF, % slider or total. `SPEC-012` names "the Trading
   screen's manual order card", which does not exist.
4. **Account data the GUI never shows.** `ExchangeConnectionStatus.usdt_balance` (Futures:
   `walletBalance`, not available balance) appears only in the CLI and Settings. Nothing reads
   order history (`allOrders`), trade history (`myTrades`/`userTrades`), commission rates,
   available balance, max buy, or changes leverage / margin mode. Open orders reach the UI only as
   side effects of Enable/Emergency Stop results plus stream events — there is no query.
5. **Reusable pieces already exist:** `ui/order_book/` (`PositionsPanel`, `HoldingsPanel`,
   `OpenOrdersPanel` with `cancelRequested`, `table_models.py`), `LiveOrderBookCoordinator`,
   `StrategyCardViewModel` + `StrategyArmingCoordinator` (shared by both screens today),
   `ChartCard`, `EquityFeed`, `OrderSubmissionService` → `ExecuteOrderCommand`,
   `manual_order_intent_for()`, `OrderQuantityRoundingPolicy`, `SymbolOrderMetadata`.

## 2. Decisions (🟢 all accepted 2026-09-29)

- **D1 — Two screens, two routes.** `trading.futures` ("Futures") and `trading.spot` ("Spot")
  replace the single `"trading"` route. Each screen is permanently bound to one venue; a screen
  whose venue is disabled shows an honest "venue not enabled — Settings" state instead of
  disappearing.
- **D2 — Both venues live at once, through a per-venue `VenueContext`.** One immutable bundle per
  enabled venue (credentials, client factory, account reader, user data stream, metadata provider,
  session state, equity recorder, limit policy, arming slot), built by a `VenueContextFactory` in
  the composition root and looked up through an `IVenueContexts` registry keyed by `TradingVenue`.
  Rejected alternatives: (a) two processes — doubles the chart/stream/DB stack and still needs
  every screen to know which process owns it; (b) keyed/named DI bindings on the existing
  container — spreads the venue key across dozens of `resolve()` call sites instead of one lookup.
- **D3 — Every command and query that touches a venue names it.** `ExecuteOrderCommand`,
  cancel/cancel-all, Enable/Disable trading, Emergency Stop, Arm/Disarm, and the new account
  queries carry `venue: TradingVenue`; handlers resolve their `VenueContext` from it. Safety gates
  (`supports_order_submission`, limits, baseline) stay per venue. Emergency Stop on one desk never
  touches the other.
- **D4 — Config becomes a set of venues.** `exchange.trading_venues: ["futures_testnet",
  "spot_testnet"]`, migrated once from the scalar `exchange.trading_venue` (a scalar value becomes a
  one-element list). Settings shows one toggle per venue. Still read at boot.
- **D5 — Shared desk kit, venue variants by composition.** One `desk/` package with shared
  panels; venue differences live in small variant classes behind a `DeskProfile` (market type,
  labels, which panels exist), never `if is_spot` branches spread through widgets:

  | Part | Shared core | Futures variant | Spot variant |
  | :--- | :--- | :--- | :--- |
  | Order entry | order-type tabs (Limit / Market / Stop-limit), price + BBO, quantity, % slider, total, TP/SL toggle, estimated fee | margin-mode chip (Cross/Isolated), leverage chip, reduce-only, TIF, **Buy/Long · Sell/Short**, liquidation price / cost / max | two columns **Buy · Sell**, available per side, max buy / max sell |
  | Account summary | reachable, equity, available | wallet, margin balance, unrealized PnL, position mode | quote free/locked, holdings value |
  | Bottom tabs | Open orders (cancel one / cancel all), Order history, Trade history | Positions (close at market), Assets | Assets (holdings) |
  | Strategy | the existing strategy card (one armed strategy per desk) | leverage field visible | leverage hidden, long-only (EPIC-027N) |
  | Chart / equity / log | existing `ChartCard`, `EquityFeed`, log panel | — | — |

- **D6 — New read ports for account data**, each with a Futures and a Spot adapter:
  `IAccountSummaryReader` (available / wallet / margin balance, unrealized PnL; Spot free/locked +
  equity), `IOrderHistoryReader` (`allOrders`), `ITradeHistoryReader` (`myTrades` / `userTrades`,
  also closing `EPIC-027` ADR O6's Spot average entry price), `ICommissionRateReader`, and an
  `IOpenOrdersQuery` so open orders load on screen open instead of waiting for an event.
  - **Amended 2026-09-30 (`EPIC-028D`, PR #296): no `IAccountSummaryReader`.** Both
    `ITradingAccountReader` implementations already fetch the whole account payload for
    `check_connection()`; a separate reader would sign and send the same request again and add a
    seventh member to `VenueContext`. The summary (`AccountSummary`, with `FuturesAccountSummary`
    and `SpotAccountSummary`) travels on `ExchangeConnectionStatus.summary`, filled by each
    reader, and `GetAccountSummaryQuery` reads it off the addressed venue — the seam
    `GetHoldingsQuery` already uses. The other readers in D6 stand: each needs its own endpoint.
- **D7 — Futures account controls are commands, not UI state.** `ChangeLeverageCommand` and
  `ChangeMarginTypeCommand` call the exchange (`change_leverage`, `change_margin_type`) and refuse
  while a position is open on that symbol, the same rule Binance enforces.
- **D8 — Money-moving estimates are domain policies, tested without Qt:** max quantity from
  available balance and leverage, order cost, estimated fee from commission rates, and a Futures
  liquidation-price estimate labelled "estimate" (never presented as the exchange's number).

## 3. Consequences

- The four "one venue per process" docstrings become false and are rewritten in the same pull
  request that removes the assumption; `ISymbolOrderMetadataCache` is keyed by
  `(TradingVenue, symbol)` first.
- `trading_presenter.py` (978-line baseline) and `trading_view.py` (575) are retired, not grown: the
  two new screens are thin compositions of the desk kit, each under 400 lines.
- `SPEC-005`/`SPEC-012` change surfaces; a new SPEC covers "see my account on a desk".
- HLD 04 §4.5 and HLD 11 §11.3 change: manual order entry moves onto both desks. The Dev Board keeps
  its F9 dialog, rebuilt on the shared order-entry panel.

## 4. Questions (🟢 answered 2026-09-29 with the recommendation)

| # | Question | Answer (the recommendation) | Blocked |
| :- | :--- | :--- | :--- |
| O1 | Both venues in one process (D2) or keep one venue per process and just give each its own screen? | **One process, both venues** — two screens where one is always dead is not what was asked | Phase 1 |
| O2 | Spot TP/SL: Binance Spot does it with OCO orders, which no code here builds. | **Futures TP/SL now** (`STOP_MARKET`/`TAKE_PROFIT_MARKET` reduce-only, already on `OrderType`); Spot TP/SL toggle visible but disabled, delivered with `EPIC-026K`'s protective orders | Phase 3 |
| O3 | Stop-limit order type (third tab in the screenshots)? | **Include** on both desks (`STOP_LOSS_LIMIT` on Spot, `STOP` on Futures) | Phase 3 |
| O4 | Retire the single `"trading"` route, or keep it as a redirect? | **Retire** — nav shows Futures and Spot; an old saved layout falls back to Futures | Phase 4 |
| O5 | History depth for order/trade history tabs? | **Last 7 days, paged 50 rows**, symbol-filtered like Binance's "hide other pairs" | Phase 2 |
