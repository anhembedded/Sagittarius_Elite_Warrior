# SDD §5 — Module contracts: what was specified, and what shipped

> Part of the SDD, split out of the single `README.md` this document used to be
> (2026-09-15, user decision). Every `###` heading below is **verbatim** from that
> file, so a reference written as *"SDD, 'Threading contract'"* still resolves.
> [`README.md`](README.md) is the index.

**The file that grows with every phase.** Each context's published surface is
specified here before it is built and corrected here after, with the
measurement that moved it. That is the traceability this split was asked for:
a reader comparing the code to the spec reads one file, and a pull request
that discovers a divergence edits one file (`epic-025.prompt.md` §3 step 10
makes that a step rather than a courtesy).

### The symbol lease (SDD-04) — `ITradingSession`

```python
class ITradingSession(ABC):
    def claim_symbol(self, symbol: str, owner_id: str) -> None: ...     # raises SymbolAlreadyLeased if another owner holds it
    def release_symbol(self, symbol: str, owner_id: str) -> None: ...   # no-op if not held by owner
```

Semantics are an **exclusive lease that refuses**, not a fencing token that supersedes:
`ActionOwnershipTracker.begin_action` invalidates the previous action (`action_superseded`), and a
lease must do the opposite, or a manual order would silently revoke an armed strategy. Who holds a
lease is **not** exposed on the public port (a diagnostic query stays internal to `trading`);
`IOrderSubmission.execute(intent)` refuses an intent whose `owner_id` differs from the holder
(`OrderRejectionReason.SYMBOL_LEASED`). `strategy` claims on arm and releases on disarm; a manual
order carries `owner_id="manual"`. The lease is an **addition** to the existing rules: `arm_strategy`
still reads `ITradingSession`'s enabled state (`arm_strategy/handler.py:62`), which is a legal
`strategy → trading` dependency.

### Errors in `contracts/` — the fifth kind

A port's failure modes are part of its contract, so `contracts/errors/` is allowed and holds only
exceptions the port raises across the boundary: `core/contracts/errors.py::ContributionError`,
`trading/contracts/errors/SymbolAlreadyLeased`, and the `OrderRejectionReason` enum.

### `market_data`: what this specification asked for, and what shipped

All five ports are built (PR 0.5 through PR 1.2), and **every one of them differs from the shape
specified here** — four in mechanism, one in a name. The list below is the authoritative record of that distance; `SDD-06b` now draws
the shipped signatures with the same reasons in per-port notes, so the diagram and this section say
one thing. The shipped surface itself is described where it lives — HLD
[§3.4](../HLD/03_module_contracts.md)'s `market_data` table, and each port's own docstring.

Four of the five share one cause, worth stating once: **ADR D12 keeps business behaviour out of
a port pull request.** A port PR renames a call path; it does not change what the system does. Every
item below is a place where the specified shape could not be built without also changing behaviour,
so the port published what the code actually does and the seam was left for the phase that needs it
(`architecture-rule.md` §7.2.1 — cut a seam at the second consumer, not in advance).

**1. `IMarketDataSync` shipped without a handle.** Specified:
`sync(symbol, timeframe, start, end, owner_id) -> SyncHandle` (a frozen DTO carrying the Engine's
`CancellationToken`) plus `cancel(handle)`. Shipped: `sync(request: MarketDataSyncRequest) -> None`,
with cancellation as a caller-owned `CancellationCheck` callable the implementation polls between
fetches. The caller already owns cancellation (`async-ui-action-rule.md`), and the module must not
learn the Engine's `CancellationToken` to read one bool. Returning `None` is deliberate rather than
unfinished: callers read the store or watch the progress events afterwards, and the handler this
port wraps has always returned `None`. Nothing named `SyncHandle` exists in `src/`.

**2. `IMarketStream` shipped without a handle either.** Specified:
`start(symbol, timeframe, owner_id) -> StreamHandle`, `stop(handle)`, `stop_all(owner_id)` — one
owner holding **several** streams (Dev Board shows *n* charts), with `owner_id` as the namespace.
Shipped: `start(owner_id, symbols, interval) -> StreamOutcome` and `stop(owner_id)`, which publish
what `BOT-126` actually built — one subscription **set** per owner, replaced on every `start`,
released together. So today's `stop(owner_id)` is both the specified `stop(handle)` and its
`stop_all(owner_id)`. A handle is not a naming choice: it needs `ILiveStreamService` to hold
per-stream subscriptions instead of replacing an owner's set. Phase 2's `strategy` (one stream per
armed symbol) is the consumer that needs the split, and that is when the seam is cut.

**3. `ISymbolCatalog` shipped without `quote_asset`.** Specified:
`list_symbols(quote_asset: str | None)`. Measured, nothing filters by quote asset: the picker's tabs
split the whole list in `ui/components/symbol_picker/quote_asset.py`, and no caller has ever asked
the module for a subset. What shipped is `list_symbols(force_refresh=False)` — the flag the picker's
manual refresh does pass (`BUG-066`) — on HLD §2.4's rule, the same one that kept
`days_back_if_empty` out of `MarketDataSyncRequest` in PR 0.5. Publishing `quote_asset` would
publish a filter no implementation applies.

