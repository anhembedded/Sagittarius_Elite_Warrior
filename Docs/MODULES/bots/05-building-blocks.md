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
`kind_id`, `supported_profiles`, `validate`, `overlay` and `executor_factory`, and three concrete methods that no implementer is forced to override: `recovery_layer`, `backtester` (since `EPIC-040B`, below) and, since `EPIC-038L`, `parameter_problem` (whether the parameters a `bot edit` sets can be stored, judged without the exchange; closed by default, so a kind that declares nothing is edited by no command line; the Grid answers in `bots/domain/grid/grid_parameter_check.py` → `grid_parameter_problem`, through `GridParams.from_config`). The shell finds a kind
by its id through `IBotKindCatalog` (`bots/contracts/i_bot_kind_catalog.py` → `IBotKindCatalog`),
implemented by `BotKindCatalog` (`.../bot_kind_catalog.py` → `BotKindCatalog`); the Grid is
`GridKind` (`bots/domain/grid/grid_kind.py` → `GridKind`). A Grid's `overlay`
(`bots/domain/grid/grid_overlay.py`) draws one label per price: a range limit equal to a level's
price is part of that level's label ("L6 · range top"), else its own "range top"/"range bottom" line,
and SL/TP keep their own roles and styles (`BUG-207`).

**The kind's backtest.** `IBotKind.backtester` answers the kind's `IKindBacktester`
(`bots/contracts/i_kind_backtester.py` → `IKindBacktester`, `KindBacktestRequest`), or `None`
(concrete, `None` by default). The request is the symbol, the parameters, the symbol's terms, the
venue, an interval and a period, an optional `warmup` before the period, and a `cancelled` poll;
the answer is a kind-neutral `BacktestAnswer`: a `BacktestOutcome`, a `BacktestRefusal` in words,
or a `BacktestCancelled`. The outcome (`bots/domain/backtest/backtest_outcome.py` →
`BacktestOutcome`) is an envelope every pane can read, with no kind named: the candles replayed,
the equity curve against buy and hold, the fills (each labelled), the fees, the provenance,
`figures` (an ordered list of labelled raw values with a kind and a tone), `notes` (the caveats,
the missing funding first) and `detail`, the kind's own rich result. The Grid's adapter is
`bots/application/kinds/grid/grid_kind_backtester.py` → `GridKindBacktester`: it runs the existing
`RunGridBacktestQuery` handler and maps the answer (`outcome_of`), keeping `GridBacktestResult`
whole as `detail`; its figures and notes are written once, in
`bots/domain/grid/grid_figures.py` → `grid_figures`, `grid_notes`, which the Grid page's summary
reads too until `EPIC-040F`. `GridKind` is given its adapter where it is built
(`bots/composition/executor_bindings.py` → `_build_kind_catalog`). No file of the outcome, the port
or `IBotKind` imports a kind (`tests/unit/architecture/test_backtest_outcome_is_kind_neutral.py`).
Nothing draws the outcome yet: the Grid page still reads `GridBacktestResult`, until `EPIC-040D`
and `EPIC-040F`.

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
    pause (the fact the `rate_limited` probe reads), stream gap and tick extremes.
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

The ladder of a Grid bot (`BOT-193`) is a read model in the same layer: `bots/contracts/grid_ladder.py` →
`grid_ladder_of`, `GridLadder`, `LadderRow`, `PricePosition` builds one row per grid, the summary and the
distances from a `BotSnapshot` alone (its saved parameters read now, its saved run), calling
`bots/domain/grid/grid_derived.py` → `grid_profits` for the step and net arithmetic; no exchange call, no
host, no Qt. The words are `bots/contracts/grid_ladder_texts.py`, shared by the Bots tab and (next) the
commands. In the tab `bots/ui/bots_screen/bot_detail.py` → `detail_for` computes it with the clock the
other figures use, `bots_view_model.py` → `BotsViewModel.set_ladder` holds it, the Ladder dock
(`bot_ladder_panel.py` → `BotLadderPanel`, rows from `bots_table_models.py` → `BotLadderTableModel`) shows
the table and the Plan panel (`bot_plan_panel.py` → `BotPlanPanel`) shows the grid step, the profit per
cycle and where the last price stands. What the record cannot give is a blank cell or a sentence, never a
zero: the account's maker rate and a Futures liquidation price are not saved, so the net after fees is
unknown and the liquidation row says so.

