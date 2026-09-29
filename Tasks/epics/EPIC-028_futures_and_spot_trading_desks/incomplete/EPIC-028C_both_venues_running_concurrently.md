# EPIC-028C — Both venues stream, refresh and trade at the same time, and Settings turns each on separately

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟡 — two user data streams and two refresh schedulers share one event loop and one event bus
**Complexity:** M — boot wiring, events gain a venue, Settings UI
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028A](EPIC-028A_venue_context_and_registry.md), [EPIC-028B](EPIC-028B_venue_addressed_commands.md)

---

## 1. Context and problem
- `module.py` `boot()` starts one `IUserDataStream` and schedules `HoldingsRefreshService` only on
  Spot, `PositionRefreshService` only on Futures.
- `OrderFilledEvent`, `PositionChangedEvent`, `HoldingsChangedEvent`, `EquitySampledEvent` carry no
  venue, so a screen cannot tell whose fill it is.
- Settings has one "Order Venue" combo.

## 2. Acceptance criteria
- [ ] With both venues enabled, both user data streams start, and each refresh service runs only for its own venue.
- [ ] Every trading event carries `venue`; the `LiveOrderBookCoordinator` / feeds filter on it (test: a Spot fill never lands in a Futures table).
- [ ] Settings shows one toggle per venue (Futures Testnet, Spot Testnet) and still says a restart applies it.
- [ ] Saving those toggles writes `exchange.trading_venues` (the list) and drops the legacy scalar `exchange.trading_venue`, so a config migrates on its first save (moved here from `EPIC-028A`: the Settings page is the only writer of this key).
- [ ] The Settings venue lock while `exchange.trading_venues` is configured (`_VENUE_LIST_MESSAGE` in `trading_settings_presenter.py`, added in `EPIC-028A` review F2) is removed: the per-venue toggles own the list, so Save is no longer refused.
- [ ] Disabling one venue in Settings leaves the other fully working after restart.

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
Integration against the fake exchange serving both venues; sanity boot with both enabled has no WARNING+ record; qtbot Settings test.
- Not run.

## Implementation notes (written when done)
Not started.