**4. `IHistoricalKlines` shipped as two methods, not one.** Specified: one
`load(symbol, timeframe, start, end)`. The handler it replaced returned
`list[MarketData] | dict[str, list[MarketData]]`, chosen by whether `symbol` was a `str` or a
`list` — a union decided by an argument's **runtime type**, which `architecture-rule.md` §2.1
forbids. Shipped: `load()` for one symbol and `load_many()` for several, keyed by symbol, each with
one return type. Only the Dev Board loads several at once; `load_many()` is a separate method rather
than a loop because its implementation may fetch concurrently, which is the only reason a caller
would ask that way. The rows come back as tuples, not lists: they are a snapshot
(`domain-truth-rule.md`).

**5. `IRangeCoverage`'s answer is `BacktestRangeCoverage`, not `RangeCoverageSnapshot`.** This is
the one divergence that is purely a name, and it is deliberate. `RangeCoverageSnapshot` exists — it
is `IMarketDataRepository`'s own answer, five aggregates the database computed — so reusing that
name on this port would have pointed a reader at the wrong type. Three screens already read every
field of `BacktestRangeCoverage` to tell the user *why* a range is unusable (`BUG-072`), and
renaming a DTO that crosses the edge is behaviour-free churn ADR D12 has no room for. The method
also takes `now` explicitly, because "is the last candle still open?" is a question about the clock
and a port must not read it for itself.

---

### `trading`: what this specification asked for, and what shipped

All three ports are built (PR 1.3b), and two of the three differ from what was
specified — plus two specified types that were never written at all and one
that had to be renamed. The pattern is the same one `market_data` set above:
the port publishes what the code actually does, and the distance is recorded
here rather than left for a reader to discover against the code.

**1. The published DTOs keep their own names.** HLD §3.4 said *"`LivePosition`
**never leaves** the module; `PositionSnapshot` is its flat DTO"*, and listed
`PositionSnapshot`, `OpenOrderSnapshot` and `AccountSnapshot` among the
published types. Measured before deciding: `Order` is a frozen dataclass with
eleven fields and **zero** methods; `LivePosition` is frozen with eight scalar
fields, a `LiquidationPrice` (a `NewType` over `Decimal`) and one pure
derivation (`side`, the sign of `position_amt`). A `PositionSnapshot` would
therefore be field-for-field identical — behaviour-free churn, and ADR D12 has
no room for it in a port pull request. It is also the same argument PR 1.2
used to **keep** the name `BacktestRangeCoverage`, so renaming here would have
made the epic inconsistent with itself. Both moved into `contracts/` under
their own names, and the 20 allowlist entries that named them retired without
one consumer being touched.

`AccountSnapshot` was never written: what the account read answers with is
`ExchangeConnectionStatus`, which already existed and already carried every
field the three measured consumers read.

**2. `OrderIntent` became `OrderRequest`.** HLD §3.4 listed `OrderIntent` among
trading's published DTOs. That name was already taken twice —
`order_intent_for()` in `modules/trading/domain/policies/` owns it for the
`(side, reduce_only)` pair a `SignalAction` maps to, and
`modules/market_data/contracts/symbol_market_metadata.py` holds a third. Two
published types with one name is how a reader picks the wrong one, so the
port's argument type is `OrderRequest`, carrying `PreviewOrderQuery`'s six
fields unchanged.

**3. `ITradingSession` shipped without the symbol lease.** Specified:
`claim_symbol(symbol, owner_id)` / `release_symbol(...)`, an exclusive lease
that refuses, so a manual order cannot be placed on a symbol a strategy is
armed on. Its first consumer is `strategy`, which claims on arm and releases
on disarm — and `strategy` is Phase 2. A lease published now would be new
exclusive-locking behaviour on the most dangerous mutable state in the app
with **no caller at all**, which `architecture-rule.md` §7.2.1 (cut the seam
at the second consumer) and ADR D12 both keep out. Phase 2 adds it under the
existing lock with claim-then-execute as one critical section, which is the
design the worked example above already argues. Same deferral, same reason, as
`IMarketStream`'s `StreamHandle` in PR 1.1b.

**4. What `snapshot()` carries, and why the port exists at all.** The import
count was never the real cost. Four presentation files read `enabled`,
`orders_sent_this_session` and `known_open_symbols` **directly off the mutable,
lock-guarded `TradingSessionState`** — from the UI thread, while the websocket
thread's `reconcile_position()` rewrote the symbol set. Those three fields are
exactly what `TradingSessionSnapshot` carries and nothing more (HLD §2.4), and
`TradingSessionState.read_all()` takes the lock **once** so the three cannot be
returned as a combination that never existed. It copies the set inside the
lock: handing a reader the live object would be handing them a race dressed as
a value.

**5. The commands stay internal.** `IOrderSubmission` takes `OrderRequest` and
translates it to `PreviewOrderQuery` / `ExecuteOrderCommand` inside the module.
Publishing a command object is the transitional dispatch surface this epic is
retiring, so the port publishes a request and keeps the CQRS vocabulary behind
the boundary — `IMarketDataSync`'s `MarketDataSyncRequest` set that shape in
PR 0.5.
