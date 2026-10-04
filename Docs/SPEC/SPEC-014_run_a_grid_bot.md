# SPEC-014 — Run a Grid bot

- **Status:** ✅ built and proven (the run on Spot Testnet is the user's, §8)
- **Actor:** trader
- **Origin:** the user, 2026-10-03, [`PRO-006`](../../Tasks/proposal/PRO-006.md): *"thêm 1 tab là bot
  trading … Tab đó có thể chọn loại bot, và tùy vào các bot sẽ có thanh công cụ riêng"* ("add a
  Bot trading tab; it picks the bot type, and each bot type has its own toolbar"). Built as
  `EPIC-029B`/`029C`/`029D`/`029E`/`029F`/`029G`; the
  [ADR](../../Tasks/epics/EPIC-029_bots_tab_grid_fast_track/DECISION_2026-10-03_bots_module_and_grid_bot.md) (D19, O3, O4).
- **Surfaces:** the Bots tab (`bots`, NAVIGATION item 18, nav "Bots").

## 1. Trigger

*"I want a Spot Grid bot on this symbol: I set its range and capital, I see whether the plan is
sound, I start it, and I watch what it does."*

## 2. Preconditions

- Spot Testnet is enabled in Tools → Options → Trading and the app was restarted after the change;
  `secrets.local.json` holds its key pair.
- The symbol's daily candles are stored (Database tab) for the ATR and Bollinger suggestions and
  the ATR zones; without them the plan is still judged, only those are missing.
- Live trading is on for Spot (`SPEC-004`) for a start to place anything.

## 3. Main flow

1. The trader opens the Bots tab. The list shows every saved bot: name, kind, venue, symbol,
   state in words (Draft, Running, Paused, Recovering, Halted, Stopped, Error) and grid profit.
2. The trader clicks **New bot** and answers, in order: the kind (Spot Grid), an enabled Spot
   venue, the symbol (typed, never taken from a chart), and the parameters (lower and upper price,
   grids, spacing, capital, stop loss, take profit). **Create bot** saves a DRAFT; nothing is
   placed. **Cancel** saves nothing.
3. The new bot is selected. The app reads the symbol's filters, fees and price from the venue and
   its stored daily candles, then shows the kind's verdict on each check: OK, Warning or Refused,
   with the threshold beside the measured value. The planner preview draws the proposed levels on
   the bot's chart; **Fit levels** scales the price axis to show them all.
4. The trader edits a parameter. The verdicts and the preview follow each edit. **Suggest from
   ATR** or **Suggest from Bollinger** fills the range only when clicked, rounded to the tick.
   Start waits until the edits are saved with **Save**.
5. While any verdict is Refused, Start is disabled and its tooltip names the refusal.
6. The trader clicks **Start**. The bot places its ladder through trading, with its own tag, and
   moves through Starting to Running. The list and the detail follow each change without a
   refresh: the state, grid profit, unrealised PnL at the latest price, what it holds, its
   running time, its resting orders (Orders), its fills from the venue's history (Fills, by the
   bot's tag) and its log (Log).
7. **Pause** stops new orders and keeps the resting ones; **Resume** continues. A Halted bot's
   **Resume** cancels its tagged orders and proposes a new ladder, shown in its log; **Confirm
   resume** lays it. With no proposal held (no Resume since the halt, or the app restarted) Confirm
   resume is refused with "press Resume first" and nothing is placed.
8. **Backtest** (`EPIC-029D`): the Backtest tab replays the parameters on screen (the unsaved
   edits too) over an interval (1m, 5m, 15m or 1h) and a UTC period, last seven days by default.
   **Run backtest** shows the replayed candles with the plan's levels, fills and exits on a
   bot chart of its own, the grid's equity against buy-and-hold on the same timestamps, and the figures:
   grid profit apart from unrealised, fees by maker and taker, what stopped the replay, the fill
   rule, and how many candles were replayed without 1-second klines. **Cancel** drops the run and
   the last result stays; selecting another bot drops it and clears the result.
9. **Stop** asks what to do with the base the bot holds, with *keep* preselected every time (O3),
   and says its resting orders will be cancelled. **Cancel** leaves the bot running.
10. Closing the app while any bot is not at rest asks first, naming the bots and what closing
   leaves behind (O4); **Cancel** keeps the app open.

Only one action runs at a time: while it runs, the list, New bot and every action are disabled.
A backtest is not such an action: it reads stored candles only, so the bot's actions stay
available while it runs.

## 4. What must be true afterwards

- A created bot is still listed after a restart, in the state it was saved in; a bot that was
  running comes back Recovering and is reconciled before it acts (ADR D12).
- A stopped bot has no resting order carrying its tag on the venue, and holds the base or sold
  it, as chosen.
- Grid profit counts only completed buy-then-sell cycles, net of both fees.

## 5. When it goes wrong

| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| No Spot venue is enabled | New bot says so and Create is disabled | Only an enabled Spot venue can run a Spot Grid |
| The symbol is unknown, or the venue cannot be read | Start is disabled: "The plan cannot be judged: …" with the venue's reason | A plan judged against no numbers cannot start |
| A parameter is unreadable or the plan certainly loses or breaks an exchange rule | A Refused verdict naming it; Start disabled | The kind refuses only certain losses and certain rejections (`EPIC-029C`) |
| Trading is off, or the switch turns off while running | The use case refuses with its reason in the status line, or the bot moves to Halted with the reason beside its state | trading is the only module that sends orders, and its switch wins |
| The fills cannot be read | The Fills tab says why | The venue's order history is a network read |
| A bot file on disk cannot be read | The status line names the file | The store refuses it rather than guessing (`EPIC-029B`) |
| The action's answer arrives after the trader moved on or closed the tab | Nothing: it is dropped and logged | One action at a time, fenced (`async-ui-action-rule.md`) |
| The backtest's period has no stored candles | "No 15m candles of BTCUSDT are stored …" and **Sync candles**; only a click syncs the interval and its 1-second klines ("Stop" leaves what was stored), then the backtest runs again | Opening a tab or running a backtest is never a network request (`BUG-107`) |
| The period is too long for the interval | The backtest asks for a longer interval | The replay holds at most 20,000 candles |
| The period is only partly stored, or has gaps | The replay runs on what is stored; "Candles stored" says N of M, the status names how many are missing and **Sync candles** is offered | A result on part of a period is shown as such, never as the whole of it |
| A backtest finishes after Cancel, or after another bot was selected | Nothing: it is dropped and logged | Each run is an action of its own, fenced like the others |

## 6. What this use case does NOT promise

- Futures grids, trailing grids, DCA and signal bots: Spot Grid is the only kind (`EPIC-029K`/`029L`).
- A backtest that fills like the exchange: it fills a level only when the price trades a tick
  through it (never on touch), orders levels inside a candle by its 1-second klines and, without
  them, takes the adverse side first and says so. It models no slippage, no queue position and no
  partial fills, and its fees are the venue's rates read by the planner.
- Watching the stop loss and take profit while the app is closed: nothing runs then, which is why
  closing asks first.
- The Fills tab reads the four newest pages of the symbol's order history since the run started;
  it says so when there is more.
- The chart's overlay for a running bot is its plan's levels; level states and fills are in the
  Orders and Fills tabs, not on the chart.

## 7. Ports and modules it exercises

- bots: `ListBotsQuery`, `GetPlannerMarketQuery`, `GetBotFillsQuery`, `RunGridBacktestQuery`; `CreateBotCommand`,
  `EditBotCommand`, `StartBotCommand`, `PauseBotCommand`, `ResumeBotCommand`,
  `ConfirmBotResumeCommand`, `StopBotCommand`, `DeleteBotCommand`; `IBotKindCatalog`,
  `IBotKind`; `BotChangedEvent`; `BotChart`, `BotTickFeed`.
- trading: `IVenueTradingPorts` (`IOrderEntryTerms`, `IAccountActivity`), `OwnerBudgetCaps`.
- market_data: `IHistoricalKlines`, `IMarketDataSync`, `IMarketStream`, `MarketDataCandleFeed`,
  `IMarketDataRepository` (the 1-second klines, streamed).
- core: `ICloseObjections`, `ICommandDispatcher`.

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| The list, legal actions per state, Refused disables Start, save before start, Stop and Delete ask, New bot creates a DRAFT, one action at a time, stale answers dropped, a write elsewhere re-read | `tests/unit/modules/bots/ui/bots_screen/test_bots_presenter.py` | unit (real bots graph) |
| Every state's legal actions and the reason for every disabled one | `tests/unit/modules/bots/ui/bots_screen/test_bot_action_rules.py` | unit |
| Verdict lines with threshold and measured value; no start without market numbers | `tests/unit/modules/bots/ui/bots_screen/test_bot_plan_judge.py` | unit |
| Suggestions fill only on a click, rounded to the tick | `tests/unit/modules/bots/ui/kinds/test_grid_panel.py` | unit |
| Stop preselects keep; Create needs a typed symbol and a Spot venue | `tests/unit/modules/bots/ui/bots_screen/test_bots_dialogs.py` | unit |
| Fills by the bot's tag; resting orders from the runtime | `tests/unit/modules/bots/application/test_bot_orders_and_fills.py` | unit |
| Closing asks while a bot is active; Cancel keeps the window | `tests/unit/presentation/ui/test_main_window_close_guard.py` | unit |
| A Grid starts, fills, pauses, stops and restarts against the fake exchange | `tests/integration/modules/bots/test_grid_bot_against_fake_server.py` | integration |
| The route is item 18 and contributed by bots | `tests/unit/shell/test_screen_wiring.py` | unit |
| The fill rule (no fill on touch, kline order, adverse side without them), fees, exits, buy-and-hold, cancellation, the report's four regimes | `tests/unit/modules/bots/domain/grid/test_grid_simulator.py` | unit |
| The backtest reads what is stored, never fetches, refuses in words | `tests/unit/modules/bots/application/test_run_grid_backtest.py` | unit |
| Two stored hours replay through their 1-second klines; without them the replay is coarse and never completes more cycles; 1-second klines that miss the candle's range are not trusted | `tests/integration/modules/bots/test_grid_backtest_stored_klines.py` | integration (real SQLite) |
| Run, Cancel keeps the last result, another bot clears it, a late result is fenced, Sync only on a click then run again | `tests/unit/modules/bots/ui/kinds/test_grid_backtest.py` | unit (real query handler) |
| The Backtest tab shows for a Grid, hides without a selection, runs through the query the module binds, reads the edits and the planner's terms | `tests/unit/modules/bots/ui/bots_screen/test_bots_backtest_tab.py` | unit (real bots graph) |
| The tab's Start, Pause, Resume and Stop reach the real executor and the exchange | `tests/integration/modules/bots/test_bots_tab_drives_the_executor.py` | integration (fake exchange) |
| A Grid rests its levels with its tag, re-lays an outside cancel and stops clean on Spot Testnet; how many owner budgets fit the venue's rate limits — **pending the user's run** | `tests/testnet/test_grid_bot_round_trip.py` · `tests/testnet/test_spot_rate_limits.py` | testnet, run by the user |
| **The user runs it**: a Grid on Spot Testnet from New bot to Stop, on a real display | `EPIC-029H` | desktop, the user |
