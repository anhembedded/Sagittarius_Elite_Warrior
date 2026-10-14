Status: Current

# `bots` — the module that runs, supervises and backtests bots

**Reader:** someone changing a bot kind, the bot shell, or what the host does with bots.
**Question it answers:** *which bots exist, what is each one doing, and how does it stay correct
across a start, a fill, a stop and a restart?*

This is a **skeleton** (`EPIC-041A`). Each view below is one paragraph of what exists at
`master-warrior`, with the code it comes from, and a `Filled by:` line naming the task that completes
it. Every `EPIC-040` child that changes a view completes it through its "Docs touched" section. The
template and its rules are in [`README.md`](README.md). The design records behind this module are
[ADR 029 §3](../../Tasks/epics/EPIC-029_bots_tab_grid_fast_track/DECISION_2026-10-03_bots_module_and_grid_bot.md)
(lifecycle, level lifecycle, reconciliation, sliced market orders),
[design 038](../../Tasks/epics/EPIC-038_headless_operation/DESIGN_2026-10-09_headless_operation.md)
(headless host) and [design 039](../../Tasks/epics/EPIC-039_futures_venue_profile/DESIGN_2026-10-10_futures_venue_profile.md)
(Futures). Paths below are from the repository root.

## 1. Context

`src/modules/bots/module.py:200` declares `dependencies = ["trading", "market_data"]`; orders reach the
venue only through `trading/contracts/`. The shell imports nothing from the module but `module.py`
(`src/shell/modules.py:43`, the only `modules.bots` import under `src/shell/`). The `operations` module
hosts the headless `run` and talks to bots through `bots/contracts/` alone
(`src/modules/operations/application/host_steps.py:33-44`). The command-line verbs are
`list`, `show`, `apply` and `export` of a plan (`src/modules/bots/cli/bot_verbs.py:82-87`). `alerting`
does not consume bot events yet: its docstring says `EPIC-036B` brings those sources
(`src/modules/alerting/module.py:3-6`).

Filled by: EPIC-041E.

## 2. Components

`BotRunner` (`src/modules/bots/application/services/lifecycle/bot_runner.py`) takes a command from a use case
and hands it to `BotExecutors` (`.../bot_executors.py:25`), which holds one executor per bot. For the
Grid kind that is `GridExecutor` (`.../grid_executor.py:125`), built by `GridExecutorFactory`
(`.../grid_executor_factory.py`) with a `BotOrderGateway` (`.../bot_order_gateway.py:112`), the
bot's one way to `trading`. Exchange events arrive at `BotEventRouter`
(`src/modules/bots/application/event_handlers/bot_event_router.py:82`), which finds the executor that
owns the client order id and gives the fill to its `GridFacts` (`.../grid_facts.py:136`). A bot's
state has one writer, `BotRunState` (`.../bot_run_state.py:54`), and is stored through `IBotStore`,
implemented by `JsonBotStore` (`src/modules/bots/adapters/persistence/json_bot_store.py:44`). A new
kind plugs in through one seam, `IBotKind` (`src/modules/bots/contracts/i_bot_kind.py:42`): `kind_id`,
`supported_profiles`, `validate`, `overlay` and `executor_factory`. A Grid's `overlay` (`domain/grid/grid_overlay.py`) draws one label per price: a range limit equal to a level's price is part of that level's label ("L6 · range top"), else its own "range top"/"range bottom" line, and SL/TP keep their own roles and styles (`BUG-207`). The backtest-side components
change in `EPIC-040B` (one kind-neutral result and simulator port); the strategy kind is a second
`IBotKind` in `EPIC-040G`.

**Where the code lives.** The application services are split first by kind, then by feature
(`BOT-177`). A path written `.../name.py` above is the file of that name in one of these
packages. Under `src/modules/bots/application/`:

- `services/` is the shell every bot kind shares, and nothing sits loose in it:
  - `lifecycle/`: the runner, run state, executors registry, command gate and lock, restore and boot recovery, lookup, the read-only runner and store, the notifying store, the kind catalog and the health contributor.
  - `orders/`: the order gateway, order history and outcome, order flags (Spot and Futures), the order-session opening and applied fills.
  - `venue/`: what the venue allows and costs: facts, needs, profiles, rules and the settings gates, symbol brackets and status, the Futures rules and start checks, the mark source, account and funding views, exchange terms.
  - `positions/`: exposure books and checks, closers, opening strategies and cost models, each Spot/Futures pair side by side.
  - `risk/`: the risk guards and risk reads.
  - `readiness/`: the readiness reader and assessment, resume readiness, the progress reader and run facts.
  - `watches/`: the price, user-stream and sleep watches, the clock-gap detector, the wake-exit check and streamed fine klines.