## Built: the protective stop's parts (Futures)

The stop is the Futures Grid's, behind one port like the opening and the close
(`bots/contracts/i_exposure_protection.py` → `IExposureProtection`, `ProtectionVerdict`):
`ProtectiveStopService` (policy) over `ProtectiveStopBook` (records and orders), the decorator
`ProtectedCloser`, the wording of a halt that cannot close (`stop_words.py` → `stop_words`, read through `IExposureProtection.describe_stop`), and Spot's `NoProtection`, all under `bots/application/kinds/grid/protection/`;
the record and its machine under `bots/domain/grid/` (`protective_stop.py` → `ProtectiveStop`;
`protective_stop_fsm_matrix.py` → `PROTECTIVE_STOP_TRANSITIONS`). The gateway splits its tagged
reads in two (`bots/application/services/orders/bot_account_reads.py` → `BotAccountReads`) and builds
the request (`.../protective_stop_request.py` → `protective_stop_request`). In `trading`, an order
gains `close_position` and `working_type` (`trading/contracts/order.py` → `Order`), carried by the
existing Algo Order mapping.

## Built: the halt-recovery policy and ledger

*Which halts are transient, and how many attempts has a bot used?* Plain data and pure functions in the
domain (`EPIC-042B`); a halt uses them from `EPIC-042C`.
`bots/domain/halt_recovery_policy.py` → `HaltRecoveryRule`, `RuleChange`, `RecoveryLayer`, `COMMON_LAYER`,
`EffectivePolicy`, `effective_policy` is the layered policy of [the decision](../../../Tasks/epics/EPIC-042_halt_auto_recovery/DECISION_2026-10-17_halt_auto_recovery.md) §2.3. A kind
contributes its layer through `bots/contracts/i_bot_kind.py` → `IBotKind.recovery_layer` (concrete, empty
by default; the Grid's is `bots/domain/grid/grid_kind.py` → `GRID_RECOVERY_LAYER`), a market through
`bots/contracts/venue_profile.py` → `VenueProfile` (field `recovery_layer`; Futures sets
`clears_lower_layers`). The attempts live in the bot's lifecycle, `bots/domain/bot.py` →
`BotLifecycle` (field `recovery_attempts`), counted by `bots/domain/recovery_ledger.py` →
`RecoveryAttempt`, `attempts_within`, `budget_left`, `recorded`. The state they serve is in
[`state-machines.md`](state-machines.md); the effective table is in [`10-quality.md`](10-quality.md).
`bots/domain/bot_lifecycle_fsm_matrix.py` → `RESUME_PROPOSES_STATES` is the one answer to "does a Resume
re-plan here", asked by the resume use case, the runner, the executor and the screen.

What uses them (`EPIC-042C`): `bots/application/services/lifecycle/halt_recovery_director.py` →
`HaltRecoveryDirector` picks `halt` or `halt_transient` for `BotRunState.halt`; the Grid's recovery run is
`bots/application/kinds/grid/recovery/grid_halt_recovery.py` → `GridHaltRecovery`, with its probe
`bots/application/kinds/grid/watch/grid_halt_probe.py` → `GridHaltProbe` over the contract
`bots/contracts/i_halt_condition_probe.py` → `IHaltConditionProbe` and the stream's status
`bots/contracts/i_user_stream_status.py` → `IUserStreamStatus`, kept by
`bots/application/services/watches/user_stream_status.py` → `UserStreamStatus`.

The exchange's pause is the third reason the probe knows (`EPIC-042F`): the Grid's layer declares
`rate_limited` (`bots/domain/grid/grid_kind.py` → `GRID_RECOVERY_LAYER`, with the shared rule
`bots/domain/halt_recovery_policy.py` → `PAUSE_RULE`), and *clear* is `bots/application/kinds/grid/watch/grid_rate_limit_pause.py`
→ `GridRateLimitPause.holds` saying the pause the bot met is over. `GridRateLimitPause` keeps the one
fact the halt cannot carry, when that pause ends on the bot's monotonic clock; the timer, its
consecutive counter and the second recovery mechanism they were are gone.

## Built: the account-level loss cap's parts

*Which component adds up the day's loss, which stops the bots, and where does the owner's figure
sit?* (`EPIC-026L`, the owner's decision N3: one figure per host, in the owner's quote asset.) The
sequence is in [`06-runtime.md`](06-runtime.md), the files in [`07-deployment.md`](07-deployment.md),
the constants in [`10-quality.md`](10-quality.md).

- **Pure rules** in `bots/domain/loss_cap/`: the owner's figure and its parser
  (`loss_cap_figure.py` → `LossCapFigure`, `parse_loss_cap_figure`, `LossCapFigureError`), the day's
  ledger of each bot's result since 00:00 UTC (`loss_cap_ledger.py` → `LossCapLedger`, `BotDayFigure`,
  `BotObservation`, `day_start_of`) and when the cap trips (`loss_cap_policy.py` → `loss_reached`,
  `unjudged_too_long`, `UNJUDGED_TRIP_AFTER`, `LossCapTrip`, `LossCapTripReason`, `LossCapRecord`).
