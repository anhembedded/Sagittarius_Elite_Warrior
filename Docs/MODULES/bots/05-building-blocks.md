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
the equity curve against buy and hold, the fills (each labelled), the fees, the provenance, why it stopped (`StopCause`),
`figures` (an ordered list of labelled raw values with a kind and a tone), `notes` (the caveats,
the missing funding first) and `detail`, the kind's own rich result. The Grid's adapter is
`bots/application/kinds/grid/grid_kind_backtester.py` → `GridKindBacktester`: it runs the existing
`RunGridBacktestQuery` handler and maps the answer (`outcome_of`), keeping `GridBacktestResult`
whole as `detail`; its figures and notes are written once, in
`bots/domain/grid/grid_figures.py` → `grid_figures`, `grid_notes`, which the Grid page's summary
reads too until `EPIC-040F`. `GridKind` is given its adapter where it is built
(`bots/composition/executor_bindings.py` → `_build_kind_catalog`). No file of the outcome, the port
or `IBotKind` imports a kind (`tests/unit/architecture/test_backtest_outcome_is_kind_neutral.py`).
**The workbench that draws it (`EPIC-040D`).** `bots/ui/backtest_workbench/backtest_workbench.py` →
`BacktestWorkbench`, built from `WorkbenchPorts`, is one page for every kind: the interval (the charts' own `ChartToolbar`, limited to the intervals a
backtest replays by its `offered_codes`) and the period, Run, Cancel (Stop while a sync runs), Sync candles and Run without funding, the sandbox's
editor, the replay chart (`BotChart` with the kind's `IBotKind.overlay` plus the outcome's fills,
`outcome_view.py` → `result_overlay`), the equity against buy and hold (`equity_pane.py` →
`EquityPane`), the figures read-out and the fills table. The replay chart reads in the application's display time zone and offers its drop-down (`BOT-205`; `WorkbenchPorts.display_timezone`), like the Live chart it will sit beside. It names no kind: it asks the catalog for the
selected bot's kind and for a new instance of that kind's editor (`BotKindPanel`), and runs the
kind's backtester through `bots/application/queries/run_backtest/` → `RunBacktestQuery`,
`RunBacktestQueryHandler` (a kind that is unknown, or has no backtest, answers a `BacktestRefusal`).
`backtest_workbench_presenter.py` → `BacktestWorkbenchPresenter` owns one fence for the page's
background work (`ActionOwnershipTracker`); `backtest_run_coordinator.py` →
`BacktestRunCoordinator` runs the query or the candle sync off the UI thread and answers with the
action's id (the page is handed `WorkbenchPorts.run_query`, a function of the one query, never a
dispatcher, so no command is in reach by type); `sandbox_editing.py` → `SandboxEditing` holds the `SandboxSession`, the editor and the
verdicts; what the page says is one value, `workbench_state.py` → `WorkbenchState`, which the view
applies (`controls_of`). The run's lifecycle is `backtest_run_fsm_matrix.py` → `RunActivity`,
`RunEvent`, `RUN_TRANSITIONS` ([`state-machines.md`](state-machines.md)). The Bots screen shows it in
the centre's Backtest tab (`EPIC-040E`, below), and `EPIC-040F` retires the Grid's own page. Nothing in the
package imports a kind (`test_backtest_outcome_is_kind_neutral.py`) or a command, an order or an
account reader (`test_backtest_workbench_reaches_no_order_or_account.py`). The picture is
[`diagrams/06-backtest-run.puml`](diagrams/06-backtest-run.puml) in [`06-runtime.md`](06-runtime.md).

**The Bots screen hosts it (`EPIC-040E`).** The centre of the Bots mode is a stock `QTabWidget`
(`bots/ui/bots_screen/bots_view.py` → `BotsView.centre`): **Live**, the selected bot's chart, and
**Backtest**, the workbench; the bottom docks are Orders, Ladder, Fills and Log, and the Plan dock
shows the real bot on both tabs (the sandbox has an editor of its own). The tab's content is
`bots/ui/bots_screen/backtest_workbenches.py` → `BacktestWorkbenches`: one workbench per venue,
built when a bot of that venue first needs it and kept (its chart and sync read that venue's market,
`BUG-172`, and a sandbox with edits survives the selection moving to another venue, so the question
about discarding them is asked where they are), followed with the selected bot, its planner market
and its risk facts (`DetailEffects.refresh`). A bot whose kind has no `backtester()`, or whose
venue the kind's `supported_profiles()` leaves out, turns the tab off with its reason as the tooltip
(`BotsView.set_backtest_available`, `TabAvailability`): disabled, never hidden. View → Live chart tab
and View → Backtest tab (Ctrl+J) switch the tabs (`bots_command_binding.py`); the second follows the
tab. A window state saved with the old Backtest dock still loads: Qt skips a dock name the window no
longer has. A run in flight when the selection moves to a bot of another venue keeps running on its
hidden workbench (it is that bot's run); its result is there when the person comes back, and a run
that fails still tells the person through the notifier, naming the action. The page keeps its
minimum size inside the mode's: the period on one row and the commands with the status line on the
next, and the results as tabs (Replay, Equity, Figures, Fills), so a tab widget, which asks for its
widest and tallest page, leaves the mode a 1024×700 window (`test_bots_view.py` measures the width
and the height with a bot selected, with either tab in front).

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
cycle and where the last price stands, as rows of its property table. What the record cannot give is a blank
cell or a sentence, never a zero: the account's maker rate and a Futures liquidation price are not saved, so the
net after fees is unknown and the liquidation row says so.

The Plan panel's figures are one grouped property table (`BOT-206`): `bots/ui/bots_screen/plan_property_rows.py`
→ `PROPERTY_GROUPS`, `PropertyGroup`, `PropertyRow` list what it shows (Readiness, Plan, Results, Holdings, a row
per figure, keyed by the `BotFacts` field or the ladder row that writes it); `plan_property_grid.py` →
`PlanPropertyGrid` is a stock `QTreeView` over a `QStandardItemModel`, configured by the Engine's
`configure_item_view` like every table, with each row's value read by the kind of its row (`plan_property_rows.py` → `PropertyRow`; `row_kind_delegate.py` →
`RowKindDelegate`, the Engine's delegate aligning a word left and a figure right, a figure whose digits line up in
the fixed-pitch font). `BotPlanPanel` writes `BotFacts`, `LadderFacts` and the readiness steps
(`readiness_words.py` → `step_rows`) into it by key, and shows or hides rows by venue (costs and liquidation
only on a venue with them) and the Readiness group only for a bot at rest. The words are the ones those
functions already built; the table only lays them out. What blocks Start (`readiness_words.py` → `item_lines`)
stays text above the table, with the platform's stop sign beside it, never a cell. The tree has no scroll bar and
is as tall as its rows, so the panel scrolls once; a row's height is asked of its wrapped text because
`QTreeView` sizes a row from one line. The kind editor's read-only *Margin mode* and *Liquidation (est.)* rows
stay in the editor (`grid_exposure_fields.py` → `ExposureFields`): the second is a live estimate of the plan
being edited, not a recorded figure.

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
| The Grid page is retired and the Grid reads the outcome through the workbench instead of `GridBacktestResult` | `bots/ui/` | `EPIC-040F` |
| The strategy kind, a second `IBotKind` | its own `bots/application/kinds/<kind>/` | `EPIC-040G` |
| A halt that leaves the position under a standing stop (D10) and the custody of that stop (D13) | `bots/application/services/positions/` | `EPIC-039L`, deferred from C3 |
| `run --resume-halted` | `operations/`, `bots/application/use_cases/` | `EPIC-042E` |