- `kinds/grid/` is everything that knows the Grid; a second kind gets its own `kinds/<kind>/` beside it:
  - the package itself: the executor and its factory, facts, ladder placer, run context, runtime codec, task guard, budgets, exposures, housekeeping, parking, margin mode, order failure, earlier runs, reference price, ladder needs, off-ladder orders, planner numbers and the Futures backtest terms.
  - `start/`: start preconditions, the start sequence and the interrupted start.
  - `stop/`: the stopper, stop sequence, request, retry and waiting, exit slices and the mark exit.
  - `watch/`: the range, risk, storage, terms and key watches, price age and reaction, the rate-limit pause, stream gap and tick extremes.
  - `recovery/`: the reconciler (with the missed fills it applies and the quantities it aligns, in their own files), the recovery reader and the resume sequence.

The shell does not import a kind. Today's exceptions, files of the shell that still import Grid types, are
listed in `tests/unit/architecture/baseline_bots_shell_imports_a_kind.txt` and the list only shrinks
(`tests/unit/architecture/test_bots_services_stay_grouped.py`).

Filled by: EPIC-040B (backtest components), EPIC-040G (strategy kind), EPIC-041E (the rest).

## 3. State machines

Two tables, both declared as data. The bot lifecycle,
`src/modules/bots/domain/bot_lifecycle_fsm_matrix.py:39-180`, has nine states (`DRAFT`, `STARTING`,
`RUNNING`, `PAUSED`, `RECOVERING`, `HALTED`, `STOPPING`, `STOPPED`, `ERROR`) and fifteen events. The
table declares `resume` from `PAUSED` (to `RUNNING`, `:125`), from `HALTED` (to `STARTING`, `:143`) and,
since `BUG-204`, from `RECOVERING` (to `RECOVERING`, `:135`: a self-loop, because the next state is the
reconcile's to decide). A `RECOVERING` bot leaves it by `reconcile_ok`, which returns to the state it
came from (`:137`, `PRIOR`), by `reconcile_mismatch`, `halt`, `fault` or `stop`; the reconcile runs when
the venue's order session opens, which the owner's Resume now asks for. A restart
turns `RUNNING` and `PAUSED` into `RECOVERING` and `STARTING` into `HALTED`
(`src/modules/bots/application/services/lifecycle/bot_restore_service.py`). Each Grid level has its own machine
in `src/modules/bots/domain/grid/grid_level_fsm_matrix.py:28-80`: five states (`EMPTY`, `PLACING`,
`RESTING`, `PARTIAL`, `FILLED`) and seven events. Design: ADR 029 §3.1 and §3.2. By decision D4 these
tables become generated diagrams with a drift test, in the task that fills this view.

Filled by: EPIC-041E.

## 4. Sequences

**Start.** The use case (`src/modules/bots/application/use_cases/start_bot/handler.py:78-111`) refuses
a closed venue, an unconfirmed Mainnet start and an unready bot, then asks the runner to start. The
Grid's preconditions (`.../grid_start_preconditions.py:78-127`) re-read the parameters, claim the
symbol, open the order session (`order_session_refusal`, `:114`) and register the owner budget. The
executor then plans and places the ladder (`.../grid_executor.py:253-271`,
`.../grid_start_sequence.py:75-108`), and `ladder_ready` moves the bot to `RUNNING`. **Fill.** The
router (`bot_event_router.py:89-103`) gives the fill to `GridFacts`, which ignores one already counted
and books the rest on the bot's worker (`grid_facts.py:190-232`). **Stop.** The use case
(`.../stop_bot/handler.py:51-61`) goes through `GridStopper` (`.../grid_stopper.py:72`) to
`GridStopSequence` (`.../grid_stop_sequence.py:94`), which cancels the bot's tagged orders and settles
the exposure. **Restart.** `BotRestoreService` applies `app_restart` to every saved bot,
`BotBootRecovery` pays cancels a crash left owing, and `GridReconciler` compares a `RECOVERING` bot
with the exchange (`.../grid_reconciler.py:134`, `run`), and only once the venue's order session is
open: until then nothing listens to the exchange and the Orders panel shows the ladder as saved, with
a note saying so. The reconcile also brings each saved order's quantity level with the exchange's, **before**
it applies any missed fill (`recovery/grid_order_quantities.py`, `adopt_exchange_quantities`;
`BUG-205`): from the open-order list, or from history for an order that is gone. A smaller
quantity is adopted and logged `[order-quantity]`; a larger one halts the bot
(`order_quantity_mismatch`). A new order is saved at the quantity the exchange accepted, never
the one asked for. **Resume from `RECOVERING`** (`BUG-204`, the desktop's way out): the use case asks
for the real-money answer on a mainnet venue, `BotRunner.resume` (`.../bot_runner.py:89`) opens the
session (`open_session_for_resume`, `.../grid_start_preconditions.py:72`) or refuses in the session's
words, and the executor reconciles (`.../grid_executor.py:285`, `GridFacts.reconcile_recovering`,
`.../grid_facts.py:276`): a fill the bot missed is booked once from the order history, its counter
order laid, an order missing from the book ended, and the bot returns to its prior state, or halts on
a mismatch. The prior state is data on the screen's side: `Bot.lifecycle.recovering_from` travels on
`BotSnapshot.recovering_from`, so the state line of a `RECOVERING` bot says where the reconcile returns
it (`bot_facts.py`, `BUG-206`). A bot the owner had paused returns to `PAUSED` with the reason
`restored_paused` (`GridReconciler.run`), which the state line shows until the next Resume clears it,
so the second press is explained on screen and not only in the `[recovering-resume]` log line. A deliberate action that trades opens the order session in one place,
`order_session_opening.py:1-59`, with exactly three callers: Start, a Resume from `HALTED` or
`RECOVERING`, and the headless `run --resume-recovering`
(`.../grid_start_preconditions.py:72,114` and `.../resume_recovering_for_host/handler.py:81`). Design:
ADR 029 §3.3 and §3.4, design 038 §5, design 039 §9.

Filled by: EPIC-041E.

## 5. Data model

A bot is an aggregate: a `BotDefinition` (name, kind, venue, symbol and a string-valued `config`) and a
`BotLifecycle` (state, run start, the state it is recovering from), `src/modules/bots/domain/bot.py:57-88`.
The store port is `src/modules/bots/contracts/i_bot_store.py:32`, which hands out a `StoredBot`.
A Grid's parameters are `GridParams` (`.../domain/grid/grid_params.py:127`) and what it has done so far
is `GridRuntime`, with one `LevelOrder` per level (`.../domain/grid/grid_runtime.py:130-194`). The plan a
user applies from a file is `AppliedPlan` (`src/modules/bots/contracts/applied_plan.py:36`). Each bot is
one file, `state/bots/<id>.json`, under the data root (`src/modules/bots/composition/state_bindings.py:75-79`),
written atomically by `JsonBotStore`.

Filled by: EPIC-040C (the sandbox copy of a plan), EPIC-040G (the strategy bot's config), EPIC-041E (the rest).

## 6. Threading and deployment

Each bot has its own worker thread and FIFO queue, so one slow bot never delays another
(`src/modules/bots/adapters/thread_bot_work_queue.py:29-36`, one queue per bot from the factory
`queues` argument, `src/modules/bots/composition/executor_bindings.py:235`). Periodic checks run on
`ThreadBotTicker` (`src/modules/bots/adapters/thread_bot_ticker.py`): one ticker, named `bots-ticker`
(`executor_bindings.py:209`), with a daemon thread per task. A second process on the same data root is
read-only: `boot()` returns before restoring any bot or subscribing to fills
(`src/modules/bots/module.py:222-226`), because a restart rule run there would rewrite the first
copy's running bots (`EPIC-035H`). Design: design 038 §5.2 (`status` from a second process).

Filled by: EPIC-041E.

## 7. Timing

The constants that decide when a bot waits, retries, pauses or halts:

| What | Value | Where |
| :--- | :--- | :--- |
| Price is stale after; grace at start | 60 s; 60 s | `src/modules/bots/domain/grid/price_freshness.py:23-24` |
| A reference price older than this is refused | 10 s | `src/modules/bots/domain/grid/reference_price.py:22` |
| Every bot's feed is checked every | 5 s | `src/modules/bots/application/services/watches/bot_price_watch.py:80` |
| Order pacer default caps: open orders, spacing, orders per minute | 100; 250 ms; 60 | `src/modules/trading/contracts/owner_budget.py:122-127` |
| User stream down for this long halts; reconciled every; checked every | 120 s; 300 s; 15 s | `src/modules/bots/application/services/watches/user_stream_watch.py:70-76` |
| Sleep: heartbeat; a gap over this is a sleep; fresh-price attempts and spacing | 15 s; 60 s; 4 × 15 s | `src/modules/bots/application/services/watches/sleep_watch.py:60-66` |
| Wait before each automatic retry of a stop | 10, 30, 60, 120, 300 s | `src/modules/bots/application/kinds/grid/stop/grid_stop_retry.py:53-59` |
| Rate-limit pause: margin, longest wait, most automatic resumes | 2 s; 1 h; 5 | `src/modules/bots/domain/grid/rate_limit_pause.py:21-23` |
| Futures funding interval assumed | 8 h | `src/modules/bots/domain/bot_kind_inputs.py:113` |

By decision D4 this table becomes generated from the constants, in the task that fills this view.

Filled by: EPIC-041E.
