# SPEC-014 — Run a Grid bot

- **Status:** ✅ built and proven (the run on Spot Testnet is the user's, §8)
- **Actor:** trader
- **Origin:** the user, 2026-10-03, [`PRO-006`](../../Tasks/proposal/PRO-006.md): *"thêm 1 tab là bot
  trading … Tab đó có thể chọn loại bot, và tùy vào các bot sẽ có thanh công cụ riêng"* ("add a
  Bot trading tab; it picks the bot type, and each bot type has its own toolbar"). Built as
  `EPIC-029B`/`029C`/`029E`/`029F`/`029G`; the
  [ADR](../../Tasks/epics/EPIC-029_bots_tab_grid_fast_track/DECISION_2026-10-03_bots_module_and_grid_bot.md) (D19, O3, O4).
- **Surfaces:** the Bots tab (`bots`, NAVIGATION item 18, nav "Bots").

## 1. Trigger

*"I want a Spot Grid bot on this symbol: I set its range and capital, I see whether the plan is
sound, I start it, and I watch what it does."*

## 2. Preconditions

- Spot Testnet is enabled in Settings and the app was restarted after the change;
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
8. **Stop** asks what to do with the base the bot holds, with *keep* preselected every time (O3),
   and says its resting orders will be cancelled. **Cancel** leaves the bot running.
9. Closing the app while any bot is not at rest asks first, naming the bots and what closing
   leaves behind (O4); **Cancel** keeps the app open.

Only one action runs at a time: while it runs, the list, New bot and every action are disabled.

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

## 6. What this use case does NOT promise

- Futures grids, trailing grids, DCA and signal bots: Spot Grid is the only kind (`EPIC-029K`/`029L`).
- A backtest of the plan before it starts: that is `EPIC-029D`.
- Watching the stop loss and take profit while the app is closed: nothing runs then, which is why
  closing asks first.
- The Fills tab reads the four newest pages of the symbol's order history since the run started;
  it says so when there is more.
- The chart's overlay for a running bot is its plan's levels; level states and fills are in the
  Orders and Fills tabs, not on the chart.

## 7. Ports and modules it exercises

- bots: `ListBotsQuery`, `GetPlannerMarketQuery`, `GetBotFillsQuery`; `CreateBotCommand`,
  `EditBotCommand`, `StartBotCommand`, `PauseBotCommand`, `ResumeBotCommand`,
  `ConfirmBotResumeCommand`, `StopBotCommand`, `DeleteBotCommand`; `IBotKindCatalog`,
  `IBotKind`; `BotChangedEvent`; `BotChart`, `BotTickFeed`.
- trading: `IVenueTradingPorts` (`IOrderEntryTerms`, `IAccountActivity`), `OwnerBudgetCaps`.
- market_data: `IHistoricalKlines`, `IMarketDataSync`, `IMarketStream`, `MarketDataCandleFeed`.
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
| **The user runs it**: a Grid on Spot Testnet from New bot to Stop, on a real display | `EPIC-029H` | desktop, the user |
