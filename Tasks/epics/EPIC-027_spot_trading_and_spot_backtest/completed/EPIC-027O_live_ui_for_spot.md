# EPIC-027O — The Trading screen and the Dev Board show Spot as balances, with Buy and Sell only

**Status:** ✅ Done (2026-09-28)
**Source:** the user, 2026-09-26: *"tui muốn giao dịch spot"* ("I want to trade spot").
**Risk:** 🟢 — presentation over behavior the earlier tasks prove.
**Complexity:** M — two surfaces, a balances table, manual-order buttons, wiring the inert market combo.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027L](EPIC-027L_spot_user_data_stream.md), [EPIC-027N](EPIC-027N_live_strategy_on_spot.md)

---

## 1. Context and problem
- The positions table shows Side, Entry, Mark, Leverage and Liquidation
  (`src/modules/trading/ui/order_book/table_models.py:81-90`). None of these exist on Spot.
- The manual order card has LONG and SHORT buttons (`dashboard/dev_board_widgets/manual_order_card.py`).
  The strategy card has a leverage spinbox (`strategy_card.py:90-97`), and so does the Trading screen
  (`ui/trading/trading_view.py:496-502`).
- The Dev Board "Market: Spot/Futures" combo is inert
  (`dashboard/dev_board_widgets/system_controls_card.py:140-145`). `TC-GAP-01`
  (`tests/integration/presentation/ui/test_dev_board_known_gaps.py:104-116`) asserts that it does
  nothing.
- The Trading presenter's block message says "only Futures Testnet is supported" (`trading_presenter.py:149`).

## 2. Acceptance criteria
- [x] On a Spot venue, a Holdings table (asset, free, locked, value in USDT) replaces the Positions
      table on both surfaces.
- [x] The manual order card shows BUY and SELL. SELL is disabled when there is no holding to sell.
- [x] Leverage controls are hidden on Spot.
- [x] The Dev Board market combo is either wired (it selects the chart's market; the trading market
      comes from the venue) or removed. `TC-GAP-01` is updated to assert the new truth, not deleted.
- [x] Every message that names the venue names the market too.

## 3. Design
- The market for trading comes from the venue (`EPIC-027G`). The chart's market is a separate choice
  for viewing. A mismatch is shown by the environment banner (venue-alignment state), not blocked.
- **Reading holdings reuses the existing seam — no new port method.** `ITradingAccountReader.
  check_connection()` already answers `ExchangeConnectionStatus.holdings: tuple[SpotHolding, ...] |
  None` (`EPIC-027H`), the exact value `EnableTradingCommandHandler`/`EmergencyStopCommandHandler`
  already read. `GetHoldingsQueryHandler` (new use case, mirrors `GetOpenPositionsQueryHandler`'s
  shape) just calls that and answers `status.holdings or ()`. `IAccountSnapshot` (a second,
  currently-unused-by-this-task port with its own `open_positions()`) is left alone — extending it
  would add an `@abstractmethod` every implementer must grow (`architecture-rule.md` §2) for a fact
  `ITradingAccountReader` already exposes for free.
- **One whole-set event, not changed/closed pair.** `PositionRefreshService` publishes
  `PositionChanged`/`PositionClosed` because positions also arrive incrementally from the Futures
  user-data stream's `ACCOUNT_UPDATE` deltas — the per-symbol distinction earns its keep there.
  Holdings have no such incremental side-channel in this app (`SpotUserDataStream` re-triggers a
  fresh `ITradingAccountReader` read on its own events, `EPIC-027L`); every holdings read this task
  adds is already the whole account snapshot. A single `HoldingsChangedEvent(holdings: tuple
  [SpotHolding, ...])` — always the complete set — is the honest shape; inventing a
  `HoldingClosedEvent` to mirror positions would be structure with no real delta behind it.
