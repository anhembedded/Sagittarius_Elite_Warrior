# EPIC-028C — Both venues stream, refresh and trade at the same time, and Settings turns each on separately

**Status:** 🟡 Implemented (2026-09-29) — awaiting independent review
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — two user data streams and two refresh schedulers share one event loop and one event bus
**Complexity:** M — boot wiring, events gain a venue, Settings UI
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028A](../completed/EPIC-028A_venue_context_and_registry.md), [EPIC-028B](../completed/EPIC-028B_venue_addressed_commands.md)

---

## 1. Context and problem
- `module.py` `boot()` starts one `IUserDataStream` and schedules `HoldingsRefreshService` only on
  Spot, `PositionRefreshService` only on Futures.
- `OrderFilledEvent`, `PositionChangedEvent`, `HoldingsChangedEvent`, `EquitySampledEvent` carry no
  venue, so a screen cannot tell whose fill it is.
- Settings has one "Order Venue" combo.

## 2. Acceptance criteria
- [x] With both venues enabled, both user data streams start, and each refresh service runs only for its own venue.
- [x] Every trading event carries `venue`; the `LiveOrderBookCoordinator` / feeds filter on it (test: a Spot fill never lands in a Futures table).
- [x] Settings shows one toggle per venue (Futures Testnet, Spot Testnet) and still says a restart applies it.
- [x] Saving those toggles writes `exchange.trading_venues` (the list) and drops the legacy scalar `exchange.trading_venue`, so a config migrates on its first save (moved here from `EPIC-028A`: the Settings page is the only writer of this key). *Met with one deviation: the scalar is kept in step instead of dropped (Implementation notes §2).*
- [x] The Settings venue lock while `exchange.trading_venues` is configured (`_VENUE_LIST_MESSAGE` in `trading_settings_presenter.py`, added in `EPIC-028A` review F2) is removed: the per-venue toggles own the list, so Save is no longer refused.
- [x] Disabling one venue in Settings leaves the other fully working after restart.
- [x] A live tick reaches only the strategy session of its own market: a Spot kline never drives the strategy armed on Futures (moved here from `EPIC-028B`: `BinanceWebsocketService`'s stream carries no market type yet, so `MarketTickEventHandler` feeds every armed session).
- [x] The armed strategy configuration is saved and restored per venue, so arming on one desk never replaces the other's restored configuration (moved here from `EPIC-028B`: `LiveStrategyConfigStore` keeps the last armed one).

## 3. Design
Events gain a `venue` field with no default (the fields are frozen dataclasses: every construction site updates in the same commit, `pitfalls/source.md` #1). The existing `EnvFirstCredentialsProvider` per venue is reused.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/module.py` | start/stop per enabled venue |
| `src/modules/trading/contracts/events/*.py` | `venue` field |
| `src/modules/trading/ui/live_order_book_coordinator.py`, feeds | filter by venue |
| `src/presentation/.../settings` | per-venue toggles |

## 5. Testing
- Unit tests per slice, each new one mutation-verified (the mechanism broken, the test red, restored): per-venue refresh services built and scheduled by the real `TradingModule.boot()`; feeds refusing another venue's events; both user data streams starting; Settings toggles, save, lock and the real-container "after restart" check; per-market websocket connections and socket choice; `MarketTickFeed`, `MarketTickEventHandler`, the watchlist and the Trading screen on the real bus; the per-venue config store and `StrategyModule.boot()` re-arming each enabled venue.
- Fast tier: `ci-local.ps1 -SkipTests` PASS per commit; unit 6036, integration 185, sanity 32 passed on the S3 tree. The full gate is GitHub Actions' check run on the PR head (`ci-rule.md` §1).
- Not run: a live dual-venue Testnet run (`EPIC-028N` owns that tier).

## Implementation notes (written when done)
Four slices, one commit each.

1. **Refresh, events, feeds.** `venue_refresh_services.py` builds one refresh per enabled venue from `_REFRESH_BY_MARKET` (Futures: positions; Spot: holdings), and `TradingModule.boot()` schedules each. Eight trading events gained `venue` (kw-only, no default). `SignalGeneratedEvent` did not, because backtests publish it too and it never reaches a venue screen. `VenueEventEmitter` stamps the venue on everything a user data stream publishes. `OrderFeed`/`EquityFeed` take the venue they show, built by `screen_venue_feeds.build()` so the presenters did not grow.
2. **Settings.** One checkbox per venue that can place orders. Save writes `exchange.trading_venues` in `TradingVenue` order, and the Save lock holds while any venue's session is live. `_VENUE_LIST_MESSAGE` is gone. **Deviation from AC 4:** the scalar `exchange.trading_venue` is kept equal to the list's primary venue (or `disabled`) rather than dropped, because `IConfig` has no delete and `app_config.json` always ships a default scalar. The list takes precedence whenever present, so the scalar is inert.
3. **Market-aware live stream.** `MarketTickEvent.market_type` is required; `IMarketStream.start`, `ILiveStreamService.subscribe` and `StartLiveStreamCommand` take the market. `BinanceWebsocketService` runs one connection per market, keyed `(market, symbol, interval)`, and `kline_sockets.py` picks the socket (Futures: `futures_multiplex_socket`, whose events are standard `kline`). `MarketTickEventHandler` feeds only the sessions whose venue trades the tick's market. `MarketTickFeed` passes only its screen's market, asked per tick. The Trading screen charts its venue's market (Spot while trading is off), the Dev Board follows its combo, and the watchlist and CLI stay on Spot.
4. **Per-venue saved strategy.** `LiveStrategyConfigStore.load/save` take the venue and use `trading.<venue>.live_*` keys. `adopt_legacy(enabled)` moves a single-venue app's unscoped keys to the one enabled venue, then empties the legacy strategy key, so a venue enabled later never inherits another market's strategy. With trading off it waits; with two venues enabled it cannot tell which venue armed them, so it leaves them and logs a WARNING (PR #295 review, finding 3). `StrategyModule.boot()` re-arms the primary venue through its own `StrategyArmingService` (`venue_strategy_arming`).

Accepted costs:
- `LiveTradingCoordinator` and `LiveStrategyFactory` take a keyword-only `venue` on top of their existing parameters. That puts them over the four-argument guideline; they are composition-built collaborators, and a parameter object would only rename the list.
- The PR #294 review's should-fix items rode this PR (commit `e6fdf907`).
- **Only the primary venue is re-armed at boot** (PR #295 review, finding 2). Every screen shows and disarms the primary venue alone until the desks exist, so re-arming the other venue would leave an armed strategy that no screen mentions or can stop. The other venue's saved strategy stays saved. `EPIC-028L` carries the criterion that widens the restore to every venue with a desk.
- PR #295 review findings 1 and 4: `test_trading_presenter_toggle.py` was split below 400 lines. The websocket-service test file and a line-count guard for `tests/` joined `BOT-146`, and `EPIC-028M` now names `SPEC-004`.
