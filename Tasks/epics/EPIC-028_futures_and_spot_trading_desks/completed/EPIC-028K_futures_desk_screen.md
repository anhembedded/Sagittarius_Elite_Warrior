# EPIC-028K — A Futures desk screen: chart, order entry, strategy, account summary and tabs

**Status:** ✅ Done (2026-10-02)
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — a new route and surface; the old screen stays until `EPIC-028M`
**Complexity:** M — composition only; every part exists by now
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028C](EPIC-028C_both_venues_running_concurrently.md), [EPIC-028I](EPIC-028I_futures_order_entry_variant.md), [EPIC-028J](EPIC-028J_account_tabs_and_summary_panels.md)

---

## 1. Context and problem
- `trading_view.py` (575-line baseline) and `trading_presenter.py` (978) are the old single screen.

## 2. Acceptance criteria
- [x] Route `trading.futures`, nav "Futures"; workspace chart, RAIL order entry + strategy card + summary, bottom tabs, EMERGENCY STOP and Enable for this venue only.
- [x] With Futures not enabled, the screen shows "Futures Testnet not enabled — Settings" and no controls that could send an order.
- [x] View, presenter and view model are each under 400 lines.
- [x] Each desk's chart streams under its own owner. `_STREAM_OWNER = "trading"` (`chart_coordinator.py`) is shared today, so opening one desk's chart would replace the other's subscription (the PR #300 epic review).
- [x] Signals reach only their venue's desk: `SignalGeneratedEvent` carries the venue and `SignalFeed` filters on it. The environment banner names both enabled venues, not the primary only.

