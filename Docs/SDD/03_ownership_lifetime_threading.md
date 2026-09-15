# SDD §3 — Ownership, lifetime and threads

> Part of the SDD, split out of the single `README.md` this document used to be
> (2026-09-15, user decision). Every `###` heading below is **verbatim** from that
> file, so a reference written as *"SDD, 'Threading contract'"* still resolves.
> [`README.md`](README.md) is the index.

Who owns a contributed panel, how long it lives, and which thread may touch
a port. One file because a change to any of the three is a change to the
other two: an owner that outlives its surface is a lifetime bug, and a port
called from the wrong thread is an ownership bug that looks like a race.

### Ownership of a contributed panel — no Coordinator in DI (ADR D12, `async-ui-action-rule` §2)

A factory returns a **panel**: a `View` and its `Presenter`, built together. The Presenter constructs
and owns its Coordinators (constructor injection, as today at `trading_presenter.py:274`) and its
own `ActionOwnershipTracker`. A panel contributed to two surfaces is therefore **two independent
instances** — exactly today's behaviour, where `TradingPresenter` and `DashboardPresenter` each
construct a `LiveOrderBookCoordinator`. What is shared is **truth, not objects**: the module's feed
(one `OrderFeed`, one `PositionRefreshService`, both application-level singletons) and the events
on the bus. No Coordinator, Presenter or widget is ever registered in the container. This is what
"one widget, many places" means: one *class*, many *instances*.

### Lifetime

- A surface is built **once**, on first navigation, and kept: `PresenterManager` caches the view and
  presenter per route (`presenter_manager.py:71-79`). Factories therefore run once per surface per
  process. Navigating away hides, it does not destroy.
- Module-level subscriptions (`subscribe(bridge)`) live for the process. A panel's Presenter owns a
  `QtEventBridge` of its own and calls `off_all()` in `dispose()`, as `BasePresenter` does today.
- On shutdown, `MainWindow` disposes surfaces in reverse creation order; a panel whose action is in
  flight records `ActionOutcome.INVALIDATED` through its tracker before its bridge is torn down.

### Threading contract for ports

The Engine's `MemoryEventBus` delivers on the **emitting thread**. `MarketTickEvent` is emitted from
the market websocket thread; `strategy`'s handler runs there; so `IOrderSubmission.execute()` and
`ITradingSession.claim_symbol()` are called **off the main thread**. The rules, per kind:

| Kind | Rule |
| :--- | :--- |
| Port implementation | **Thread-safe by contract**: guards its state with one lock (`TradingSessionState` already has `live_submission_guard()`; the lease table lives under the same lock, and claim-then-execute is one critical section). A port never touches Qt. |
| Event | Emitted on any thread; a UI consumer subscribes through `QtEventBridge`, which hops to the main thread. Application consumers must be thread-safe. |
| Widget factory | Main thread only; a factory that is called off the main thread raises. |
| Scheduler jobs / hosted services | Task-manager threads; they reach modules only through ports and events. |

