# EPIC-028B — Every order, cancel, enable, emergency stop and arm names the venue it acts on

**Status:** 🟡 Awaiting review (2026-09-29) — implemented and verified on the fast tier; code merge waits on the independent review (`ONBOARDING.md` §7)
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🔴 — the safety gates move from a global venue to a per-command venue; a missed call site is an order on the wrong exchange
**Complexity:** L — every trading handler, `OrderSubmissionService`, strategy arming
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028A](EPIC-028A_venue_context_and_registry.md)

---

## 1. Context and problem
- `ExecuteOrderCommand` (`application/orders/execute_order/command.py`) carries `order_request`,
  `live`, `owner_id` — no venue; the handler uses the one bound `ITradingClientFactory`.
- Cancel, Enable/Disable trading, Emergency Stop, Arm/Disarm handlers resolve single-venue ports;
  one armed strategy per process (`disarm_strategy/command.py`).

## 2. Acceptance criteria
- [x] `ExecuteOrderCommand`, cancel one / cancel all, `EnableTradingCommand`, `DisableTradingCommand`, `EmergencyStopCommand`, `ArmStrategyCommand`, `DisarmStrategyCommand`, `GetOpenPositionsQuery`, `GetHoldingsQuery`, `GetExchangeConnectionStatusQuery` each carry `venue: TradingVenue` (no default). `PreviewOrderQuery` too; `ExecuteOrderCommand`/`SubmitOrderCommand` read it from their `order_request`, so the two can never disagree.
- [x] With both venues enabled, Emergency Stop on Futures leaves Spot's session, orders and baseline untouched, and vice versa (`tests/unit/modules/trading/application/test_venue_isolation.py`).
- [x] One strategy can be armed per venue at the same time; arming on Spot still refuses SHORT-capable strategies (EPIC-027N) and Futures still allows them (`tests/unit/modules/strategy/application/use_cases/test_arm_strategy_per_venue.py`).
- [x] `supports_order_submission`, trading limits and the Spot baseline are checked against the command's own venue (`test_execute_order.py`, `test_enable_trading.py`, `test_emergency_stop.py`, `test_module_trading_client_per_venue.py`).
- [x] The Phase-1 single-venue shim from `EPIC-028A` is deleted (`test_module_venue_contexts_binding.py::test_no_per_venue_port_is_bound_on_its_own`); `tests/unit/architecture/test_venue_addressed_handlers_resolve_their_venue.py` fails if a trading or strategy-arming handler is built with a single venue's port, state or `TradingVenue`, or asks a lookup for its `primary()`.

## 3. Design
Handlers take `IVenueContexts` and call `contexts.get(command.venue)` once at the top — the Resolve-once pattern `EmergencyStopCommandHandler` already uses for `TradingVenue.market_type`. `OrderSubmissionService` gains a `venue` argument. The Dev Board keeps working by passing its configured venue.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/application/**/command.py`, `query.py`, `handler.py` | `venue` field; resolve context |
| `src/modules/trading/application/orders/order_submission_service.py` | `venue` argument |
| `src/modules/strategy/…/arm_strategy`, `disarm_strategy` | one arming slot per venue |
| `src/modules/trading/ui/**` | callers pass their venue |
| `tests/unit/architecture/` | guard: handlers only reach venue ports via `IVenueContexts` |

## 5. Testing
Unit per handler (right context used, other untouched); integration: both venues on the fake exchange, Emergency Stop isolation.
- Run 2026-09-29 on the final tree: ruff and format clean; mypy clean (751 files); `tests/unit` + `tests/integration` (without `presentation`) 6121 passed; `tests/integration/presentation` 57 passed, 4 skipped; `tests/sanity` 32 passed. No new warning.
- Mutation-verified (each turned its test red, then restored): Emergency Stop always on Futures (isolation test); the ports registry always building Futures' service (binding test); the arm handler always using Futures' session (per-venue arming test); removing the `supports_order_submission` gate in `SubmitOrderCommandHandler` (`test_module_trading_client_per_venue.py`); shutdown stopping only the first venue's stream, or one `try` around the loop (shutdown test); a `TradingSessionState` constructor parameter on a handler (the new guard); re-binding `IUserDataStream` on its own (shim test).

## Implementation notes (written when done)
1. **Two per-venue lookups, one per layer.** Trading handlers take `VenueTradingScopes` (application: the venue's `VenueContext` plus its own `TradingSessionState` and `EquityCurveRecorder`, from `VenueSessionStates`) or `IVenueContexts` when they need ports only. Another module takes `IVenueTradingPorts` (contracts: order submission, trading session, account snapshot, equity curve per venue). Each resolves `command.venue` once, at the top; an unserved venue raises `VenueNotEnabledError` before any state is created for it.
2. **Services are bound to a venue.** `OrderSubmissionService`, `TradingSessionService`, `AccountSnapshotService` and both refresh services take their venue at construction and stamp it on every command, so a screen holds the service of the venue it trades instead of passing a venue per call.
3. **The single published ports stay, bound to the primary venue.** `IOrderSubmission`, `ITradingSession`, `IAccountSnapshot`, `IEquityCurve`, `IStrategyArming` and `LiveStrategySession` resolve to the primary venue's bundle: the single Trading screen and the Dev Board show one venue until the two desks replace them (`EPIC-028K`/`L`/`M`). They are consumer conveniences, not a shim: nothing in a handler can reach them (the guard).
4. **One `LiveStrategySession` per venue.** `VenueStrategySessions` builds each venue's session on first use from that venue's own ports; `MarketTickEventHandler` feeds a tick to every built session. The live stream carries no market type yet, so routing a tick to the session of its own market moved to `EPIC-028C`, as did saving the armed configuration per venue (the store keeps the last armed one).
5. **`venue` has no default,** a deliberate exception to `testing-rule.md` §2's "a new field on a frozen dataclass has a default": a default venue is exactly the silent wrong-exchange order this task removes. Every construction site was updated in the same change (`pitfalls/source.md` #1).
6. **`ITradingClient` is no longer bound anywhere.** `TradingModule._bind_trading_client_if_enabled()` is deleted; `SubmitOrderCommandHandler` refuses a venue that cannot trade before it looks up any adapter, then creates the client from the venue's own factory. The sanity tier's `_NOT_DISPATCHED` entry for `SubmitOrderCommand` went with it, and `test_module_trading_client_binding.py` became `test_module_trading_client_per_venue.py`, which drives the refusal through a real container instead of an unbound type.
7. **A verified fake for `IVenueContexts`.** `trade-once` (strategy) and the Settings presenter now read the primary venue's context; a test outside `trading` may not mock trading's ports, so `contracts/testing/` gained `FakeVenueContexts` (held to `VenueContextsContract` alongside the real registry) and `fake_venue_context()`, whose unarranged slots fail a test that reaches them instead of answering like a `Mock`.
8. **Shutdown stops every enabled venue's user-data stream,** each in its own `try`, so one socket failing to close cannot leave the other open.
