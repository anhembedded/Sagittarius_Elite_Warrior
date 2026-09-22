# EPIC-026K — Every strategy entry carries an exchange-side protective stop: a reduce-only `STOP_MARKET` placed after the fill, cancelled on exit

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.2 row 4; ADR D8; the user (2026-09-20):
*"hãy cho lô trình để có thể giao dịch thật"*.
**Risk:** 🔴 — a second live order per entry; a stop placed on the wrong side closes nothing and
a stop not cancelled on exit opens the opposite position.
**Complexity:** L — a fill-driven step in the coordinator, a stop-order life cycle in the journal,
the cancel on exit, and the crash case (`EPIC-026H` adopts a position with or without its stop).
**Epic:** [`EPIC-026`](../README.md)
**SPEC:** updates `SPEC-005` §6 ("No brackets") and `SPEC-010` §3.
**Depends on:** [`EPIC-026G`](EPIC-026G_trade_journal.md) (the stop's order id is journaled with
its entry), [`EPIC-026I`](EPIC-026I_resilient_submission.md)

---

## 1. Context and problem

`LiveTradingCoordinator.handle()` builds one `MARKET` order per signal
(`strategy/application/services/live_trading_coordinator.py`, `OrderType.MARKET`); the exit is
the next opposite signal. `OrderType.STOP_MARKET` exists (`trading/contracts/order_type.py:19`)
and `ISizingPolicy` already takes `stop_loss_pct` (`strategy/contracts/i_sizing_policy.py:82`),
so the app knows the distance and can express the order — it never places one. While the app is
down (crash, update, laptop asleep) the position has no exit at all. Testnet never charged for
that; mainnet will.

## 2. Acceptance criteria

- [ ] On `OrderFilledEvent` for a strategy entry, the coordinator submits a reduce-only
      `STOP_MARKET` with `closePosition=true` at `entry × (1 ∓ stop_loss_pct)` rounded to the tick
      in the direction that guarantees a trigger (`OrderQuantityRoundingPolicy` extended for stop
      prices), through `IOrderSubmission.submit(live=True)` — the same gates and limits, with the
      stop exempt from `MAX_ORDERS_PER_SESSION` and `MIN_ORDER_INTERVAL` by a named exemption, not
      by bypassing the handler.
- [ ] The stop's client order id is journaled with the entry's; on the strategy's exit fill the
      stop is cancelled; on the stop's own fill the strategy is told (a new `Signal`-independent
      `PositionClosedByStopEvent`) so it starts flat.
- [ ] A partial entry fill produces one stop for the filled quantity (`closePosition=true` covers
      later fills); the stop is never duplicated on the second partial fill.
- [ ] A failed stop placement is an `ERROR` under `App.LiveTradingCoordinator`, publishes
      `LiveOrderBlockedEvent`, **and trips the circuit breaker** (`EPIC-026L`) — an unprotected
      position is treated as an emergency, not a warning.
- [ ] `EPIC-026H`'s adoption re-checks the stop: present on the exchange → kept; absent → placed
      before trading is reported enabled.

## 3. Design

A `ProtectiveStopPolicy` (pure domain, `strategy/domain/policies/`) computes the stop from the
fill and the config; the coordinator owns the life cycle because it owns the entry
(`strategy` is `trading`'s customer; it may submit, it may not reach the client). The
exemption is a field on `OrderRequest` (`purpose=PROTECTIVE_STOP`) read by `TradingLimitPolicy`,
so the exemption is visible in the limit check's output rather than hidden. The manual-order path
(`SPEC-005`) does **not** get a stop in this task — a manual trader chooses their own — and §6 of
that SPEC says so.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/strategy/domain/policies/protective_stop_policy.py` | Stop price and side from a fill |
| `src/modules/strategy/application/services/live_trading_coordinator.py` | Subscribe to fills of its own entries; place, cancel, react to the stop's fill |
| `src/modules/trading/contracts/order_request.py`, `trading_limits.py`, `domain/policies/trading_limit_policy.py` | `purpose`; named exemption |
| `src/modules/trading/contracts/order_quantity_rounding_policy.py` | Stop-price rounding direction |
| `src/modules/trading/adapters/binance/futures_order_payload_mapper.py` | `stopPrice`, `closePosition`, `workingType` |
| `src/modules/strategy/contracts/events/position_closed_by_stop_event.py` | New event; `EventRegistry` row |
| `tests/unit/modules/strategy/domain/policies/test_protective_stop_policy.py` | Both sides, rounding direction |
| `tests/unit/modules/strategy/application/services/test_live_trading_coordinator.py` | Place after fill, cancel on exit, no duplicate on partial, failure trips breaker |
| `tests/integration/application/test_live_trading_pipeline_against_fake_server.py` | Entry → stop → stop fill → flat |
| `tests/sanity/binance_fake_server.py` | `STOP_MARKET` accepted; a "trigger the stop" control |
| `Docs/SPEC/SPEC-005_….md`, `SPEC-010_….md` | §6 / §3 |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Price and side | policy unit test | unit | long → sell stop below; short → buy stop above; tick rounding toward trigger |
| Life cycle | coordinator unit test | unit | one stop per entry; cancelled on exit; strategy flat after stop fill |
| Failure | coordinator unit test | unit | `ERROR`, event, breaker tripped |
| End to end | fake-server integration | integration | green |
| Testnet | `tests/testnet/` opt-in: entry, stop visible on the web UI, exit cancels it | human | recorded here |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
