Status: Current

# `bots` — 3. Context

*What does the module depend on, who depends on it, and which commands, queries and events cross its
edge?*

**Built.** `bots/module.py` → `BotsModule.dependencies` declares `["trading", "market_data"]`: orders
reach the venue only through `trading/contracts/` (ADR 029 D1: `trading` stays the only module that
sends orders), and the bot chart and the price watch read `market_data`'s candle feed, its
`IMarketStream` (`src/modules/market_data/contracts/i_market_stream.py` → `IMarketStream`) and its
`MarketTickEvent`. `test_module_declarations.py` holds the list both ways, and the boundary guards
under `tests/unit/architecture/boundaries/` hold the direction (`architecture-rule.md` §3).

Two pictures: [`diagrams/03-context-in.puml`](diagrams/03-context-in.puml) (*who reaches into the
bots module, and through what?*) and [`diagrams/03-context-out.puml`](diagrams/03-context-out.puml)
(*what does a bot ask of other modules, and what does it hear back?*).

## In: who calls the module

- **The shell** imports nothing from the module but `module.py` (`src/shell/modules.py` → `MODULES`),
  the file's own docstring says so, and the boundary guards hold it.
- **`operations`** hosts the headless `run` and reads the bots through `bots/contracts/` alone: the
  plan the host starts from (`bots/contracts/i_bot_plan.py` → `IBotPlan`), the host's commands
  (`bots/contracts/host_bot_requests.py` → `StartBotForHostCommand`, `StopBotForHostCommand`,
  `ResumeRecoveringForHostCommand`) and the status report (`bots/contracts/bot_status_report.py` →
  `GetBotStatusReportQuery`, `BotStatusReport`), as `src/modules/operations/application/host_steps.py`
  shows.
- **`alerting`** reads `BotChangedEvent` (`bots/contracts/events/bot_changed_event.py` →
  `BotChangedEvent`), `BotStopGaveUpEvent` (`bots/contracts/events/bot_stop_gave_up_event.py` →
  `BotStopGaveUpEvent`) and the status report (`EPIC-036G`;
  [`../alerting/03-context.md`](../alerting/03-context.md)).
- **The command line** has `bot list`, `show`, `apply` and `export` of a plan
  (`bots/cli/bot_verbs.py` → `BOT_VERBS`), declared by `bots/module.py` → `BotsModule.declare_cli`.
  The host's health snapshot and pre-flight check come from `BotsModule.declare_operations`.

Writing a plan is shared by every bot kind and by two callers: the Bots mode's **Export plan…** (a
menu item and a toolbar button, one `QAction`: `bots_commands.py` → `EXPORT_PLAN`; the dialog and the
flow in `bots/ui/bots_screen/export_plan_dialog.py` and `plan_export_flow.py`) and `bot export` both
dispatch `ExportBotPlanQuery` (`bots/application/queries/export_bot_plan/`) and write through
`bots/adapters/plan_file.py`. Nothing on that path names a kind: `BotSnapshot.kind` and `config` pass
through as opaque data, and only the parser asks `IBotKindCatalog`
(`test_bots_export_path_names_no_kind.py`, `test_export_of_a_second_kind.py`; `BOT-179`).

## Out: what the module asks and hears

- **Calls** go through `trading`'s ports, `IVenueTradingPorts`
  (`src/modules/trading/contracts/i_venue_trading_ports.py` → `IVenueTradingPorts`): orders, the
  owner budget a bot registers before it trades
  (`src/modules/trading/contracts/owner_budget_registration.py` → `OwnerBudgetRegistration`), the
  account and the symbol rules.
- **Events** the module subscribes to at boot (`bots/module.py` → `BotsModule.boot`): a fill, an end
  and a rejection of a bot's order, its symbol's funding fee, a divergence of its position from the
  exchange's (`EPIC-039F`), its symbol's ticks, the trading switch
  (`src/modules/trading/contracts/events/trading_switch_changed_event.py` →
  `TradingSwitchChangedEvent`), and the user-data stream's health
  (`src/modules/trading/contracts/events/user_stream_health_event.py` → `UserStreamHealthEvent`).
- **Published:** `BotChangedEvent` after every write to the store, and `BotStopGaveUpEvent` when a
  stop's automatic retries are used up.

**Planned.** `EPIC-040B` gives the backtest a kind-neutral result and simulator port; `EPIC-039L`
adds an exchange-side stop order, which still goes through `trading` (see
[`06-runtime.md`](06-runtime.md)).
