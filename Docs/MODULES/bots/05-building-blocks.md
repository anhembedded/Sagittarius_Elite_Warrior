Status: Current

# `bots` — 5. Building blocks

*Which components do the work, which one calls which, and what are the domain types and contracts?*

Five pictures, drawn by hand at a high level, one question each:

- [`diagrams/05-command-path.puml`](diagrams/05-command-path.puml) — *which components carry an
  owner's command to the exchange?*
- [`diagrams/05-event-path.puml`](diagrams/05-event-path.puml) — *how does an exchange event reach the
  one bot it concerns, and where is the result kept?*
- [`diagrams/05-kind-seam.puml`](diagrams/05-kind-seam.puml) — *where does a new kind of bot plug in?*
- [`diagrams/05-domain.puml`](diagrams/05-domain.puml) — *what is a bot made of, and what does a Grid
  add?* (the facts: [`08-concepts.md`](08-concepts.md))
- [`diagrams/05-contracts.puml`](diagrams/05-contracts.puml) — *which ports does a caller or a new
  kind build against?*

## Built: a command's path

`BotRunner` (`bots/application/services/lifecycle/bot_runner.py` → `BotRunner`) takes a command from a
use case (`bots/application/use_cases/`, one directory each: start, pause, resume, stop, and the
host's start, stop and resume) and hands it to `BotExecutors` (`.../bot_executors.py` →
`BotExecutors`), which holds one executor per bot. For the Grid kind that is `GridExecutor`
(`.../grid_executor.py` → `GridExecutor`), built by `GridExecutorFactory`
(`.../grid_executor_factory.py` → `GridExecutorFactory`) with a `BotOrderGateway`
(`.../bot_order_gateway.py` → `BotOrderGateway`), the bot's one way to `trading`. Every call to an
executor is queued and run in order on the bot's own worker ([`07-deployment.md`](07-deployment.md)).

## Built: an event's path

Exchange and market events arrive at `BotEventRouter`
(`bots/application/event_handlers/bot_event_router.py` → `BotEventRouter`), which only copies and
queues: it finds the executor that owns the client order id, or every executor on the venue for a
switch, and hands the event to its `GridFacts` (`.../grid_facts.py` → `GridFacts`), which acts on the
bot's worker. While a bot has a worker, its state has one writer there, `BotRunState`
(`.../bot_run_state.py` → `BotRunState`); who else writes a bot, and when, is in
[`07-deployment.md`](07-deployment.md). Everything is stored through `IBotStore`
(`bots/contracts/i_bot_store.py` → `IBotStore`): `NotifyingBotStore`
(`.../notifying_bot_store.py` → `NotifyingBotStore`) publishes `BotChangedEvent` after each write and
hands it on to `JsonBotStore` (`bots/adapters/persistence/json_bot_store.py` → `JsonBotStore`). A
second copy of the app gets read-only wrappers instead (`.../read_only_bot_store.py` →
`ReadOnlyBotStore`; `.../read_only_bot_runner.py` → `ReadOnlyBotRunner`).

## Built: the seam a kind plugs into

A new kind plugs in through one seam, `IBotKind` (`bots/contracts/i_bot_kind.py` → `IBotKind`):
`kind_id`, `supported_profiles`, `validate`, `overlay` and `executor_factory`. The shell finds a kind
by its id through `IBotKindCatalog` (`bots/contracts/i_bot_kind_catalog.py` → `IBotKindCatalog`),
implemented by `BotKindCatalog` (`.../bot_kind_catalog.py` → `BotKindCatalog`); the Grid is
`GridKind` (`bots/domain/grid/grid_kind.py` → `GridKind`). A Grid's `overlay`
(`bots/domain/grid/grid_overlay.py`) draws one label per price: a range limit equal to a level's
price is part of that level's label ("L6 · range top"), else its own "range top"/"range bottom" line,
and SL/TP keep their own roles and styles (`BUG-207`).

The shell does not import a kind. Today's exceptions, files of the shell that still import Grid
types, are listed in `tests/unit/architecture/baseline_bots_shell_imports_a_kind.txt`, and the list
only shrinks (`tests/unit/architecture/test_bots_services_stay_grouped.py`).

## Built: where the code lives

The application services are split first by kind, then by feature (`BOT-177`). A path written
`.../<name>.py` in this folder is the file of that name in one of these packages, under
`bots/application/`:

- `services/` is the shell every bot kind shares, and nothing sits loose in it:
  - `lifecycle/`: the runner, run state, executors registry, command gate and lock, restore and boot
    recovery, lookup, the read-only runner and store, the notifying store, the kind catalog and the
    health contributor.
  - `orders/`: the order gateway, order history and outcome, order flags (Spot and Futures), the
    order-session opening and applied fills.
  - `venue/`: what the venue allows and costs: facts, needs, profiles, rules and the settings gates,
    symbol brackets and status, the Futures rules and start checks, the mark source, account and
    funding views, exchange terms.
  - `positions/`: exposure books and checks, closers, opening strategies and cost models, each
    Spot/Futures pair side by side.
  - `risk/`: the risk guards and risk reads.
  - `readiness/`: the readiness reader and assessment, resume readiness, the progress reader and run
    facts.
  - `watches/`: the price, user-stream and sleep watches, the clock-gap detector, the wake-exit check
    and streamed fine klines.
- `kinds/grid/` is everything that knows the Grid; a second kind gets its own `kinds/<kind>/` beside
  it:
  - the package itself: the executor and its factory, facts, ladder placer, run context, runtime
    codec, task guard, budgets, exposures, housekeeping, parking, margin mode, order failure, earlier
    runs, reference price, ladder needs, off-ladder orders, planner numbers and the Futures backtest
    terms.
  - `start/`: start preconditions, the start sequence and the interrupted start.
  - `stop/`: the stopper, stop sequence, request, retry and waiting, exit slices and the mark exit.
  - `watch/`: the range, risk, storage, terms and key watches, price age and reaction, the rate-limit
    pause, stream gap and tick extremes.
  - `recovery/`: the reconciler (with the missed fills it applies and the quantities it aligns, in
    their own files), the recovery reader and the resume sequence.

## Built: the contracts

The ports in [`diagrams/05-contracts.puml`](diagrams/05-contracts.puml) are `IBotStore` with
`StoredBot` (`bots/contracts/i_bot_store.py` → `IBotStore`, `StoredBot`), `IBotRunner`
(`bots/contracts/i_bot_runner.py` → `IBotRunner`), `IBotKind`, and `IBotExecutor` with its factory
(`bots/contracts/i_bot_executor.py` → `IBotExecutor`, `IBotExecutorFactory`). What a screen reads is
`BotSnapshot` (`bots/contracts/bot_snapshot.py` → `BotSnapshot`); a plan applied from a file is
`AppliedPlan` (`bots/contracts/applied_plan.py` → `AppliedPlan`). Their members are in the code, not
copied here.

## Built: the protective stop's parts (Futures)

The stop is the Futures Grid's, behind one port like the opening and the close
(`bots/contracts/i_exposure_protection.py` → `IExposureProtection`, `ProtectionVerdict`):
`ProtectiveStopService` (policy) over `ProtectiveStopBook` (records and orders), the decorator
`ProtectedCloser`, and Spot's `NoProtection`, all under `bots/application/kinds/grid/protection/`;
the record and its machine under `bots/domain/grid/` (`protective_stop.py` → `ProtectiveStop`;
`protective_stop_fsm_matrix.py` → `PROTECTIVE_STOP_TRANSITIONS`). The gateway splits its tagged
reads in two (`bots/application/services/orders/bot_account_reads.py` → `BotAccountReads`) and builds
the request (`.../protective_stop_request.py` → `protective_stop_request`). In `trading`, an order
gains `close_position` and `working_type` (`trading/contracts/order.py` → `Order`), carried by the
existing Algo Order mapping.

## Planned

| Change | Where | Task |
| :--- | :--- | :--- |
| One kind-neutral backtest result and simulator port | `bots/application/`, `bots/contracts/` | `EPIC-040B` |
| The strategy kind, a second `IBotKind` | its own `bots/application/kinds/<kind>/` | `EPIC-040G` |
| The halt asks the exchange whether a stop stands; the Emergency Stop closes, then cancels conditional orders | `bots/application/services/positions/`, `trading/application/session/emergency_stop/` | `EPIC-039L` C3 |
| The mainnet gate as a port, `IVenueOpening`, in place of `CLOSED_VENUES` | `bots/contracts/` | `EPIC-039L` C4 |
| The halt-recovery mechanism: the state `AWAITING_RECOVERY`, the director that picks `halt` or `halt_transient`, the recovery policy composed as data from a common, a kind and a venue layer (`COMMON_LAYER`, `IBotKind.recovery_layer`, `VenueProfile.recovery_layer`), the probe that says a reason has cleared, and the attempt ledger in the bot record | `bots/domain/`, `bots/application/services/lifecycle/`, `bots/contracts/i_bot_kind.py` | `EPIC-042B`, `EPIC-042C` |
| `run --resume-halted` | `operations/`, `bots/application/use_cases/` | `EPIC-042E` |
| The grid rate-limit resume moves onto that mechanism | `bots/application/kinds/grid/watch/` | `EPIC-042F` |