## 3. Design
- **One desk package, two routes.** `ui/desk/desk_screen/` composes one desk for a venue; the two desks differ only in their `DeskProfile` (ADR D5). `futures_desk_screen.py` and `spot_desk_screen.py` each build their own `ScreenContribution(route=<constant>)`, one screen per file, so the sanity route scan reads each route statically. `desk_factories.py` holds what they share.
- **A composition presenter.** `DeskPresenter` builds the existing parts with the desk's own venue's ports and feeds: the order panel (`EPIC-028H`/`028I`), the account tabs and summary (`EPIC-028J`), the TP/SL follower (`EPIC-028I`, Futures only), the strategy card (`EPIC-022D`) and the chart. Three helpers keep it a composition: `DeskChart` (history, live candles, overlay, last price), `DeskSessionControls` (Enable/Disable and Emergency Stop for this venue) and `DeskStrategy` (the card over this venue's arming). `TradingViewModel` is reused as the desk's view model.
- **The seams the desks needed:**
  - **Chart stream owner.** `ChartCoordinator(stream_owner=...)`; each desk streams under `desk.<venue>`.
  - **Venue-stamped signals.** `SignalGeneratedEvent.venue`, stamped by the live `StrategyEngine` (`None` for a backtest), and `SignalFeed(bus, venue)` forwards its own venue's only.
  - **Per-venue strategy controls.** `IVenueStrategyControls.get(venue)` (trading's port) gives each desk its venue's arming and armed state. `VenueStrategyControlsAdapter` (strategy) implements it over `venue_strategy_arming` and `VenueStrategySessions`.
  - **Banner.** `banner_from_config.py` names every enabled venue and judges the chart by the primary venue's market.
- **The disabled venue.** The view builds an empty shell and reads no service, as every screen's view does. The presenter side checks `IVenueTradingPorts.enabled()`: an enabled venue gets `DeskPresenter`, which lays the desk out; a disabled one gets the notice (`DeskView.show_venue_disabled`) and a plain presenter.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/desk/desk_screen/` | new: view, presenter, chart, session controls, strategy, dependencies, chart ports, factories, Futures screen, preview |
| `src/modules/trading/module.py` | contributes the Futures desk |
| `src/modules/trading/ui/trading/coordinators/chart_coordinator.py` | `stream_owner` parameter, `TRADING_STREAM_OWNER` |
| `src/modules/trading/contracts/events/signal_generated_event.py`, `strategy/application/services/strategy_engine.py`, `strategy_factory.py`, `live_strategy_factory.py` | the venue on every live signal |
| `src/modules/trading/ui/signal_feed.py`, `screen_venue_feeds.py` | the feed filters by venue; `build_for(bus, venue, parent)` |
| `src/modules/trading/contracts/i_venue_strategy_controls.py`, `venue_strategy_controls.py`, `strategy/adapters/venue_strategy_controls_adapter.py`, `strategy/composition/port_bindings.py` | the per-venue strategy port and its binding |
| `src/support/ui_kit/environment_banner/banner_from_config.py`, `environment_banner_content.py`, `src/presentation/ui/app_bootstrapper.py` | the banner names every enabled venue |
| `src/modules/trading/ui/session_outcome_text.py`, `market_ticks.py` | texts and the tick-feed seam the old screens and the desks share |
| `src/modules/trading/ui/dashboard/dev_board_widgets/strategy_card_binding.py`, `strategy_card.py`, `dashboard/dev_board_panel.py` | the card takes an explicit binding |
| `src/modules/trading/ui/trading/trading_view_model.py` | typed accessors for the desks |
| `src/modules/trading/ui/desk/order_entry/order_entry_presenter.py`, `account_tabs/account_tabs_presenter.py` | `orderAccepted`, `list_accepted_order` |

## 5. Testing
- Unit:
  - `test_desk_screen.py` and `test_desk_journeys.py` — the whole desk over verified fakes, driven through its real controls. The journey types a Limit, clicks Buy, sees it in Open orders and cancels it.
  - `test_chart_coordinator.py` — two owners.
  - `test_screen_venue_feeds.py` — signals by venue.
  - `test_strategy_engine.py` and `test_live_strategy_factory_venue.py` — the venue on every signal.
  - `test_venue_strategy_controls_adapter.py` — the real binding.
  - `test_banner_from_config.py`.
- Sanity: the route scan and every navigable route constructing, both green.
- Mutation-checked, each turning a test red:
  - each of the presenter's wiring lines (go live on enable, re-read on account change, symbol, Emergency Stop, status, accepted order);
  - the desk's feeds built for the wrong venue;
  - the feed filter;
  - the venue dropped at the forming-bar publish;
  - the factory dropping the venue;
  - the adapter's arming or session built for the wrong venue.
- Integration (whole tier): green. The wire itself (both venues' orders against the fake exchange) is `EPIC-028P`'s and `EPIC-028O`'s integration tests.

## Implementation notes (written when done)
- **One shared package, not `futures_desk/` and `spot_desk/`.** The two desks differ only in data (ADR D5), so two packages would hold the same code twice. One screen file per route keeps the route scan's "one screen per file" convention.
- **A `PageShell`, not a `WorkbenchSurface`.** It has the same structure as the single screen it replaces; converting every remaining `PageShell` is `EPIC-025`'s, so no `src/shell/surfaces.py` entry was needed.
- **Found by the journey and fixed: a resting Limit placed from the desk never appeared in Open orders.** The venue's stream announces an order only when it fills or ends (an acknowledgement carries `x="NEW"`), so the order sat on the exchange, unseen and uncancellable from the desk, until something re-read the account. The order panel now announces each order the venue accepted (`orderAccepted`), and the desk lists it (`AccountTabsPresenter.list_accepted_order`). The Dev Board has the same gap; it leaves in `EPIC-028M`.
- **The PR #308 review found the first version of that fix wrong (blocking): it listed a filled Market order as open.** Both trading adapters answer an accepted order unchanged, `NEW`, and the fill (the user-data stream) can reach the UI thread before that answer (the REST worker); the late `NEW` re-listed the filled order. The first test passed only because its double answered `FILLED`, which no adapter does. Fixed at the mechanism, the shared order book: `LiveOrderBookCoordinator.on_order_filled` applies a status only when `order_status.is_valid_transition` allows it and never re-lists an order it saw end (filled, cancelled). It serves the Trading screen and the Dev Board too. Tests: the coordinator's late-`NEW`-after-fill, after-cancel and after-partial cases, and the desk journey with the adapters' `NEW` answer in both orders; each was red before the fix.
- **Other review fixes:** the strategy card's chart is a constructor argument of `DeskStrategy` (no callback set after construction); the Emergency Stop log line names the venue; a desk opened while its venue's trading is already on puts its chart live, as the toggle does, so the order panel values orders at the live price (opening with trading off still touches no network, `BUG-107`); `EPIC-028M` now moves `TradingViewModel`, `ChartCoordinator` and `StrategyOverlayCoordinator` out of `ui/trading/` before deleting it, and moves the Dev Board onto `DeskSessionControls`.
- **`StrategyCard` takes a `StrategyCardBinding`,** not a structural host Protocol: mypy reads a host's Qt `@Property` as the descriptor, so no host could be checked against one. `TradingViewModel` gained plain typed accessors (`strategy_card`, `symbol_list`, `current_symbol`, `set_symbol`), as `log_model` mirrors `logModel`. One documented `type: ignore[arg-type]` in `desk_strategy.py` follows `presenter_factory_trading.py`'s, for the coordinator's Protocol over the card's `@Property`s.
- **The chart stream is left running when a desk closes,** as the single screen and the Dev Board leave theirs. A closed desk's owner keeps its subscription until the desk opens again or the app stops.
- **The banner**: the bootstrapper passed `MarketType.SPOT` as the chart's market, so a Futures-only run read as a market mismatch (DANGER). It is now judged by the primary venue's market and names every enabled venue.
- `allowlist_module_boundaries.txt` went from 10 lines to 9: one seam, `trading/ui/market_ticks.py`, replaces the two screens' imports of `MarketTickFeed`.
