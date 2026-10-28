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
(`.../bot_order_gateway.py` → `BotOrderGateway`), the bot's one way to `trading`; the requests it sends
are built by `BotOrderRequests` (`.../bot_order_requests.py` → `BotOrderRequests`): a placement, or an
exit sent as a close that trading judges by the inventory or exposure (`BUG-241`). Every call to an
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
`kind_id`, `supported_profiles`, `validate`, `overlay` and `executor_factory`, and three concrete methods that no implementer is forced to override: `recovery_layer`, `backtester` (since `EPIC-040B`, below) and, since `EPIC-045B`, `exposure_left` (what a bot at rest still holds according to its record, so `bot delete` on the running host can refuse; closed by default for a bot that ran; the Grid answers in `bots/domain/grid/grid_exposure_left.py` → `grid_exposure_left`) and, since `EPIC-038L`, `parameter_problem` (whether the parameters a `bot edit` sets can be stored, judged without the exchange; closed by default, so a kind that declares nothing is edited by no command line; the Grid answers in `bots/domain/grid/grid_parameter_check.py` → `grid_parameter_problem`, through `GridParams.from_config`). The shell finds a kind
by its id through `IBotKindCatalog` (`bots/contracts/i_bot_kind_catalog.py` → `IBotKindCatalog`),
implemented by `BotKindCatalog` (`.../bot_kind_catalog.py` → `BotKindCatalog`); the Grid is
`GridKind` (`bots/domain/grid/grid_kind.py` → `GridKind`). A Grid's `overlay`
(`bots/domain/grid/grid_overlay.py`) draws one label per price: a range limit equal to a level's
price is part of that level's label ("L6 · range top"), else its own "range top"/"range bottom" line,
and SL/TP keep their own roles and styles (`BUG-207`). A plan with a trigger price adds one
`OverlayRole.TRIGGER` line, "Trigger ≤ T" (≥ for a SHORT), dash-dot in a colour no other line has;
the Bots screen leaves it out once the bot has laid its ladder
(`bots/ui/bots_screen/plan_trigger_line.py` → `shown_for`, `TRIGGER_LATCHED_STATES`, `RESUMED_BY_WHAT_IT_HOLDS`: a halted bot keeps the line only while its record holds nothing; `EPIC-046B`).

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
`bots/domain/grid/grid_figures.py` → `grid_figures`, `grid_notes`, which the workbench draws: the Grid
has no page of its own (`EPIC-040F`). Its provenance and the period asked for are the neutral
`BacktestProvenance` and `DataWindow`, not a copy. `GridKind` is given its adapter where it is built
(`bots/composition/executor_bindings.py` → `_build_kind_catalog`). No file of the outcome, the port
or `IBotKind` imports a kind (`tests/unit/architecture/test_backtest_outcome_is_kind_neutral.py`).
**A replay that waits for its range (`EPIC-044D`).** `bots/domain/grid/waiting_replay.py` → `engine_starting_at` builds the venue's engine itself when the window's first candle opens inside the range, and a `WaitingReplay` over it when it does not: the capital in cash, equity and the buy-and-hold benchmark flat, the candles that reach the range walked second by second, and the venue's own `ReplayEngine` (Spot or Futures, built through the same factory) created at the close of the first step that is inside (`range_position`, the live entry's definition), dated at that step's end (`PriceStep.end`), so it plans and opens there and nothing earlier in the entry candle (a funding settlement, an extreme) reaches it and its ladder rests from the next step; `GridBacktestResult.waited_for_range` and `range_entry` carry it and `grid_figures.py` → `grid_notes` says it, including that a position venue judges the entry on the trade close because the replay has no mark-price history. `PriceStep.close` is what is judged.
**The workbench that draws it (`EPIC-040D`).** `bots/ui/backtest_workbench/backtest_workbench.py` →
`BacktestWorkbench`, built from `WorkbenchPorts`, is one page for every kind: the interval (the charts' own `ChartToolbar`, offering every interval the bot's market loads and the replay judges: `interval_toolbar.py` → `OFFERED_INTERVALS`, all but `UNREPLAYED_INTERVALS` (3d, 1w, 1M: their candles open off the epoch-aligned grid the replay counts expected candles and 1-second windows by, until it takes bar ends from the venue's calendar); `BacktestWorkbenchView.offer_intervals_of` → `ChartToolbar.set_market`, so a Futures bot has no `1s`, `BOT-232`; a period over `MAX_CANDLES` is refused) and the period, Run, Cancel (Stop while a sync runs), Sync candles and Run without funding, the sandbox's
editor (in the same `PlanColumn` as the Live Plan, `BOT-218`), the replay chart, which before any run draws the stored candles of the period (`BOT-233`: `candle_drawing.py` → `CandleDrawing` over `candle_preview.py` → `CandlePreview`, which reads `get_stored_candles/` → `GetStoredCandlesQuery` off the UI thread under its own fence; `BotChart.say_empty` replaces the plot with a sentence when there is nothing to draw; a result holds the chart until the next run; `sync_offer.py` → `sync_plan` says what Sync candles fetches and whether a run follows) and then the result (`BotChart` with the kind's `IBotKind.overlay` plus the outcome's fills,
`outcome_view.py` → `result_overlay`), the equity against buy and hold (`equity_pane.py` →
`EquityPane`), the figures read-out and the fills table. The replay chart reads in the application's display time zone and offers its drop-down (`BOT-205`; `WorkbenchPorts.display_timezone`), like the Live chart it will sit beside; the equity pane's time axis follows the same setting (`BUG-243`; `equity_pane.py` → `EquityPane.follow_display_timezone`), without a drop-down of its own. It names no kind: it asks the catalog for the
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
the centre's Backtest tab (`EPIC-040E`, below), as it does for the Grid, whose own page `EPIC-040F` deleted. Nothing in the
package imports a kind (`test_backtest_outcome_is_kind_neutral.py`) or a command, an order or an
account reader (`test_backtest_workbench_reaches_no_order_or_account.py`). The picture is
[`diagrams/06-backtest-run.puml`](diagrams/06-backtest-run.puml) in [`06-runtime.md`](06-runtime.md).

**The Bots screen hosts it (`EPIC-040E`).** The centre of the Bots mode is a stock `QTabWidget`
(`bots/ui/bots_screen/bots_view.py` → `BotsView.centre`): **Live**, the selected bot's chart, and
**Backtest**, the workbench; the bottom docks are Orders, Ladder, Fills and Log. The Plan is the Live tab's own pane,
a splitter with the chart on its right (`BotsView.live`), and the Backtest tab's setup column is the same class on the left of its
results: `bots/ui/bots_screen/plan_column.py` → `PlanColumn`, one scroll holding a status banner, what sits under it, the figures, the
kind's editor and the checks list (`BOT-218`). The Plan fills it with the real bot's name, venue and figures; the workbench fills it
with the sandbox's source line as the banner, its question about discarding edits and the verdicts as the checks, with an editor of
its own, so the Backtest tab shows none of the Live Plan. A layout saved while the Plan or the Strategies panel was a dock restores without them. Arming a strategy has no panel (`BOT-219`): `bots/ui/strategies/venue_strategies.py` → `VenueStrategies` holds the two commands, Arm strategy… asking what and on which venue in `arm_strategy_dialog.py` → `ArmStrategyDialog` (which lists what is armed) and Disarm strategy… asking which armed venue in `disarm_choice.py` → `venue_chooser`, and each `ArmedStrategyChangedEvent` is told in the Bots channel of the Output pane (`BotsView.output_log`). The tab's content is
`bots/ui/bots_screen/backtest_workbenches.py` → `BacktestWorkbenches`: one workbench per venue,
built when a bot of that venue first needs it and kept (its chart and sync read that venue's market,
`BUG-172`, and a sandbox with edits survives the selection moving to another venue, so the question
about discarding them is asked where they are), followed with the selected bot, its planner market
and its risk facts (`DetailEffects.refresh`). A bot whose kind has no `backtester()`, or whose
venue the kind's `supported_profiles()` leaves out, turns the tab off with its reason as the tooltip
(`BotsView.set_backtest_available`, `TabAvailability`): disabled, never hidden. View → Live chart tab
and View → Backtest tab (Ctrl+J) switch the tabs (`bots_command_binding.py`); the second follows the
tab. View → Chart (`EPIC-040` F1) holds the chart commands (`chart_commands`) for the chart in front, kept in step by one
`ChartCommandMirror` (`bots_chart_commands.py` → `BotsChartCommands`, parented to the view model by `bind_bots_commands`):
on the Live tab the selected bot's chart (More timeframes…, zoom, Follow latest), on the Backtest tab the workbench's
interval row (More timeframes… only), and every command off while a tab shows a note. It re-follows on
`BotsView.front_chart_changed`, which the tab, the chart slot and the page slot raise. The workbench's result chart has
no timeframe row of its own (`ChartToolbar.hide_timeframes`, F3: the replay is at the interval that was run), and the
interval picker keeps the chosen interval pinned (`CurrentStaysPinned`, F4: choosing pins it, the dialog refuses to unpin it and says why, so the row always shows what Run replays). A window state saved with the old Backtest dock still loads: Qt skips a dock name the window no
longer has. A run in flight when the selection moves to a bot of another venue keeps running on its
hidden workbench (it is that bot's run, and the hidden page stays a child of the tab, never a window of its own: `widget_slot.replace_in`, `BUG-242`); its result is there when the person comes back, and a run
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
    symbol brackets and status, the Futures rules and start checks, the mark source, the funding
    view, exchange terms (the account view is a contract, `bots/contracts/account_view.py`).
  - `positions/`: exposure books and checks, closers, opening strategies and cost models, each
    Spot/Futures pair side by side.
  - `risk/`: the risk guards and risk reads.
  - `readiness/`: the readiness reader and assessment, resume readiness, the progress reader and run
    facts (`BotRunFactsReader`, `run_facts_for`).
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

## Built: the Bots screen's doors (EPIC-048B)

The Bots screen reaches the application through the dispatcher, the bus and the allowlist of
`architecture-rule.md` §3.1, and holds no application internal, no adapter and no venue port. What
it used to compute or read itself is three queries and a command:

- `bots/application/queries/get_bot_run_facts/handler.py` → `GetBotRunFactsQueryHandler` answers the
  host's Run facts of one bot (`bots/contracts/run_facts.py` → `BotRunFacts`): whether the venue is on
  and trades the bot's market, who else holds the symbol's lease, which bots hold the symbol, fill the
  venue or wait to recover on it (`.../lifecycle/other_active_bot.py` → `occupancy_of`, over the store
  in the list's order, `list_bots/handler.py` → `listed`), and the owner budget caps. The budget itself is
  not judged there: it is the parameters on screen.
- `bots/application/queries/assess_bot/handler.py` → `AssessBotQueryHandler` is the pure assessment the
  screen judges with (`EPIC-048` D5): `assess_readiness` for a bot at rest, with the budget judged from
  the parameters on screen against the carried caps (`.../readiness/bot_run_facts.py` → `run_facts_for`),
  `assess_resume` for a bot that proposes a Resume, and the parameter verdicts. It reads nothing, so it is
  answered where the screen runs. While the Run facts are not read and nothing else is left, it adds
  one waiting item (`RUN_FACTS_READING`) instead of judging a Start against facts nobody has read.
  The screen reads the Run facts off the UI thread and holds them (`bots/ui/bots_screen/run_facts_check.py`
  → `RunFactsCheck`).

- `bots/application/queries/get_venue_choices/handler.py` → `GetVenueChoicesQueryHandler` answers the
  venues a bot may be on, each with its connection words (`bots/contracts/venue_choice.py` →
  `VenueChoices`, `VenueChoice`, `KEY_SAVED`, `NO_KEY`, `NOT_ENABLED`): whether a saved API key exists,
  never the key. New bot and the Plan's Venue field offer what the screen holds
  (`bots/ui/bots_screen/bot_venues.py` → `BotVenues`); `venue_choice.py` keeps only the combo box row
  (`add_venue_choice`).
- `bots/application/use_cases/export_bot_plan_to_file/handler.py` → `ExportBotPlanToFileCommandHandler`
  writes the plan of the chosen bots to a new file through `bots/contracts/i_plan_file_writer.py` →
  `IPlanFileWriter`, and answers `PlanFileExported` or `PlanFileNotExported` (`exists`, `os_error`,
  `unknown_bots`, the ids checked before the query runs). `bot export` dispatches the same command.
- The selected bot's tables quote prices in the tick and step sizes the planner read
  (`PlannerMarket.terms`), kept per venue and symbol (`bots/ui/bots_screen/selected_bot_precisions.py` →
  `SelectedBotPrecisions`), not in a venue's metadata cache.

`bots/ui/bots_screen/bot_detail.py` → `detail_for` takes the assessment as its door (`Assess`) and keeps
the presentation: figures, checks, availability, overlay, ladder. The values both sides hold are
published with the contracts: `bots/contracts/connection_read.py` → `ConnectionRead`; the Run
step's facts, `bots/contracts/run_facts.py` → `RunFacts`; the account view,
`bots/contracts/account_view.py` → `account_view_of`; the words of
`bots/contracts/connect_failure_words.py` → `failure_cause`, `state_words`; and
`bots/contracts/bot_readiness.py` → `MARKET_NOT_READ`.

## Built: the remote backend of the Bots screen (EPIC-047E)

The VPS Bots tab shows another host's bots through the doors above, with a second dispatcher behind the same
screen. The parts, from the screen outward:

- `bots/adapters/remote_host/remote_command_dispatcher.py` → `RemoteCommandDispatcher` is an `ICommandDispatcher`.
  A query is answered from what the host last published, even while the link is down; a command is turned into
  the host's request and sent through `IHostControl`; `AssessBotQuery` runs on the local dispatcher, as it reads
  nothing. A command while the link is down is refused in words and not sent
  (`DISCONNECTED_WORDS`), and so is a command on a bot whose earlier command was lost with the link
  (`bots/contracts/i_unanswered_commands.py` → `IUnansweredCommands`, kept by `shell/vps_link/unanswered_ledger.py` →
  `UnansweredLedger` until the host's audit settles it), because a second press would apply the first twice (Stop and Pause, which only reduce exposure, pass both this block and the one-command-at-a-time claim); a query or command the tab does not offer raises
  `remote_requests.py` → `NotOfferedInVpsTabError`.
- `bots/adapters/remote_host/remote_queries.py` → `RemoteQueries` answers the nine queries the screen asks
  from one `HostWorld` (`bots/contracts/host_world.py`, the port `i_host_world.py` → `IHostWorld`). Where a
  handler judged host facts, the judgement is that handler's own pure function, called with the published facts:
  `bots/application/queries/get_venue_choices/handler.py` → `venue_choices_of`;
  `bots/application/queries/get_plan_risk_facts/handler.py` → `plan_risk_of`;
  `bots/application/services/readiness/bot_run_facts.py` → `host_run_facts` and `venue_problem_of`.
  A fact the host never published is `NOT_PUBLISHED_BY_THE_HOST` in the field the screen already shows a problem
  in; the Run facts, which have no honest default, fail the read (`NotPublishedError`) and Start keeps waiting.
- `bots/adapters/remote_host/remote_connection.py` → `connection_of` puts the Connect step's
  `VenueAccountSnapshot` together from the bot's exchange facts, the planner's inputs and the symbol's rules, each
  with the moment the host read it; with any of them missing it is a `ConnectFailure`, never a snapshot of defaults.
- `bots/adapters/remote_host/remote_requests.py` → `request_of`, `result_of`, `proposal_in` turn each command of
  the screen into the request the `bot` verb of the same name sends (the parity table of `EPIC-045D` is checked
  against it), and the host's reply into the screen's `BotCommandResult` in the host's own words. A Start that
  carries unsaved edits and a rename are refused with the words to save first: two requests cannot keep the
  in-process Start's "saved only if the bot is ready".

The link side is in `shell/` because it needs the transport: `shell/vps_link/link_host_world.py` →
`LinkHostWorld` (an `ILinkObserver` and the `IHostWorld`: snapshot at each welcome, events through the connection's
revision gate), `link_host_control.py` → `LinkHostControl` (the `IHostControl`, one request id per command, never
resent; a lost command is `NO_ANSWER` and is listed in `unanswered`), `host_event_publisher.py` →
`HostEventPublisher` (`BotChangedEvent` and `MarketTickEvent` on the tab's own bus, forming candles only while the
host's market file is live), `host_candle_feed.py` → `HostCandleFeed` (an `ICandleFeed` over the bridge's `candles`
call; its `sync` does nothing) and `host_state_line.py` → `host_state_line` (host, keys, connected or "data as of",
age). A guard keeps the closure of these files free of any Binance client
(`tests/unit/architecture/test_the_vps_tab_reaches_no_binance_client.py`).

## Built: the VPS Bots tab (EPIC-047E PR 2)

The tab is the Bots screen's own `BotsView` and `BotsPresenter`, built a second time over the host's link; no class of the
screen is copied or subclassed (`tests/unit/architecture/test_the_vps_tab_is_the_bots_screen.py`).

- `bots/ui/bots_screen/bots_dependencies.py` → `BotsBackend` is what differs between the two tabs as one value: the
  doors (`BotsDependencies`), how the strategy commands are made, what the tab arranges in its view, and the binder its
  commands go through. `backend_for(container)` builds this computer's; with an `IVpsTab` in the container it builds the
  VPS tab's from `vps_backend.py` → `vps_dependencies`, `vps_arrangement`, `vps_binder`.
- `bots/contracts/i_vps_tab.py` → `IVpsTab` is the port the shell fills: the screen's dispatcher over the link, a candle
  feed per venue, the line above the tab (`host_line.py` → `HostLine`) and `opened()`, called when the tab is first shown.
  It is on the UI-doors allowlist (`architecture-rule.md` §3.1).
- What the tab turns off, with its reason, never hidden: New bot (`bots_view_model.py` → `new_bot_unavailable`; its symbol
  list is the exchange's) and the Backtest tab (`backtest_workbenches.py` → `WorkbenchUnavailableError`; it replays
  candles from Binance). `host_line_bar.py` → `HostLineBar` shows the honest line, asking again every second.
- The real-money question is typed: `typed_venue_consent.py` → `TypedVenueConsent` asks every time for a mainnet venue,
  with `typed_venue_dialog.py` → `TypedVenueDialog`; a testnet is never asked and nothing is remembered.
- Commands: `vps_command_ids.py` → `vps_commands` contributes the Bots commands under the `bots.vps` prefix and
  `PrefixedBinder` binds the screen's own ids through it, so a command added to the Bots tab is in the VPS tab by itself.
- The shell owns the rest (`shell/vps_tab/`): `vps_tab_screen.py` (the contribution, route `vps_bots`, item 19),
  `vps_tab_builder.py` (the Bots presenter over a `VpsContainer` that answers the tab's private bus, the session and no local
  venue), `vps_tab_session.py` → `VpsTabSession` (the supervised link, started on the first show, stopped at quit).

## Built: the types that cross the remote link (EPIC-047A)

`bots` declares which of its contract types the remote link may carry, and nothing else crosses.
`bots/composition/wire_roots.py` → `BOTS_WIRE_ROOTS` is the one list: each entry is a wire name
(`sew.bot-snapshot/1`) and a root type, 15 in all in `bots` (the results of the queries the Bots screen reads, the
venues a bot may be on included (`EPIC-048B`), the bot, a command's result, the host-control request and reply); `bots/link.py` → `wire_roots` hands it
to the shell (`EPIC-047C` moved it from `module.py`, which loads the whole module; `operations/link.py` hands over the host-facts
document, the fifteenth root). The codec itself is `support/wire` and imports no module. A root is added by one entry here
and one contract test (`tests/unit/support/wire/contract/`).

A union member crosses with its own wire name, kept on the record: `@wire_name` (`core/contracts/wire_name.py`
→ `wire_name`) on `bots/contracts/exchange_facts.py` → `ExchangeChecking`, `ExchangeUnavailable`,
`ExchangeLoaded`, on `bots/contracts/futures_facts.py` → `FuturesLoaded`, on
`bots/contracts/plan_risk_read.py` → `PlanRiskUnavailable`, on `bots/domain/bot_kind_inputs.py` →
`PlanRiskFacts`, and on trading's `ConnectFailure` and `VenueAccountSnapshot`. Moving a class changes no
name; changing a name is a version change. `BotAssessment` and `AssessBotQuery` do not cross (the pure
assessment runs on the desktop, `EPIC-047` D1), and `BotStatusReport` is read by the command line only.

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
distances from a `BotSnapshot` alone (the parameters it carries read now, its saved run: the saved ones for `bot show`, the design on screen for the Bots tab, which says "Not saved" then), calling
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
functions already built; the table only lays them out. What blocks Start is not in the table: it is the status
banner (below). The tree has no scroll bar and
is as tall as its rows, so the panel scrolls once; a row's height is asked of its wrapped text because
`QTreeView` sizes a row from one line. The kind editor's read-only *Margin mode* and *Liquidation (est.)* rows
stay in the editor (`grid_exposure_fields.py` → `ExposureFields`): the second is a live estimate of the plan
being edited, not a recorded figure.

Two Plan rows are estimates of a straight run (`BOT-235`): *Loss at stop loss (estimate)* and *Result at take profit
(estimate)*. The numbers are `bots/domain/grid/grid_exit_estimate.py` → `exit_estimates_for`, `estimate_exits`,
`ExitEstimates`: the plan a Start would place (`grid_evaluation.py` → `entry_plan`, the one place that sizes and
prices it) run from its last price to the exit on `grid_position_model.py` → `PositionBook`, the book the Futures
replay books its fills with, with `FuturesReplay`'s fee rule (taker on the opening and the closing trade, maker on
the ladder fills); funding and slippage are left out. `bot_detail.py` → `detail_for` asks for them for a Grid at rest
whose market numbers are read, `ui/bots_screen/exit_estimate_words.py` → `exit_rows` writes the amount, its share of
the capital and the path assumed into `BotFacts.loss_at_stop` and `gain_at_take_profit`, and a row with no text (an
exit off, a bot with a run, no plan) is hidden, and a row whose exit the guard refused as beyond the liquidation
price (`STOP_LOSS_AFTER_LIQUIDATION`) says so instead of a figure (`rows_cut_by_liquidation`). A bot at rest also shows the plan guard's liquidation estimate in
the *Liquidation price* row, as a design not saved yet does (`BUG-261`); only a bot with a run reads the exchange's.

**A figure and a state read by their meaning, never by colour alone (`EPIC-043C`).** A profit, a loss or a change is
a `signed_key` column or row (`support/ui_kit/value_formatter.py` → `signed_key`): the formatter writes an arrow and
a sign (`▲ +12.50`, `▼ -9.00`), and the tone comes from the meaning table's colour on the application's palette.
In a table that is `support/ui_kit/table_model.py` → `RowTableModel._tone`, which `bots_table_models.py` →
`BotsTableModel` (grid profit, total PnL, state) and `BotLadderTableModel` (gross, net step, net per cycle) answer; in
the Plan dock's property table it is the tone a cell names in `support/ui_kit/tone_delegate.py` → `TONE_ROLE`, which
`row_kind_delegate.py` → `RowKindDelegate` paints, given by `bot_facts.py` → `BotFacts.tones` and
`bot_ladder_facts.py` → `LadderFacts.tones` from the sign of each figure. A bot's lifecycle state is a word, an icon
and a tone from two complete tables in `bot_state_looks.py` → `STATE_WORDS`, `STATE_LOOKS` (the word was
`value.capitalize()`, which wrote `AWAITING_RECOVERY` as `Awaiting_recovery`): the Bots table puts the icon beside the
word (`BotsTableModel._role_data`, the decoration), the Plan dock's state line and the identity strip's connection are
a `support/ui_kit/state_badge.py` → `StateBadge`, and `connect_view.py` → `ConnectView.look` says the connection's
icon and tone. The banner's message takes the tone of its severity in `support/ui_kit/notice_bar.py` → `NoticeBar`; each check
takes the tone of its own in `plan_checks_view.py` → `PlanChecksView`.

**The Plan says where the bot stands once, and lists what the kind says as checks (`BOT-209`).** Top to
bottom for a bot at rest: the name and the state word, one status banner, the Venue field, the kind's editor, the
checks list, the property table; a bot with a run has its figures first and the checks last. The banner
(`plan_status_banner.py` → `PlanStatusBanner`, a `NoticeBar` from `support/ui_kit/notice_bar.py`, no button, since
what a person can do is a command of the Bots menu) is written by `plan_status.py` → `plan_status`: the first
thing left before Start with where to fix it (`readiness_words.py` → `item_sentence`) and a count of the others,
else *Connecting…*, else *Ready to start*; the exchange's notes and the run's last note (`bot_facts.py` →
`BotFacts.note`) are lines under it, and a bot with a run says how it ended or nothing. The kind's verdicts reach
the dock as `plan_checks.py` → `PlanChecks` (`plan_checks_of`): a refusal, then a warning, each `PlanCheck` with a
`title`, a one-line `headline` and the whole `detail`; every check that passed is counted. `plan_checks_view.py` →
`PlanChecksView` is the stock `QTreeView` that shows them: a row per check that needs attention, one folded row
"N checks passed" that opens to list the rest and stays as the person left it, the whole sentence as each row's
tooltip. The words are the kind's, written where the check is made: `domain/verdict.py` → `Verdict.title`
(`grid_constraints.py` → `GridConstraint.title`; for the Futures risk codes, in `futures_grid_checks.py` → `FUTURES_PLAN_TITLES`) and
`Verdict.summary` (`grid_advice.py` → `Advice.summary`, the one-line part of every advice). The hint under a
Grid field is that same `summary` (`grid_field_errors.py` → `FieldError`, laid out by `grid_field_hints.py` →
`FieldHints`), with a "Use N grids" button on the Grids field when the check names a count
(`Verdict.numbers["suggested_grids"]`); it is the same text as the list's row, and the long sentence is a tooltip
in both places. The two read-only rows of the editor (*Margin mode*, *Liquidation (est.)*) are rows of its form
as before.

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

**A Grid that waits for its range** (`EPIC-044B`): the state is `AWAITING_RANGE`; `bots/application/kinds/grid/watch/grid_range_entry.py` → `GridRangeEntry` decides on every price the exits are judged on (`waits_for_the_range` for the first Start, `on_price` while it waits), `GridPriceReaction` hands it the price and arms the range-exit close's one skipped beat, and the contract `bots/contracts/i_entry_readiness.py` → `IEntryReadiness` is what it asks of the Bots screen's readiness at the price that enters (`bots/application/services/readiness/bot_entry_readiness.py` → `BotEntryReadiness`, resolved lazily in `bots/composition/executor_bindings.py` because the readiness reader needs the kind catalogue these deps build). `bots/domain/bot_lifecycle_fsm_matrix.py` → `may_hold_exposure` is what the exposure watches ask instead of naming states.

**What shows a waiting Grid** (`EPIC-044C`): `GridPriceReaction._enter_if_waiting` keeps the price the bot hears as the run's last price while it waits (nothing else of the exits is watched), so every surface has a "now" to say; `bots/contracts/grid_ladder_texts.py` → `waiting_text` is the one sentence ("Waiting for the price to enter X–Y (last price Z, N s ago); nothing is placed until it does", the price with how long ago the bot heard it, since a waiting bot watches no stale-feed halt; for a plan with a trigger price, "Waiting for the price ≤ X within L–U (…)", ≥ for a SHORT, from `GridLadder.position.trigger` (`EPIC-046B`; `bots/contracts/grid_ladder.py` → `TriggerMark`)) the Plan's banner (`bots/ui/bots_screen/bot_facts.py` → `bot_facts`), `bot list` and `bot show` (`bots/cli/bot_waiting_reason.py` → `reason_cell`) and the heartbeat (`alerting/application/heartbeat_text.py`) print; `BotsHealthContributor` and the `[health]` line count `awaiting_range` apart from `running`; `bots/contracts/events/bot_range_entered_event.py` → `BotRangeEnteredEvent` is published once by `GridRangeEntry._tell_the_ladder_is_laid` when the ladder is laid, carrying the trigger price it met (`trigger`, `trigger_at_or_below`; `None` without one), and the alerting module turns it into one INFO alert.

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
  (`alerting/application/sources/account_alert_source.py` → `AccountAlertSource.on_account_loss_cap_tripped`).

## Planned

| Change | Where | Task |
| :--- | :--- | :--- |
| The strategy kind, a second `IBotKind` | its own `bots/application/kinds/<kind>/` | `EPIC-040G` |
| A halt that leaves the position under a standing stop (D10) and the custody of that stop (D13) | `bots/application/services/positions/` | `EPIC-039L`, deferred from C3 |
| `run --resume-halted` | `operations/`, `bots/application/use_cases/` | `EPIC-042E` |
