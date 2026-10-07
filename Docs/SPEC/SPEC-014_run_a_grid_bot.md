# SPEC-014 — Run a Grid bot

- **Status:** ✅ built and proven (the run on Spot Testnet is the user's, §8)
- **Actor:** trader
- **Origin:** the user, 2026-10-03, [`PRO-006`](../../Tasks/proposal/PRO-006.md): *"thêm 1 tab là bot
  trading … Tab đó có thể chọn loại bot, và tùy vào các bot sẽ có thanh công cụ riêng"* ("add a
  Bot trading tab; it picks the bot type, and each bot type has its own toolbar"). Built as
  `EPIC-029B`/`029C`/`029D`/`029E`/`029F`/`029G`; the
  [ADR](../../Tasks/epics/EPIC-029_bots_tab_grid_fast_track/DECISION_2026-10-03_bots_module_and_grid_bot.md) (D19, O3, O4).
- **Surfaces:** the Bots mode (`bots`, NAVIGATION item 18, nav "Bots"), laid out as HLD §11.2.1
  lists it since `EPIC-033K`: the selected bot's chart in the centre, Bots (the list) on the left,
  Plan on the right, and Orders, Fills, Log and Backtest tabbed at the bottom. Every command is in
  the Bots menu.

## 1. Trigger

*"I want a Spot Grid bot on this symbol: I set its range and capital, I see whether the plan is
sound, I start it, and I watch what it does."*

## 2. Preconditions

- `secrets.local.json` (or the environment) holds Spot Testnet's key pair. There is no venue switch
  in Tools → Options and no restart (`EPIC-034B`): a venue with a key is on, and a key saved there
  is used by the next request.
- The symbol's daily candles are stored (Database tab) for the ATR and Bollinger suggestions and
  the ATR zones; without them the plan is still judged, only those are missing.
- Nothing has to be switched on for a start to place anything: Start opens Spot's order session
  itself, after reconciling the account (`SPEC-004`, `EPIC-034C`).

## 3. Main flow

1. The trader opens the Bots mode. The Bots panel lists every saved bot: name, kind, venue, symbol,
   state in words (Draft, Running, Paused, Recovering, Halted, Stopped, Error) and grid profit.
2. The trader chooses Bots → **New bot…** and answers the minimum, in order: the kind (Spot Grid), the
   Spot venue (every Spot venue is listed with its connection state, "API key saved" or "no API key";
   one is preselected, and none blocks: Start refuses a venue that is not a Spot venue
   this app trades on), the symbol (chosen in the shared symbol picker over the Spot catalog, never taken
   from a chart) and, optionally, a name.
   **Create bot** saves a DRAFT with no parameters; nothing is placed. **Cancel** saves nothing
   (`BOT-150`).
3. **Connect** (`EPIC-034D`). Selecting a bot reads its venue's account by itself, once for every bot
   on the same venue and symbol, and again every minute: what the account can spend, what the venue
   charges, whether the account's key may trade, and the symbol's filters and price, all as one
   snapshot. An identity strip above the bot shows its name, kind, saved state, the venue by its
   title with the result ("Spot Testnet: Connected · 900 USDT available · key can trade") and the
   status bar names the same venue. Until the read succeeds the chart's place and the Plan are
   locked and say why, and the Plan lists the unread account as the first thing left before Start; Bots →
   **Retry venue account** reads again. A key the exchange says cannot trade opens the chart and
   keeps Start off (the Design step's `KEY_CANNOT_TRADE`). Go live is offered only once the account
   was read, and a lock hides the same bot's chart instead of closing it.
   Reading places nothing and needs trading off.
   A failed read is told **once**, in the message bar of the mode (what failed, what to do, Retry and
   Details…); the strip, the chart's place and the Plan's Connect item say only the short state, "Not
   connected: key refused" (`BUG-181`). A read of the same venue that the exchange refuses for the
   same reason (the bot's fills, with the key refused) joins that bar and raises none of its own.
   **Venue.** While the bot is a Draft that never ran, the Plan's Venue field offers every Spot
   venue, and choosing another moves the bot there at once: Connect reads the new venue's account,
   the chart switches to that venue's market, and readiness is judged again; parameters not yet
   saved stay on screen. Moving to Spot Mainnet asks nothing here; the real-money question is asked
   at Start (`EPIC-034` D11). A bot that has run or runs keeps its venue, and the field says so
   (`BOT-171`; Futures grid bots are `EPIC-029K`).
   The new bot's design follows: the app reads the symbol's filters, fees and price from the venue and
   its stored daily candles, then shows the kind's verdict on each check: OK, Warning or Refused,
   with the threshold beside the measured value. The planner preview draws the proposed levels on
   the bot's chart; Bots → **Fit levels** scales the price axis to show them all. A draft's chart
   reads stored candles until the trader's **Go live** on its chip opens a view-only price stream
   (it places nothing); a running bot's chart is Live on its own (`EPIC-034G`). The chart and the
   Backtest tab read the bot's own venue's market and stored candles, never another venue's (`BUG-172`).
4. **Design** (`EPIC-034F`). The trader sets the parameters in the Plan panel, the kind's editor (lower and
   upper price, grids, spacing, capital, stop loss, take profit). Until the lower price, upper price and
   capital are set, the one verdict is Refused and names them. Every constraint on the plan is a named
   assertion that answers with its numbers, judged beside the account the Connect step read; the
   verdicts, the field messages and the drawn levels follow each edit.
   **Suggest from ATR** or **Suggest from Bollinger**, the Grid's own commands (Bots menu, and the
   Grid toolbar at the top of the editor, shown while a Grid is selected), fills the range only
   when chosen, rounded to the tick; while the parameters cannot be edited, both are disabled. **Save bot**
   (Ctrl+S) stores the edits for a draft; Start does not wait for it (step 6). The parameters can be
   changed whenever the bot is not running: a Draft, or a Stopped bot, which returns to Draft.
5. **Blocking or advice** (decision D7). A constraint that states the exchange's rules or money **blocks
   Start**: the capital against the balance the account can spend, the minimum notional, trading's
   per-order cap, the open-order limit, the price band, break-even after fees (every grid loses), the
   key's permission to trade, and a stop loss or take profit on the wrong side of the range. One that
   is strategy judgement only **advises**: the ATR, the room left for slippage, the spacing, how far
   an exit sits, some grids losing on each cycle. The field the number lives in carries the sentence
   under it, "Blocks Start: The capital is 10,000 USDT, above the 9,999.99 USDT available on Spot
   Testnet; lower it to at most 9,999.99", or "Advice: …"; a constraint about the key, which is no
   field, appears in the verdicts and in Start's reason. While any verdict is Refused, Start is
   off and the Plan lists it among what is left (step 6). **The sell
   levels need no base in the account**: Start buys the base they sell at market first, out of the
   same capital, and the "Opening buy" verdict says how much and for about what (ADR O2).
6. **Run** (`EPIC-034H`). At the top of the Plan the trader sees the three steps in words and what
   is left before Start: "Start: 3 things left", then "1. Connect: done", "2. Design: 2 things left",
   "3. Run: waits for Design", then one line per item with its reason and its fix ("• Design: The
   capital is 1000 USDT, above the 800.00 USDT available on Spot Testnet; lower it to at most 800.00
   → edit Capital (quote)"). The items come from one query, `GetBotReadiness`, the same function the
   Start use case asks at the click, so the button and the click cannot disagree: Connect (the
   account unread or not readable), Design (every blocking constraint of step 5, once connected) and
   Run (the venue trades Spot, no other bot is active, nobody else holds the symbol, the owner budget
   fits trading's caps). Bots → **Fix next item** does the first fix on offer: reads the account again,
   brings the field to change forward, or selects the bot that is still active so **Stop…** is one
   command away. The primary action is **Save and start** (decision D8, Bots menu and toolbar): it
   is off while anything is left, and its tip says "N things left" and why. One thing a click can
   still meet is not in the list because only the exchange can answer it: reconciling the account
   (a position the app did not open, §5) and registering the owner budget; they
   refuse in their own words, and a race on a listed item (another bot started in the gap) refuses
   in the list's words. Nothing is placed and nothing saved when the list refuses.
7. The trader clicks **Save and start**. The edits on screen are judged as they would be saved, and
   only a bot that is ready with them is saved and started: a refusal from the list saves nothing. A
   refusal only the exchange can give (the reconciliation, the budget's registration) comes after the
   save, so the edits stay saved and the bot is not started; with no edits it starts what is saved. The bot places its ladder through trading,
   with its own tag, and moves through Starting to Running. The list and the panels follow each
   change without a refresh: the state, grid profit, unrealised PnL at the latest price, what it holds, its
   running time, its resting orders (Orders), its fills from the venue's history (Fills, by the
   bot's tag) and its log (Log).
8. **Pause** stops new orders and keeps the resting ones; **Resume** continues. A Halted bot's
   **Resume** cancels its tagged orders and proposes a new ladder, shown in its log; **Confirm
   resume** lays it. With no proposal held (no Resume since the halt, or the app restarted) Confirm
   resume is refused with "press Resume first" and nothing is placed.
9. **Backtest** (`EPIC-029D`): the Backtest panel replays the parameters on screen (the unsaved
   edits too) over an interval (1m, 5m, 15m or 1h) and a UTC period, last seven days by default.
   **Run backtest** shows the replayed candles with the plan's levels, fills and exits on a
   bot chart of its own, the grid's equity against buy-and-hold on the same timestamps, and the figures
   as a read-out: grid profit apart from unrealised, both curves' end against the capital, fees by
   maker and taker, and how many candles were replayed without 1-second klines; under them, in words,
   what stopped the replay, the fill rule and what the coarse or missing candles mean. **Cancel**
   drops the run and the last result stays; selecting another bot drops it and clears the result.
10. **Stop** asks what to do with the base the bot holds, with *keep* preselected every time (O3),
   and says its resting orders will be cancelled. **Cancel** leaves the bot running.
11. Closing the app while any bot is not at rest asks first, naming the bots and what closing
   leaves behind (O4); **Cancel** keeps the app open.

Only one action runs at a time: while it runs, the list, New bot and every action are disabled.
A backtest is not such an action: it reads stored candles only, so the bot's actions stay
available while it runs.

## 4. What must be true afterwards

- A created bot is still listed after a restart, in the state it was saved in; a bot that was
  running comes back Recovering and is reconciled before it acts (ADR D12).
  It is reconciled when the venue's order session opens, which only a deliberate action does
  (a Start, an arm or a manual order, SPEC-004, `EPIC-034C`): nothing trades at start-up without a
  person acting, so a restored bot stays Recovering until then.
- A stopped bot has no resting order carrying its tag on the venue, and holds the base or sold
  it, as chosen.
- Grid profit counts only completed buy-then-sell cycles, net of both fees.

## 5. When it goes wrong

| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| No Spot venue is available in this build | New bot says so and Create is disabled | Only a Spot venue can run a Spot Grid |
| The venue has no key, rejects it, or the exchange answers a maintenance page or cannot be reached | One message bar says what failed and what to do, with Retry and Details…; the chart's place, the strip and the Plan's Connect item say the short state ("Not connected: key refused"); the Plan is locked and lists it as the first thing left; Start is disabled with the same words; Bots → Retry venue account (or Fix next item) | A design judged against an account that was not read is a guess (`EPIC-034D`, D1); a web page where data was expected is named MAINTENANCE, never an unclassified exception |
| The symbol is unknown, or the venue cannot be read | A Design item: "The plan cannot be judged: …" with the venue's reason; Start is disabled | A plan judged against no numbers cannot start |
| Another bot is still active (ADR D20) | A Run item "Bot … is still active; stop it before starting another", and Fix next item selects that bot; Start is disabled | The fast track lets one bot hold the exchange; the check and the start are one step under one lock |
| Another owner (a strategy, a manual order) holds the symbol | A Run item "BTCUSDT is held by another owner"; Start is disabled | Trading's lease keeps two owners off one symbol; the item is read from the session, not claimed |
| The ladder needs more open orders than trading's caps allow | A Run item naming the count and the cap; Start is disabled | Trading refuses the same budget at registration; asking first says it before the click |
| The click finds what the screen did not: another bot started in the gap, the lease taken, the key cut | The refusal names the same item in the same words ("1 thing left: Bot … is still active …"); nothing was saved or placed | The Start use case asks the same assessment as the screen, before any order and before saving the edits |
| A required parameter is not set yet (a new bot) | One Refused verdict naming the lower price, upper price or capital to set; Start disabled | A bot is created with the minimum (`BOT-150`) |
| A parameter is unreadable or the plan certainly loses or breaks an exchange rule | A Refused verdict naming it, and the same sentence under the field to change, with the number that fixes it ("raise the capital to about …", "lower it to at most …"); Start disabled | The kind refuses only certain losses and certain rejections: the exchange's rules and money (`EPIC-029C`, `EPIC-034F`, D7) |
| The capital is more than the account can spend | "Blocks Start: The capital is … USDT, above the … USDT available on …; lower it to at most …" under Capital; Start disabled | The balance is read once by the Connect step, so the click is no longer the first time it is compared (D7) |
| The key cannot trade | A Refused verdict "The API key for … cannot trade"; Start's reason says it; the chart stays open | The exchange's own `canTrade` flag; an unknown flag never blocks, its order check decides |
| A stop loss at or above the lower limit, or a take profit at or below the upper | Refused, under the exit's field: put it below, or above, the range | An exit on the wrong side would fire inside the grid or close it while it earns (D7) |
| The ATR, the slippage room, the spacing or an exit's distance is outside advice | "Advice: …" under the field; Start stays enabled | Strategy judgement is the trader's (D7) |
| Start's reconciliation refuses (it needs the exchange to answer, so it is not in the list before the click): the connection is not ready, or the account holds a position the app did not open | The use case refuses with the reason in words ("…unexpected open positions — please handle them manually on the exchange before starting a bot…"), before a lease is claimed or anything is sent | trading is the only module that sends orders, and the guard against foreign positions is kept (SPEC-004) |
| An Emergency stop closes the order session while the bot runs | The bot moves to Halted with the reason beside its state; it resumes only through a deliberate action (a Start, an arm or an order reopens the session) | trading is the only module that sends orders, and a stop wins |
| The fills cannot be read | The Fills panel says why | The venue's order history is a network read |
| A bot file on disk cannot be read | The status line names the file | The store refuses it rather than guessing (`EPIC-029B`) |
| The action's answer arrives after the trader moved on or left the mode | Nothing: it is dropped and logged | One action at a time, fenced (`async-ui-action-rule.md`) |
| The backtest's period has no stored candles | "No 15m candles of BTCUSDT are stored …" and **Sync candles**; only a click syncs the interval and its 1-second klines ("Stop" leaves what was stored), then the backtest runs again | Opening a panel or running a backtest is never a network request (`BUG-107`) |
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
- The Fills panel reads the four newest pages of the symbol's order history since the run started;
  it says so when there is more.
- The chart's overlay for a running bot is its plan's levels; level states and fills are in the
  Orders and Fills panels, not on the chart.

## 7. Ports and modules it exercises

- bots: `ListBotsQuery`, `GetPlannerMarketQuery`, `GetVenueConnectionQuery`, `GetBotReadinessQuery`, `GetBotFillsQuery`, `RunGridBacktestQuery`; `CreateBotCommand`,
  `EditBotCommand`, `StartBotCommand`, `PauseBotCommand`, `ResumeBotCommand`,
  `ConfirmBotResumeCommand`, `StopBotCommand`, `DeleteBotCommand`, `ChangeBotVenueCommand`; `IBotKindCatalog`,
  `IBotKind`; `BotChangedEvent`; `BotChart`, `BotTickFeed`.
- trading: `IVenueTradingPorts` (`IOrderEntryTerms`, `IAccountActivity`, `ITradingSession.lease_holder`), `IVenueAccounts` / `IVenueAccountReader` (`VenueAccountSnapshot`, `ConnectFailure`), `OwnerBudgetCaps`.
- market_data: `IHistoricalKlines`, `IMarketDataSync`, `IMarketStream`, `MarketDataCandleFeed`,
  `IMarketDataRepository` (the 1-second klines, streamed).
- core: `ICloseObjections`, `ICommandDispatcher`.

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| The list, legal actions per state, Refused disables Start, save before start, Stop and Delete ask, New bot creates a DRAFT, one action at a time, stale answers dropped, a write elsewhere re-read | `tests/unit/modules/bots/ui/bots_screen/test_bots_presenter.py` | unit (real bots graph) |
| Every state's legal actions and the reason for every disabled one | `tests/unit/modules/bots/ui/bots_screen/test_bot_action_rules.py` | unit |
| Verdict lines with threshold and measured value; no start without market numbers | `tests/unit/modules/bots/ui/bots_screen/test_bot_plan_judge.py` | unit |
| Every constraint at and around its boundary; the balance, the key and the opening buy read the account; each violation blocks exactly when D7 says | `tests/unit/modules/bots/domain/grid/test_grid_checks.py` · `test_grid_account_checks.py` · `test_grid_constraints.py` | unit |
| What is left before Start is one assessment: each step's items, status and words; the Start use case refuses exactly what the query reports, before any order and before saving; Save and start judges the edits as they would be saved | `tests/unit/modules/bots/application/test_bot_readiness_assessment.py` · `test_start_bot_readiness.py` · `test_other_active_bot_and_budget.py` | unit (real reader over fakes) |
| The Plan shows the three steps and each item with its reason and fix; Bots → Fix next item; Save and start is the primary action, off with "N things left"; a bot with a run shows no progress; a click refused in the list's words | `tests/unit/modules/bots/ui/bots_screen/test_bots_run_step.py` · `test_readiness_words.py` · `test_save_and_start_command.py` · `test_bot_readiness_fsm_matrix.py` | unit (real bots graph) |
| From a new bot to a running bot through the three steps on the composed app; Save and start with edits; a capital above the account listed before the click | `tests/integration/modules/bots/test_bots_tab_drives_the_executor.py` | integration (fake exchange) |
| The lease's holder is readable without claiming | `tests/unit/modules/trading/contracts/test_trading_session_contract.py` | unit (contract suite, real and fake) |
| A violated constraint is said on its field with its number, blocking apart from advice; every code decides its field; the plan's levels are drawn on the chart and follow each edit | `tests/unit/modules/bots/ui/kinds/test_grid_field_errors.py` · `tests/unit/modules/bots/ui/bots_screen/test_bots_design_step.py` | unit (real bots graph) |
| Suggestions fill only on a click, rounded to the tick; none while read-only | `tests/unit/modules/bots/ui/kinds/test_grid_panel.py` | unit |
| The Grid's commands are in the Bots menu, follow the Grid toolbar's actions, and are disabled with no Grid selected | `tests/unit/modules/bots/ui/bots_screen/test_kind_commands.py` | unit (real bots graph) |
| Stop preselects keep; Create needs a typed symbol and a Spot venue, and asks no parameter | `tests/unit/modules/bots/ui/bots_screen/test_bots_dialogs.py` | unit |
| A bot created with the minimum: Start names the parameters to set; the ones typed are saved | `tests/unit/modules/bots/ui/bots_screen/test_bots_presenter.py` | unit (real bots graph) |
| A Grid without its range or capital is one Refused verdict naming them | `tests/unit/modules/bots/domain/grid/test_grid_parameters_not_set.py` | unit |
| Fills by the bot's tag; resting orders from the runtime | `tests/unit/modules/bots/application/test_bot_orders_and_fills.py` | unit |
| A draft that never ran moves between the Spot venues from the Plan's Venue field and reads the new venue's account and market; a running or stopped bot keeps its venue; unsaved parameters stay; no confirmation until Start; New bot lists every Spot venue with its connection state | `tests/unit/modules/bots/ui/bots_screen/test_bots_change_venue.py` · `tests/unit/modules/bots/domain/test_bot_venue.py` · `tests/unit/modules/bots/application/test_change_bot_venue.py` · `tests/integration/modules/bots/test_a_draft_bot_and_its_venue_on_the_fake_exchange.py` | unit · integration (fake exchange) |
| One Connect failure is one advisory paragraph on screen, whatever its kind; a fills read the venue refuses raises no bar of its own | `tests/unit/modules/bots/ui/bots_screen/test_one_connect_failure_one_paragraph.py` · `test_bots_failures.py` · `tests/unit/modules/trading/adapters/binance/test_history_failures_name_their_kind.py` · `tests/integration/modules/bots/test_a_refused_fills_read_on_the_fake_exchange.py` | unit · integration (fake exchange, `-2015`) |
| Selecting a bot reads its venue's account by itself; chart, Plan and Start wait for it and say why; Retry; a key that cannot trade; one read shared by bots on a venue and symbol; the timer's re-read; a late answer dropped | `tests/unit/modules/bots/ui/bots_screen/test_bots_connect_step.py` · `test_bots_connect_chart.py` · `test_bot_connect_fsm_matrix.py` | unit (real bots graph) |
| One read returns the snapshot a design needs, or a named failure; an HTML answer is MAINTENANCE | `tests/unit/modules/trading/application/account/test_composed_venue_account_reader.py` · `tests/unit/modules/trading/adapters/binance/test_html_answer_is_maintenance.py` · `tests/integration/modules/bots/test_spot_testnet_boot_on_the_fake_exchange.py` | unit · integration (fake Binance server, with a maintenance switch) |
| The chart is central; Bots, Plan, Orders, Fills, Log and Backtest are docked as HLD §11.2.1 lists; no push button and no nested scroll area; Fit levels is a command that reaches the chart | `tests/unit/modules/bots/ui/bots_screen/test_bots_view.py` · `tests/unit/modules/bots/ui/bots_screen/test_bots_commands.py` · `tests/unit/modules/bots/ui/bots_screen/test_bots_presenter.py` | unit |
| A draft's chart goes live only by the trader's command and draws what streams; a chart at rest draws no live candle; a running bot's chart is Live on its own | `tests/unit/modules/bots/ui/chart/test_bot_chart_live_state.py` | unit |
| The chart, Plan, Orders, Fills and Log follow the selection, and say what to do with none | `tests/unit/modules/bots/ui/bots_screen/test_bots_selection.py` | unit (real bots graph) |
| The Bots menu and the mode's toolbar hold exactly HLD §11.2.3's Bots commands | `tests/integration/presentation/ui/test_bots_mode_catalogue.py` | integration (booted app) |
| Orders and fills are written in the bot's symbol filters; every column aligns, and its digits sit, by its kind | `tests/unit/modules/bots/ui/bots_screen/test_bot_tables_precision.py` · `tests/integration/modules/bots/test_bots_tab_drives_the_executor.py` | unit · integration (fake exchange) |
| Closing asks while a bot is active; Cancel keeps the window | `tests/unit/presentation/ui/test_main_window_close_guard.py` | unit |
| A Grid starts, fills, pauses, stops and restarts against the fake exchange | `tests/integration/modules/bots/test_grid_bot_against_fake_server.py` | integration |
| The route is item 18 and contributed by bots | `tests/unit/shell/test_screen_wiring.py` | unit |
| The fill rule (no fill on touch, kline order, adverse side without them), fees, exits, buy-and-hold, cancellation, the report's four regimes | `tests/unit/modules/bots/domain/grid/test_grid_simulator.py` | unit |
| The backtest reads what is stored, never fetches, refuses in words | `tests/unit/modules/bots/application/test_run_grid_backtest.py` | unit |
| Two stored hours replay through their 1-second klines; without them the replay is coarse and never completes more cycles; 1-second klines that miss the candle's range are not trusted | `tests/integration/modules/bots/test_grid_backtest_stored_klines.py` | integration (real SQLite) |
| Run, Cancel keeps the last result, another bot clears it, a late result is fenced, Sync only on a click then run again | `tests/unit/modules/bots/ui/kinds/test_grid_backtest.py` | unit (real query handler) |
| A backtest's figures are a read-out of raw values by kind and its caveats are sentences | `tests/unit/modules/bots/ui/kinds/test_grid_backtest_summary.py` | unit |
| The Backtest panel holds a Grid's page and, without a selection, an instruction; it runs through the query the module binds, reads the edits and the planner's terms | `tests/unit/modules/bots/ui/bots_screen/test_bots_backtest_tab.py` | unit (real bots graph) |
| The mode's Start, Pause, Resume and Stop reach the real executor and the exchange | `tests/integration/modules/bots/test_bots_tab_drives_the_executor.py` | integration (fake exchange) |
| A Grid rests its levels with its tag, re-lays an outside cancel and stops clean on Spot Testnet; how many owner budgets fit the venue's rate limits — **pending the user's run** | `tests/testnet/test_grid_bot_round_trip.py` · `tests/testnet/test_spot_rate_limits.py` | testnet, run by the user |
| **The user runs it**: a Grid on Spot Testnet from New bot to Stop, on a real display | `EPIC-029H` | desktop, the user |