- **The service** in `bots/application/services/loss_cap/`: `account_loss_cap.py` →
  `AccountLossCap` (the one object behind three narrow ports: `ILossCapHold`, `ILossCapStatus`,
  `ILossCapAcknowledgement`, all in `bots/contracts/`), over `loss_cap_sampler.py` →
  `LossCapSampler` (one read of the bots, through `GetBotStatusReportQuery`) and `loss_cap_stopper.py`
  → `LossCapStopper` (a trip's `StopBotCommand` per bot not at rest, the Bots tab's own Stop).
  `loss_cap_preflight_check.py` → `LossCapPreflightCheck` and `loss_cap_health_contributor.py` →
  `LossCapHealthContributor` say what the owner reads.
- **The record** is `bots/contracts/i_loss_cap_store.py` → `ILossCapStore`, kept by
  `bots/adapters/file_loss_cap_store.py` → `FileLossCapStore`.
- **Where it plugs in.** `BotRunner.start` and `BotRunner.resume` ask `ILossCapHold` first
  (`bot_runner.py` → `BotRunner._loss_cap_refusal`), the one place every start and resume passes.
  `writable_boot.py` → `boot_writable` registers `AccountLossCap.sample` on the bots ticker;
  `bots/composition/loss_cap_bindings.py` → `bind_loss_cap` builds it from `bots.account_loss_cap`.
  The owner's acknowledgement is `AcknowledgeLossCapForHostCommand`
  (`bots/contracts/host_bot_requests.py`), answered by
  `bots/application/use_cases/acknowledge_loss_cap_for_host/handler.py` →
  `AcknowledgeLossCapForHostCommandHandler`, reached from the command line by
  `bots/cli/bot_control_verbs.py` → `AcknowledgeLossCapVerb` and the host's command directory
  (`operations/application/bot_host_command_executor.py`, `HostControlAction.ACKNOWLEDGE_LOSS_CAP`).
- **The alert.** `alerting` turns `AccountLossCapTrippedEvent` into `AlertKind.ACCOUNT_LOSS_CAP_TRIPPED`
  (`alerting/application/sources/bot_alert_source.py` → `BotAlertSource.on_account_loss_cap_tripped`).

## Planned

| Change | Where | Task |
| :--- | :--- | :--- |
| The workbench draws any kind's outcome; the Grid page reads it instead of `GridBacktestResult` | `bots/ui/` | `EPIC-040D`, `EPIC-040F` |
| The strategy kind, a second `IBotKind` | its own `bots/application/kinds/<kind>/` | `EPIC-040G` |
| A halt that leaves the position under a standing stop (D10) and the custody of that stop (D13) | `bots/application/services/positions/` | `EPIC-039L`, deferred from C3 |
| `run --resume-halted` | `operations/`, `bots/application/use_cases/` | `EPIC-042E` |