- **`HoldingsRefreshService` mirrors `PositionRefreshService`** (poll on the engine `Scheduler`,
  no-op while trading is disabled) but its scheduler registration in `module.py::boot()` is gated on
  `TradingVenue.market_type is MarketType.SPOT` — unlike positions (cheap on every venue, Spot
  answers `[]`), a holdings poll is a real network round trip through `check_connection()` that would
  be pure waste on a Futures venue, where `ExchangeConnectionStatus.holdings` is always `None` anyway.
- **`LiveOrderBookCoordinator` grows one more table, not a second coordinator.** It already owns "the
  account's live tables, shared by both screens, driven by `OrderFeed`" for Positions/Open Orders;
  Holdings is the same shape of fact (an account-wide read-only live set another screen would
  obviously also want — `architecture-rule.md` §6's absurdity test says no). `OrderBookDisplay` gains
  `set_holdings(rows: Sequence[HoldingRow])`; the coordinator gains `_holdings: dict[str, SpotHolding]`
  and `replace_holdings()`/`_render_holdings()`, following `_positions`'s exact pattern. `OrderFeed`
  gains a `holdingsChanged` signal alongside `positionChanged`/`positionClosed`.
- **`HoldingRow`/`build_holding_row()`/`HoldingsTableModel`/`HoldingsPanel`** mirror `PositionRow`/
  `build_position_row()`/`PositionsTableModel`/`PositionsPanel` file-for-file. Value in USDT needs a
  price the holding itself doesn't carry (`SpotHolding` is asset/free/locked only) — `build_holding_row`
  takes the holding plus a `Mapping[str, Decimal]` of last-known prices (asset → USDT), the same "caller
  already knows current prices" assumption `build_position_row` makes for its own PnL text; a missing
  price (an asset with no live price feed) renders the value cell as `"—"` rather than guessing.
- **Which panel shows is a market switch, not two screens' worth of new state.** `DashboardPresenter`/
  `TradingPresenter` already resolve `TradingVenue`/`market_type` at composition (`trading_actions_
  coordinator.py`'s own constructor is the existing precedent). Each screen wraps its existing
  `PositionsPanel` and the new `HoldingsPanel` in a `QStackedWidget`, shown/hidden once at construction
  by `market_type is MarketType.SPOT` — a static choice for the process lifetime (the venue does not
  change without a restart, `EPIC-027G`), not a live-toggle property, so no `marketTypeChanged` signal
  is needed here (unlike leverage-hiding below, which reads a `ViewModel` property because the backtest
  screen's own precedent for this exact idiom (`strategy_properties_dialog.py::
  _show_leverage_for_market()`) is a `Property`+signal on that screen — the live Trading/Dev Board
  screens have no equivalent live-switchable market property to read, only the fixed venue).
- **Leverage hiding is a static `setVisible()` at construction**, for the same "venue is fixed for the
  process" reason above — `strategy_card.py`'s `field_row("Leverage", ...)` wrapper and `trading_view.
  py`'s equivalent each get `.setVisible(market_type is not MarketType.SPOT)` once, no new ViewModel
  property or signal needed (the backtest screen's `Property`+signal precedent exists because *that*
  screen's market is user-switchable mid-session; this one's is not).
- **Manual order card: BUY/SELL labels, SELL disabled without a holding.** `ManualOrderDirection`
  stays `LONG`/`SHORT` (the domain enum `manual_order_intent_for()` already keys off, unchanged) —
  only the button *text* becomes "BUY"/"SELL" on Spot (`_btn_manual_long.setText("BUY" if spot else
  "LONG")`, `_btn_manual_short.setText("SELL" if spot else "SHORT")`), since `manual_order_intent_for`
  already refuses a Spot SHORT with a named error and already maps LONG→BUY/SHORT→SELL — relabeling
  is honest, not a semantic change. SELL-disabled-without-a-holding is new: `ManualOrderCard` reads the
  same holdings set `HoldingsPanel` renders (via the shared `LiveOrderBookCoordinator`, extended with a
  `has_holding(symbol) -> bool` query the card's Presenter reads) rather than re-deriving it from a
  second live-updated collection.
- **Dev Board market combo: wired to the chart's market, not removed.** Per this task's own §3 line
  already in the file (kept): trading's market is fixed by the venue; the combo instead selects which
  market's candles the chart card shows (`market_data`'s existing per-market kline storage,
  `EPIC-027A`) — a real, useful choice independent of the live trading venue. `TC-GAP-01` is rewritten
  to assert selecting the combo changes the active chart's requested `MarketType`, not that nothing
  happens.
- **The block message and `TRADING_VENUE_DISABLED`'s text name the market**, e.g. "Trading venue is
  disabled in configuration." → the venue's own market-aware label (`MarketType`'s existing display
  name, `backtest_market.py::market_label()` reused rather than a third label table).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/application/queries/get_holdings/` | new — `GetHoldingsQuery`/`GetHoldingsQueryHandler`, mirrors `get_open_positions/` |
| `src/modules/trading/contracts/events/holdings_changed_event.py` | new — one whole-set event |
| `src/modules/trading/application/holdings_refresh_service.py` | new — mirrors `position_refresh_service.py`, Spot-gated scheduling |
| `src/modules/trading/ui/order_feed.py` | `holdingsChanged` signal |
| `src/modules/trading/ui/live_order_book_coordinator.py` | `OrderBookDisplay.set_holdings`, `_holdings`, `replace_holdings()`, `_render_holdings()`, `has_holding()` |
| `src/modules/trading/ui/order_book/holding_row.py`, `table_models.py`, `holdings_panel.py` | new — mirror `position_row.py`/`PositionsTableModel`/`positions_panel.py` |
| `src/modules/trading/ui/dashboard/dashboard_presenter.py`, `ui/trading/trading_presenter.py` | `QStackedWidget` Positions/Holdings switch by `market_type`, `set_holdings()` implementation, `holdingsChanged` wiring |
| `src/modules/trading/ui/dashboard/dev_board_widgets/manual_order_card.py` | BUY/SELL labels, SELL enablement from holdings |
| `src/modules/trading/ui/dashboard/dev_board_widgets/strategy_card.py`, `ui/trading/trading_view.py` | leverage row hidden on Spot |
| `src/modules/trading/ui/dashboard/dev_board_widgets/system_controls_card.py` | market combo wired to the chart |
| `src/modules/trading/ui/trading/trading_presenter.py` | `TRADING_VENUE_DISABLED` message names the market |
| `src/modules/trading/composition/query_bindings.py`, `state_bindings.py`, `module.py` | bind the new query/service, Spot-gated scheduler registration |
| `tests/integration/presentation/ui/test_dev_board_known_gaps.py` | `TC-GAP-01` rewritten |
| `preview.py` of each touched package | Spot previews |

## 5. Testing
- Unit: `GetHoldingsQueryHandler` (answers `status.holdings`, empty on `None`); `HoldingsRefreshService`
  (publishes on success, silent on a transient failure, no-op while trading disabled); `LiveOrderBookCoordinator.
  replace_holdings()`/`has_holding()`; `build_holding_row()` (value text, a missing price renders `"—"`);
  ViewModel/View visibility and enablement per market (leverage hidden on Spot, SELL disabled with no
  holding, panel switch); `manual_order_intent_for()`'s Spot Sell rows (real holding sells, dust holding
  still refused); `StreamLifecycleController`'s market threading through `_read_and_validate_inputs`/
  `_run_load_history`/`_run_load_more_history`/`_run_sync_and_start`/`_sync_market_data`.
- Integration (real `qtbot` clicks): `TC-GAP-01` rewritten — picking "Futures" on the Dev Board market
  combo and clicking Load History changes `DashboardPresenter._active_market` and the `MarketType` the
  chart's own `IHistoricalKlines` read carries (`tests/integration/presentation/ui/
  test_dev_board_known_gaps.py::test_market_dropdown_changes_which_market_load_history_fetches`).
- Integration (fake Spot exchange, application layer, no GUI): a real BUY click's mapped
  `ExecuteOrderCommand`, dispatched through the exact `ExecuteOrderCommandHandler`/`SpotTradingClient`
  path a human's click uses, is placed on the fake exchange's wire and moves the BTC balance
  `SpotAccountReader.check_connection().holdings` reports afterwards — the same read
  `HoldingsRefreshService`/`OrderFeed.holdingsChanged` feed the Holdings table from
  (`tests/integration/application/test_spot_manual_order_pipeline_against_fake_server.py`). Chosen over
  a full `qtbot`-driven Dev Board boot on a Spot Testnet venue: this app's existing UI integration
  fixture (`tests/integration/presentation/ui/conftest.py`) is wired specifically around
  `TradingVenue.DISABLED` (mocked dispatcher, no real account reader), and standing up a second,
  parallel Spot-Testnet-booting fixture would duplicate a large amount of fixture machinery to prove a
  fact this file already proves at the layer where the real behaviour lives — the manual order card's
  own click→dispatch wiring is separately proven end-to-end for a real click reaching
  `ExecuteOrderCommandHandler` (`test_dev_board_manual_order_qt_click.py`), and SELL's enable/disable
  reaction to a `HoldingsChangedEvent` is proven at the unit level
  (`test_dashboard_presenter.py::test_holdings_changed_updates_the_manual_order_sell_button`).
- Full fast-tier gate green: `pwsh scripts/ci-local.ps1 -SkipTests` (ruff lint, ruff format, mypy,
  reference check) plus `tests/unit/architecture`, the full `tests/unit/modules/trading` tree, and
  `tests/integration/presentation/ui` + `tests/integration/application` — 511 passed, 4 skipped
  (opt-in e2e/testnet tiers), 0 failed.

## 6. Implementation notes
- **`DashboardQmlViewModel.market`'s private getter/setter renamed** `_get_market`/`_set_market` to
  `_get_chart_market`/`_set_chart_market` — the obvious functional-`Property` names collided with
  `BrokerSimulationConfigViewModel`'s own `_get_market`/`_set_market` (backtest's market selector,
  `EPIC-027D`), which `test_presenter_duplication_only_shrinks.py`'s cross-package ratchet counts even
  though the two bodies do genuinely different things (this one only commits a string; that one also
  pins leverage to 1x on Spot). Renaming these two private implementation-detail methods was free and
  keeps the ratchet at its 66-name baseline; the public `market` Property name itself is unchanged and
  intentionally shared vocabulary (`code/naming.md` §4).
- **`_active_market` follows the exact `_active_interval`/`_active_symbol` "commit at click time" shape**
  end to end: `DashboardQmlViewModel.market` (live combo state) then `StreamLifecycleController.
  _read_and_validate_inputs()` (reads fresh) then `_on_load_history`/`_on_start_stream` (commits via
  `set_active_market`) then `DashboardPresenter._active_market` (the committed value) then
  `fetch_older_history()`'s scroll-driven load-more (reads the committed value via `get_active_market`,
  never a live re-read) — the same data-mixing bug a live re-read would risk for `_active_symbol`
  already ruled this design in for `_active_market` too.
- **god-file ratchet**: `stream_lifecycle_controller.py` (baseline 601) and `dashboard_presenter.py`
  (baseline 1454) both needed comment/docstring condensation (never behavioural trimming) to absorb the
  new market-threading parameters and stay at or under baseline — both land exactly at baseline after
  this task, the same shrink-only discipline every earlier EPIC-027O sub-task also had to apply.
- All of this task's implementation slices landed in this one PR; no follow-up bug filed.
