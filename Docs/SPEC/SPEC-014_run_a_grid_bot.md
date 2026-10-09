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
   key's permission to trade, a stop loss or take profit on the wrong side of the range, **the price below
   the range** (Start would market-buy the whole ladder's base: `PRICE_BELOW_RANGE`, `EPIC-035L`) and
   levels that round to one price on the venue's tick (`LEVELS_ROUND_TO_ONE_PRICE`, `EPIC-035S`). One
   that is strategy judgement only **advises**: the ATR, the room left for slippage, the spacing, how
   far an exit sits, some grids losing on each cycle, **the price above the range** (the bot starts
   with nothing bought and waits for a fall: `PRICE_ABOVE_RANGE`). The field the number lives in carries the sentence
   under it, "Blocks Start: The opening buy and the BUY levels need 995.48 USDT and Spot Testnet has
   800.00 USDT free; lower the capital to at most 803.63" (the balance is judged on the exchange's
   snapshot, step 6), or "Advice: …"; a constraint about the key, which is no
   field, appears in the verdicts and in Start's reason. While any verdict is Refused, Start is
   off and the Plan lists it among what is left (step 6). **The sell
   levels need no base in the account**: Start buys the base they sell at market first, out of the
   same capital, and the "Opening buy" verdict says how much and for about what (ADR O2).
6. **Run** (`EPIC-034H`). At the top of the Plan the trader sees the three steps in words and what
   is left before Start: "Start: 3 things left", then "1. Connect: done", "2. Design: 2 things left",
   "3. Run: waits for Design", then one line per item with its reason and its fix ("• Run: The
   opening buy and the BUY levels need 995.48 USDT and Spot Testnet has 800.00 USDT free; lower the
   capital to at most 803.63 → edit Capital (quote)"). The items come from one query,
   `GetBotReadiness`, the same function the Start use case asks at the click, so the button and the
   click cannot disagree: Connect (the account unread or not readable), Design (every blocking
   constraint of step 5, once connected) and Run (the venue trades Spot, no other bot is active,
   nobody else holds the symbol, the owner budget fits trading's caps, and the exchange's own facts
   below). Bots → **Fix next item** does the first fix on offer: reads the account again,
   brings the field to change forward, or selects the bot that is still active so **Stop…** is one
   command away. The primary action is **Save and start** (decision D8, Bots menu and toolbar): it
   is off while anything is left, and its tip says "N things left" and why. One thing a click can
   still meet is not in the list because only the exchange can answer it: reconciling the account
   (a position the app did not open, §5) and registering the owner budget; they
   refuse in their own words, and a race on a listed item (another bot started in the gap) refuses
   in the list's words. Nothing is placed and nothing saved when the list refuses.

   **The exchange's facts** (`BOT-173`). What only the venue knows is one snapshot, read off the UI
   thread when a bot at rest (Draft, Stopped) or Halted is selected, again by Bots → **Refresh
   exchange check** (or the item's own fix) and whenever the bot's state changes or a command it was
   sent finishes: the free and locked base and quote, the bot's own resting orders apart from the
   others on the symbol, and what its earlier runs left. It has three states and the Run step says
   each in words. **Checking the exchange…** while it is asked: the bot is not called ready and
   Start (or Resume) is off. **Unavailable**, with the reason ("Not connected: exchange
   unreachable"), never an empty account or a zero balance; Refresh asks again. **Loaded**: the
   rules judge it, each a pure function of the plan's needs and the facts (`exchange_rules.py`):
   - *Left from earlier runs* is advice, never an item: "A previous run kept 0.0166 ETH ≈ 41.50 USDT
     that this run will not trade" (`BUG-196`: Start is allowed, the base is told, not carried). If
     the history cannot be read the advice says so.
   - *The free quote is too small* for the opening buy and the BUY levels refuses Start, naming
     both numbers and the largest capital that fits (it replaces the former Design verdict
     `CAPITAL_ABOVE_BALANCE`, which compared the whole capital with a balance read earlier; the
     sentence still shows on the Capital field).
   - *The free base is too small for the SELLs of a Resume* refuses the Resume of a Halted bot
     ("Resume is blocked: The resumed ladder sells 0.0028 ETH and Spot Testnet has 0.0010 ETH
     free; 0.005 ETH is locked by orders that are not this bot's; free the base or stop the bot",
     `BUG-195`). The bot's own resting SELLs count as free, since a Resume cancels them first. The
     Resume button carries the sentence as its tip, and the Resume use case refuses it before
     anything is queued, on facts read at the click; a Paused bot's resume lays no ladder and is
     not judged.
   A further check is one more rule in `RULES`; the extension cases are in that module's docstring.
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
   resume** lays it. The proposal sizes the BUY side from what the inventory leaves of the capital
   (the capital less the inventory at cost, shared equally; a share under the exchange's minimum
   notional leaves its level empty), and a held base that no SELL level reaches is named in the
   bot's reason ("… of the inventory has no SELL level to go on and stays unplaced") (`EPIC-035R`). With no proposal held (no Resume since the halt, or the app restarted) Confirm
   resume is refused with "press Resume first" and nothing is placed. A confirmed ladder the exchange
   refuses part-way ends Halted with nothing resting: whatever part of it was placed is cancelled,
   and the bot's reason says what was refused and what could not be cancelled (`EPIC-035C`).
9. **Backtest** (`EPIC-029D`): the Backtest panel replays the parameters on screen (the unsaved
   edits too) over an interval (1m, 5m, 15m or 1h) and a UTC period, last seven days by default.
   **Run backtest** shows the replayed candles with the plan's levels, fills and exits on a
   bot chart of its own, the grid's equity against buy-and-hold on the same timestamps, and the figures
   as a read-out: grid profit apart from unrealised, both curves' end against the capital, fees by
   maker and taker, and how many candles were replayed without 1-second klines; under them, in words,
   what stopped the replay, the fill rule and what the coarse or missing candles mean. **Cancel**
   drops the run and the last result stays; selecting another bot drops it and clears the result.
10. **Stop** asks what to do with the base the bot holds, with *keep* preselected every time (O3),
   and says its resting orders will be cancelled. **Cancel** leaves the bot running. A stop the
   exchange has not finished (a refused cancel, an order not yet gone) keeps the bot Stopping and
   says why and how many orders still rest. It retries by itself five times (after 10 s, 30 s, 60 s,
   2 min and 5 min); **Stop** is offered again while it waits and starts a fresh round. After the
   last retry the bot stays Stopping and says to press Stop. It is never Stopped while an order
   carrying its tag is open (`EPIC-035C`).
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
- A Recovering bot is not silent meanwhile (`EPIC-035C`): at start-up the app reads, from the
  exchange, which of its saved orders still rest, which filled while the app was closed, which are
  missing and which tagged orders the bot never saved, and shows the four counts beside its state
  ("after the restart: 2 saved order(s) rest, 1 filled while the app was closed, 1 missing, 0 not
  saved by the bot; nothing is placed until trading is enabled"). The read places and cancels
  nothing; a read that fails is said in the same place. Counter orders for what filled still wait
  for the order session.
- A bot whose start the restart cut short (Starting when the app closed) comes back Halted, and the
  app cancels the orders carrying its tag as soon as the exchange lets it — when trading is enabled
  at the latest. Until then the bot says how many tagged orders still rest; a cancel the exchange
  refuses is said, never reported as a clean halt.
- A stopped bot has no resting order carrying its tag on the venue, and holds the base or sold
  it, as chosen.
- **Every bot that is not Draft or Stopped streams its own symbol's price** (`EPIC-035A`), on its
  own venue's market and under its own stream owner, whether or not any chart is open or any other
  bot is selected; the stream is released when the bot reaches Stopped or Draft or is deleted.
  Two bots on one symbol share the venue's one subscription. A Testnet price never reaches a
  Mainnet bot, and a Spot price never a Futures bot (`BUG-172`).
- **A stop loss or take profit is watched in every state that holds or lays orders**: Starting,
  Running, Paused, Recovering, Halted and Error. A price at or beyond it stops the bot as it always
  did (the ladder off, the base sold), including a bot restored Recovering that has not yet
  reconciled. A bot already Stopping is not re-decided by a tick.
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
| The price is below the range's lower bound at Start | Refused under Lower and Upper price: "The price … is below the range's lower bound …. Starting now would buy about … of the base asset at market, …% of the capital. Lower the range to include the price, or wait for it to return"; Start disabled | Below the range every level is a SELL level, so the plan buys the whole ladder's base at market before laying an order (owner decision D4 (a), `EPIC-035L`) |
| The price is above the range's upper bound at Start | "Advice: The price … is above the range's upper bound …. The bot starts with nothing bought and places BUY orders only"; Start stays enabled | Above the range every level is a BUY level: nothing is bought, no money is at risk (D4 (a)) |
| Two or more levels round to one price on the venue's tick | Refused under Grids, Lower and Upper price, naming the colliding levels and their price: use fewer grids or a wider range; Start disabled | Two rungs at one price make a fill or an adopted order ambiguous (`EPIC-035S`, audit L3) |
| A running bot's price leaves the range, or comes back | Nothing changes for the bot (no automatic exit, D2); one `BotRangeChangedEvent` (BELOW / ABOVE / INSIDE) is published per change, for the alert `EPIC-036B` builds | The fact exists now so the alert is a subscriber, not a new price path (`EPIC-035L`, audit H7) |
| The ATR, the slippage room, the spacing or an exit's distance is outside advice | "Advice: …" under the field; Start stays enabled | Strategy judgement is the trader's (D7) |
| Start's reconciliation refuses (it needs the exchange to answer, so it is not in the list before the click): the connection is not ready, or the account holds a position the app did not open | The use case refuses with the reason in words ("…unexpected open positions — please handle them manually on the exchange before starting a bot…"), before a lease is claimed or anything is sent | trading is the only module that sends orders, and the guard against foreign positions is kept (SPEC-004) |
| A confirmed resume is refused part-way (a cap, a rule, a lost connection) | The bot is Halted, its reason names what was refused, and none of the part already placed is left on the exchange; if a cancel failed the reason says which order may still rest | A bot that no longer manages its ladder must not leave it trading (`EPIC-035C`, H4) |
| A stop is waiting on the exchange and nothing seems to move | Stopping, with the reason, the orders still open and "retry n of 5 in …"; after the last retry "the automatic retries are used up; press Stop to try again" and an error line in the log; Stop is offered | The bot is never Stopped early, and a wait is bounded, visible and repeatable (`EPIC-035C`, H5) |
| The app restarts while a bot runs, and the exchange cannot be read at start-up | The bot stays Recovering and says "after the restart the exchange could not be read: …" | A read that fails is a report, not a fault: an offline start must not mark every bot Error (`EPIC-035C`, H6) |
| The app restarted during a start and the order session is still closed | Halted, "the app closed while this bot was starting; N tagged order(s) still rest and are cancelled when trading is enabled" | Cancels are refused while the session is closed; the debt is on the bot's own file and paid at the next enable (`EPIC-035C`, H6) |
| A start (or a confirmed resume) is refused because trading went off, part of its ladder already laid | Halted, "trading went off while this bot was starting; its tagged orders may still rest and are cancelled when trading is enabled"; at the next enable the partial ladder is cancelled and the bot says how many | Cancels are refused while the session is closed (D13), but a ladder that never completed is no valid grid: the debt is on the bot's own file and paid at the enable, as for a restart (`BUG-190`). A ladder that completed rests until Resume or Stop, as before |
| An Emergency stop closes the order session while the bot runs | The bot moves to Halted with the reason beside its state; it resumes only through a deliberate action (a Start, an arm or an order reopens the session) | trading is the only module that sends orders, and a stop wins |
| The chart is closed, another bot is selected, or the app was just restarted | Nothing changes: the bot's own price stream is open and its stop loss and take profit are watched exactly as with the chart open | A safety rule must not depend on a widget being open (`EPIC-035A`) |
| The price feed goes quiet: no tick for 60 s while the bot holds orders (or no first tick within 60 s of its stream opening) | The bot moves to Halted with the reason "price_feed_stale" and its detail, "last tick N s ago; the limit is 60 s", beside its state; its ladder is taken off the exchange. A fresh tick does not resume it: Resume, with its confirmation, is the only way back | A quiet feed looks like a flat market, so the stop loss cannot be trusted; a halt that stops placing and takes the ladder off is the safe answer, and the user decides (`EPIC-035A`) |
| The symbol is not trading (BREAK, HALT, CANCEL_ONLY …), at Start, at a Resume, or when the exchange refuses an order for it | Start and a confirmed Resume are refused before any order, the bot Halted with the reason "symbol_not_trading" and "BTCUSDT is BREAK on the exchange; resume once it is TRADING". A running bot whose order is refused for it is Paused with the same reason, its ladder still resting and the orders it could not place held; Resume while it still does not trade stays Paused and says the status; once it trades, Resume places what was held. Stop still cancels in every status | A refusal for the status is a fact about the symbol, not a fault of the bot, so it is a named pause the user ends; the status is read at each Start and Resume from the exchange itself, not from the symbol catalog trading keeps for a day (`EPIC-035E`, `EPIC-035U`) |
| The exchange no longer lists the symbol (a delisting) | At Start or Resume the bot is Halted with the reason "symbol_delisted"; a running bot whose order is refused as an unknown symbol is Halted with it and its ladder is taken off the exchange | Nothing can be placed on a symbol that is gone, and the orders are cancelled while the exchange still answers (`EPIC-035E`) |
| The exchange changes a filter of the symbol while the bot runs (tick size, step size, market step or minimum notional), found by the bot's own read of the exchange about every 15 minutes while it holds orders | The bot moves to Halted with the reason "exchange_terms_changed" and, beside it, each filter with its old and new value ("tick size 0.01 -> 0.001"); its ladder is taken off the exchange. Resume proposes a ladder on the new numbers. A symbol the exchange stopped listing halts it with "symbol_delisted"; a changed fee only replaces the kept terms; a read that fails is logged and asked again | The ladder's prices and quantities were rounded to numbers that no longer hold, and the first order built on them would be refused (`-1013`) and end in Error; a halt that names the change is the answer, and the same read keeps the symbol status the Start and Resume gate reads as fresh as the filters (`EPIC-035U`) |
| Start or Resume cannot reach the exchange to read the symbol's terms (a timeout, a refused request) | The start goes on with the terms the bot already holds and says so in its log (`[symbol-status]`); it is never called a delisting, which only a catalog that was read and does not list the symbol is. A running bot's 15-minute terms read that fails is logged and asked again | A bad moment says nothing about the symbol; the exchange's own refusal of an order is still the guard (`EPIC-035U`) |
| The user presses Stop while a Start is still laying its opening buy and ladder | The Start lays no further order at its next step; the Stop queued behind it then cancels what was placed, as for any Stop. A Stop never waits for the rest of a paced ladder | The bot has one writer, so a Stop used to wait for every order the Start would still lay, each paced, only to cancel them (`EPIC-035V`, L9) |
| A mainnet Start arrives without the user's answer to the real-money question (a caller other than the Bots screen) | The use case refuses with "REAL_MONEY_NOT_CONFIRMED" before it reads the account or claims anything; the screen asks first and carries the answer (`real_money_confirmed`) | The question is asked by a screen, but the rule that real money is never started unasked belongs to the use case, so no other caller can bypass it (`EPIC-035V`, L6; a Resume of a bot that already started is not asked again by the use case) |
| Orders are already open on the bot's symbol that it did not place, at design time | The Design step shows an advice (never a block): "N other orders are already open on this symbol; with the plan's M that is N+M against a limit of L, and this bot will not manage them"; a count that could not be read says the check did not run | They share the exchange's open-order limit with the plan, and the bot neither places nor cancels them (`EPIC-035V`, L7) |
| A BUY fills on the highest level of the ladder (only possible when the plan opened with the price above the range) | Nothing is placed: no SELL is owed above the range, and one at the upper bound would sell at the price it was bought for and lose the fees. The base stays in the bot's inventory for the take profit, the stop loss and Stop to settle | A deliberate limit, locked by a test, not an oversight (`EPIC-035V`, L4) |
| The exchange rejects the API key while the bot runs (revoked, or off its IP list: `-2015`, `-2008`, `-2014`), on the next order or on the bot's own key check, made about once a minute while it holds orders | The bot moves to Halted with the reason "key_rejected" and, beside it, that its orders may still rest on the exchange and this app cannot cancel them until a working key is added; Stop halts the same way instead of waiting to retry. The ladder is not taken off, because the cancel would be rejected too | A rejected key is not a switch-off (which cancels nothing by design and waits for trading to return): nothing a wait can mend, and the one thing the user must know at once is that orders are left unmanaged (`EPIC-035F`). The Discord alert is `EPIC-035K`; until then the reason is the notice |
| The bot's file cannot be written (a full disk, a permission) three times in a row while it runs | The bot moves to Paused with the reason "storage_failure" and the failure beside it. Its orders stay on the exchange, nothing new is placed (a fill's counter order is held), and the bot does not trade on memory any longer. Resume works once the disk accepts a write: while it still fails, Resume is refused, the bot stays Paused and the log says why; a write that succeeds resets the count, so one or two failures that recover change nothing. Nothing fails silently: each failed save is a line in the bot's log tab (WARNING "state save failed (1/3) … retrying", then "(2/3)"; ERROR from the third), the pause is an ERROR line and the bot's reason reads "paused because its state cannot be saved … Check the disk, then press Resume" (shown at once: the store keeps the record whose write failed in front of the file, so the list and the state line say Paused and the reason while the disk still fails, and every failed save refreshes them), and the first save that works logs "state save recovered after N failure(s)". A Resume of a Halted bot, the user's or the automatic one after a rate limit, first asks the store for a write: while the disk fails no ladder is laid, the bot stays Halted with the reason "storage_failure", and no further automatic resume is scheduled. The Discord alert for the pause is `EPIC-035K`, not yet built | A bot that cannot save cannot be reconciled after a crash from its own file, and the screen reads that file, so the user cannot be told while it fails (owner decision D6, `EPIC-035G`). The count is read when a worker task ends, so the task under way finishes its own placements |
| The exchange (or trading, before it sends) refuses a running bot's counter order for its own numbers: its quantity, the percent-price band, the minimum notional, or a plain `-2010` | The bot stays Running. That rung stays empty, and the bot's reason is "counter_order_rejected" with the rung, its side and the exchange's words ("L2 SELL: …"); the rest of the ladder goes on trading and nothing is cancelled. A second refused order (or an order that ended) on any rung within a minute halts the bot with "level_keeps_ending", so an account-wide cause such as a missing balance cannot empty the ladder rung by rung. A refused rung is offered an order again only when a neighbour's fill owes it one. During a start or a confirmed resume the same refusal is a refused start (Halted, "start_refused"), not an Error | One order's numbers are not the ladder's fault, and an Error that took the whole ladder off for it was the loudest answer to the smallest problem. Until a neighbour's fill owes that rung an order again it rests nothing; the reason says so. A refusal about the bot or the venue (a limit, a lease, a switch) still halts (`EPIC-035T`) |
| A Halted bot is resumed after it lost money: the base it holds cost more than it is worth, or most of the capital is already in inventory | The proposed BUY side shares only what the inventory leaves of the capital (capital less the inventory at cost), and no BUY at all when nothing is left; a base the SELL levels do not reach is named on the bot, not left unsaid | Trading refuses open BUYs plus the inventory at cost beyond the capital, so a BUY side sized from the whole capital again would ask for what the budget refuses (`EPIC-035R`) |
| A Start after a Stop that kept the base (or after halted runs): the bot's earlier runs left base on the account | Start is allowed. The new run trades only its own orders, and the bot's figures name the base the earlier runs left ("Left from earlier runs", with its cost), read from the exchange's history of the bot's orders and capped by the free base the account still holds; the log says it too (`[earlier-runs]`). A venue that does not answer leaves the figure empty and the log says so | A run counts only its own orders (ADR D6), so that base is neither sold by the ladder nor in the bot's inventory; it is told, not carried, because a hand-sale in between would make a carried figure wrong. Adopting it into the run is a later action (`BUG-196`) |
| A bot's earnings are read (the Plan panel's figures and the Bots list) | The first figure is **Total PnL**: every sell, of a completed cycle, of the opening inventory or of an exit slice, against the average cost and net of fees, plus the unrealised PnL of what is held at **the price the bot itself last heard** (saved with its state every 30 s at most). "Of which grid profit" is the completed buy/sell cycles; "of which unrealised"; "HODL benchmark" is what the same capital would have gained held from the price the run began at. A fee paid in BNB is converted to the quote asset at the fill; one that cannot be priced is counted and the total says "(N fees could not be priced)". With no price heard yet the total says "no price yet" | The screen's grid profit and the account's gain disagreed, because sells of the opening inventory booked nothing, BNB fees were dropped and the unrealised used a chart's or the planner's price (`EPIC-035M`, L2) |
| A parameter the plan cannot run with, on a bot at rest | The parameters come right after the count of what is left, each field with a verdict carrying a stop icon ("Blocks Start") or a warning icon ("Advice") beside its sentence, so the field and its reason are in view together; the chart says "Grid not drawn: <the first refusing verdict>" above itself; a Save stores the parameters as they are and says "Start is still blocked: <the reason>". The status bar is `EPIC-035W`'s | A reason scrolled out of view, a field that does not say it is wrong and a chart that is silent left the owner guessing (`EPIC-035N`, L10) |
| Resume is confirmed after the market moved more than 1 % from the price the ladder was proposed at (or the price cannot be read at that moment) | The bot stays Halted with the reason "proposal_price_moved" and its detail, "the price moved from … to …, more than 1.0 %, since the ladder was proposed; nothing was laid, resume again"; the proposal is dropped and Resume proposes a new ladder at the current price | A ladder's sides and quantities were decided for one price; laying it against another is a different trade, so the user is asked again. The price a resume, a stop's slices and the dust check use is never older than 10 s: older, the book is read (`EPIC-035J`) |
| A request to the exchange fails in transit (a timeout, a reset, a gateway page) | Nothing: reads and cancels are tried again after 0.5, 1 and 2 s. An order's submit is never sent twice: if its outcome is unknown the bot's order is looked up by its client order id, and the bot stops in Error only if that lookup fails too | A repeated cancel is harmless, a repeated submit is a duplicate order (`EPIC-035D`, M3) |
| The exchange rate-limits the app (HTTP 429, `-1003`, `-1015`) or bans its IP (HTTP 418) | No request is sent to that venue while the pause lasts. The bot moves to Halted with the reason "rate_limited" and its detail, "the exchange asked for a pause of N s; resumes by itself in N s", then resumes by itself: it takes its orders off, derives its inventory from the exchange and lays a fresh ladder. A Stop pressed meanwhile wins. A pause over one hour, or five automatic resumes that meet the limit again, leave it Halted with "resume by hand" | The pause is the exchange's, not a fault of the bot, so it is not Error; waiting out exactly what was asked keeps a 429 from becoming a ban (`EPIC-035D`, M3). A Stop that meets a pause stays Stopping and retries after it |
| The fills cannot be read | The Fills panel says why | The venue's order history is a network read |
| The exchange stream that reports fills (the user-data stream) drops, as it does at least every 24 h | Nothing changes on screen while it reconnects (seconds). The bot reconciles against the exchange as soon as the stream is back: a fill that happened in the gap is counted and its counter order is placed, once; with nothing missed nothing is placed. A running bot is reconciled the same way every five minutes while the stream is up | Binance does not replay what a dropped stream missed; trading's stream reconnects with a growing, capped delay whatever failed, and says where it is (`UserStreamHealthEvent`) |
| The stream stays down for more than two minutes | The bot moves to Halted with the reason "the exchange stream that reports fills has been down N s; the ladder was taken off" beside its state, and its resting orders are cancelled. A stream that comes back does not resume it; Resume re-plans from the exchange as for every other halt | A bot that cannot see its own fills must not keep orders on the exchange; resuming a grid is the owner's decision (D13) |
| After a gap the exchange and the bot's ladder disagree beyond what the missed fills explain (for example a partly filled order the stream never reported) | The same Halted state, reason "inventory mismatch: saved … against … derived from the exchange", after a second reconcile confirmed it; the ladder is taken off | A disagreement the bot cannot explain is not guessed at; the second run lets a fill that arrived while the first read reach the ladder first |
| The computer sleeps or hibernates and wakes (the app notices the clocks jumped by more than a minute beyond their 15 s beat) | Within a beat of the wake the user is told once, "The computer was asleep N h M min; K bots re-checked against the exchange". Each bot reconciles as after a stream gap (a fill that happened in the night is counted and its counter order placed, once) and its stop loss and take profit are judged against a price read from the exchange just then, not the last one heard: a stop loss crossed in the night stops the bot and sells the base now. If the exchange cannot be reached yet the price is asked again every 15 s, four times; after that the price-feed rule halts a bot that hears nothing | A sleeping process sees no fill and no price; the last tick is hours old and the streams died with the connection. Windows counts sleep in its monotonic clock and Linux does not, so the wall clock is read too (`EPIC-035I`) |
| A second copy of the app is started on the same data (the first is running) | The second opens read-only: its window title ends "(read-only)", a notice says "This copy is read-only" and why, and the Bots tab lists the bots as the first copy saved them. Start, Pause, Resume, Stop and Confirm resume are refused by name, with that reason; Create, Edit, Delete and Change venue fail the same way because the bot store refuses every write; no order is placed or cancelled, no bot file is written, and no bot is restored, watched or reconciled by this copy. When the first copy exits, the next start is the first | Two copies would lay two ladders on one account and answer the same fills twice; the best case is a `DUPLICATE_LEVEL_ORDER` halt. The lock is the operating system's, so a crashed first copy frees it (`EPIC-035H`) |
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
- Seeing a fill the instant it happens while the stream is down: after a gap the bot catches up to
  the fills it missed (a partial fill of a still-open order included, `BUG-188`), lays again once
  an order cancelled while the stream was down (`BUG-187`), and halts when what remains cannot be
  explained. A fill the stream delivers twice, or that the catch-up already applied from history,
  is counted once, by the exchange's trade id (`EPIC-035P`); an order the bot sent but never saved
  is adopted with what it had already executed (`EPIC-035Q`).
- Telling the user on screen that the bot's file cannot be written: the screen used to read the file, which is what failed; it now reads the bot's newest state even when its write failed (`NotifyingBotStore`). A running bot no longer trades on in the meantime: three failed saves in a row pause it (owner decision D6, `EPIC-035G`).
- Watching the stop loss and take profit while the app is closed: nothing runs then, which is why
  closing asks first. An exchange-side stop is `EPIC-026K`.
- Halting a bot that is Stopping when the feed goes quiet: a stop sells and cancels without a price,
  and a halt would turn the user's Stop into a resume that re-plans a ladder.
- A price the venue pushes but that is wrong: the watch measures the feed's age, not its truth.
- The Fills panel reads the four newest pages of the symbol's order history since the run started;
  it says so when there is more.
- The chart's overlay for a running bot is its plan's levels; level states and fills are in the
  Orders and Fills panels, not on the chart.

## 7. Ports and modules it exercises

- bots: `ListBotsQuery`, `GetPlannerMarketQuery`, `GetVenueConnectionQuery`, `GetBotReadinessQuery`, `GetExchangeFactsQuery`, `GetBotFillsQuery`, `RunGridBacktestQuery`; `CreateBotCommand`,
  `EditBotCommand`, `StartBotCommand`, `PauseBotCommand`, `ResumeBotCommand`,
  `ConfirmBotResumeCommand`, `StopBotCommand`, `DeleteBotCommand`, `ChangeBotVenueCommand`; `IBotKindCatalog`,
  `IBotKind`; `BotChangedEvent`; `BotChart`, `BotTickFeed`; `UserStreamWatch` (hears `UserStreamHealthEvent`); `SleepWatch` (reads the clocks; `IFreshPriceReader`).
- trading: `IVenueTradingPorts` (`IOrderEntryTerms`, `IAccountActivity`, `IAccountSnapshot`, `ITradingSession.lease_holder`, `ITradingSession.earlier_runs_inventory`), `IVenueAccounts` / `IVenueAccountReader` (`VenueAccountSnapshot`, `ConnectFailure`), `OwnerBudgetCaps`, `UserStreamHealthEvent` (`UserStreamState`), `IAccountHistoryReader.discard_remembered`.
- market_data: `IHistoricalKlines`, `IMarketDataSync`, `IMarketStream`, `MarketDataCandleFeed`,
  `IMarketDataRepository` (the 1-second klines, streamed); `IMarketDataSources` and `IMarketStream`
  for each bot's own price stream (`BotPriceWatch`, `EPIC-035A`).
- core: `ICloseObjections`, `ICommandDispatcher`, `IInstanceAccess` (read-only copy, `EPIC-035H`).

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| The list, legal actions per state, Refused disables Start, save before start, Stop and Delete ask, New bot creates a DRAFT, one action at a time, stale answers dropped, a write elsewhere re-read | `tests/unit/modules/bots/ui/bots_screen/test_bots_presenter.py` | unit (real bots graph) |
| Every state's legal actions and the reason for every disabled one | `tests/unit/modules/bots/ui/bots_screen/test_bot_action_rules.py` | unit |
| Verdict lines with threshold and measured value; no start without market numbers | `tests/unit/modules/bots/ui/bots_screen/test_bot_plan_judge.py` | unit |
| Every constraint at and around its boundary; the key and the opening buy read the account; each violation blocks exactly when D7 says | `tests/unit/modules/bots/domain/grid/test_grid_checks.py` · `test_grid_account_checks.py` · `test_grid_constraints.py` | unit |
| What is left before Start is one assessment: each step's items, status and words; the Start use case refuses exactly what the query reports, before any order and before saving; Save and start judges the edits as they would be saved | `tests/unit/modules/bots/application/test_bot_readiness_assessment.py` · `test_start_bot_readiness.py` · `test_other_active_bot_and_budget.py` | unit (real reader over fakes) |
| The Plan shows the three steps and each item with its reason and fix; Bots → Fix next item; Save and start is the primary action, off with "N things left"; a bot with a run shows no progress; a click refused in the list's words | `tests/unit/modules/bots/ui/bots_screen/test_bots_run_step.py` · `test_readiness_words.py` · `test_save_and_start_command.py` · `test_bot_readiness_fsm_matrix.py` | unit (real bots graph) |
| The exchange rules as pure functions: the three states of the snapshot, each rule at and around its boundary, the advisory, a further rule as one line in `RULES` | `tests/unit/modules/bots/application/test_exchange_rules.py` | unit |
| The exchange snapshot read over the venue's ports: free and locked balances, own orders apart from others, a failed read unavailable and never empty | `tests/unit/modules/bots/application/test_exchange_facts_reader.py` | unit (fakes) |
| A Resume is refused before anything is queued when the free base cannot cover its SELLs; a paused bot's resume is not judged | `tests/unit/modules/bots/application/test_resume_bot_readiness.py` | unit (real reader over fakes) |
| The screen loads the snapshot off the UI thread: checking, unavailable, refresh on demand and on a state change, a late or replaced answer dropped, cancelled on deselection and shutdown, the Resume tip | `tests/unit/modules/bots/ui/bots_screen/test_bots_exchange_check.py` | unit (real bots graph) |
| The snapshot, the warning before Start, a short quote and a Resume whose base was moved, on the composed app | `tests/integration/modules/bots/test_exchange_backed_readiness_on_the_fake_exchange.py` | integration (fake exchange) |
| From a new bot to a running bot through the three steps on the composed app; Save and start with edits; a capital above the account listed before the click | `tests/integration/modules/bots/test_bots_tab_drives_the_executor.py` | integration (fake exchange) |
| The lease's holder is readable without claiming | `tests/unit/modules/trading/contracts/test_trading_session_contract.py` | unit (contract suite, real and fake) |
| A violated constraint is said on its field with its number, blocking apart from advice; every code decides its field; the plan's levels are drawn on the chart and follow each edit | `tests/unit/modules/bots/ui/kinds/test_grid_field_errors.py` · `tests/unit/modules/bots/ui/bots_screen/test_bots_design_step.py` | unit (real bots graph) |
| Start with the price outside the range (below refused, above advised, the bounds themselves neither); levels that round to one price are refused; a running bot publishes one event per change of place against the range, once per exit and re-armed on return | `tests/unit/modules/bots/domain/grid/test_grid_range_checks.py` · `test_grid_level_checks.py` · `tests/unit/modules/bots/application/services/test_grid_range_exit.py` · `tests/unit/modules/bots/application/test_start_bot_readiness.py` | unit |
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
| Every bot that is not at rest owns its venue's price stream; a stop loss is watched with no chart, in Recovering and Starting; a quiet feed halts with a named reason and a tick does not resume; the stream is released at rest; two bots share a symbol | `tests/unit/modules/bots/application/services/test_bot_price_watch.py` · `test_bot_price_watch_checks.py` · `test_grid_executor_exit_states.py` · `test_grid_executor_price_age.py` · `tests/unit/modules/bots/domain/grid/test_price_is_stale.py` | unit |
| The price a bot acts on carries its age and is read from the book when older than 10 s; a resume confirmed after a move beyond 1 % is refused, not laid | `tests/unit/modules/bots/application/services/test_grid_executor_reference_price.py` · `tests/unit/modules/bots/domain/grid/test_reference_price.py` | unit |
| A transient failure retries for reads and cancels and never for a submit; a 429 / 418 closes the venue for the stated pause with no request sent; one session per venue is reused (a steady order costs 6 requests, measured) | `tests/unit/modules/trading/adapters/binance/test_exchange_call_policy.py` · `test_exchange_call_failure.py` · `test_rate_limit_gate.py` · `test_resilient_session.py` · `test_venue_sessions.py` · `test_rate_limited_error_of.py` · `tests/integration/infrastructure/binance/test_exchange_resilience_against_fake_server.py` · `tests/integration/application/test_order_request_cost_against_fake_server.py` | unit · integration (fake exchange) |
| A rate-limited order halts the bot with a named reason, a pause scheduled by the retry scheduler resumes it, a stop waits out the pause | `tests/unit/modules/bots/application/services/test_grid_executor_rate_limit.py` · `test_bot_order_gateway_rate_limit.py` | unit (real executor over the simulated venue) |
| The price watch is wired at boot, on every bot change and at shutdown; a bot, a restart and a silent feed on the composed app | `tests/integration/modules/bots/test_bots_module_price_watch_wiring.py` · `tests/integration/modules/bots/test_a_bot_owns_its_price_stream_on_the_fake_exchange.py` | integration (fake exchange) |
| A Grid starts, fills, pauses, stops and restarts against the fake exchange | `tests/integration/modules/bots/test_grid_bot_against_fake_server.py` | integration |
| A task that placed orders and ends Halted or Error takes them off the exchange, a parked bot is not cancelled again, and a refused confirm-resume leaves nothing resting | `tests/unit/modules/bots/application/services/test_grid_task_guard.py` | unit (real executor over the simulated venue) |
| Stop is declared in Stopping; a stop that waits retries on the bounded schedule, shows its reason and the orders still open, is never Stopped early, and gives up with a named next action; the retry scheduler is verified in both implementations | `tests/unit/modules/bots/domain/test_bot_lifecycle_fsm_matrix.py` · `tests/unit/modules/bots/application/services/test_grid_executor_stop_retry.py` · `tests/unit/modules/bots/contracts/test_bot_retry_scheduler_contract.py` | unit |
| A restored bot's boot report (counts, unreadable, no fault), the cleanup a cut-short start owes (paid, waiting for trading, refused), and that `boot()` runs both | `tests/unit/modules/bots/application/services/test_grid_boot_recovery.py` · `tests/unit/modules/bots/ui/test_recovery_report_is_visible.py` · `tests/integration/modules/bots/test_bots_module_wiring.py` | unit · integration (module graph) |
| A fill missed in a stream gap places its counter order once after a reconnect or a periodic check; with nothing missed nothing is placed; a disagreement halts only on a second run; a stream down past the limit halts and parks the ladder, and its return resumes nothing | `tests/unit/modules/bots/application/services/test_grid_reconciler_gap.py` · `test_user_stream_watch.py` · `tests/integration/modules/bots/test_a_user_stream_gap_on_the_fake_exchange.py` · `test_bots_module_wiring.py` | unit · integration (fake exchange) |
| The user-data streams (Spot and Futures) retry any failure with a growing, capped, jittered delay, start again after their task ended, publish connecting, connected, reconnecting and stopped, and never log a signed URL | `tests/unit/modules/trading/adapters/binance/test_user_stream_supervisor.py` · `spot/test_spot_user_data_stream_resilience.py` · `test_futures_user_data_stream_resilience.py` | unit |
| A clock gap reconciles every bot as after a stream gap and meets its stop loss and take profit with a fresh price (a fill missed in the night; a stop loss crossed in it; a take profit crossed in it); the threshold at and over its boundary; a Linux suspend the monotonic clock did not count; a wall clock set back; a price the exchange will not give is retried, bounded | `tests/unit/modules/bots/application/services/test_sleep_watch.py` · `tests/unit/modules/bots/adapters/test_venue_fresh_price_reader.py` · `tests/integration/modules/bots/test_sleep_watch_wiring.py` | unit · integration (real container) |
| The first copy on a data root is writable and a second is read-only (the bots module boots none of its watches, saves no bot, starts none; a venue's trading client places and cancels nothing, and a Futures venue changes no leverage or margin mode); the lock is released at a clean exit and by the OS when the process dies; two data roots never meet; only the entry points take the lock | `tests/unit/infrastructure/single_instance/test_instance_access.py` · `tests/integration/infrastructure/test_the_lock_dies_with_the_process.py` · `tests/unit/modules/trading/test_read_only_trading_client.py` · `tests/unit/modules/bots/application/services/test_read_only_bots.py` · `tests/integration/modules/bots/test_a_second_instance_on_the_bots_module.py` · `tests/unit/shell/test_a_second_instance_on_the_composed_app.py` · `tests/unit/architecture/test_only_the_entry_points_take_the_instance_lock.py` · `tests/sanity/test_self_check_process.py` | unit · integration (a real second process) · sanity (the real entry point) |
| A fill reported twice (the stream, or the stream after a catch-up) is counted once; the same trade id on another order, and fills with no trade id, are separate fills | `tests/unit/modules/bots/application/services/test_grid_duplicate_fill.py` · `test_applied_fills.py` · `tests/unit/modules/trading/adapters/binance/test_venue_event_emitter_trade_id.py` | unit (real executor over the simulated venue) |
| An order sent but never saved is adopted at its level with the quantity it had already executed, so the reconcile that adopts it does not halt | `tests/unit/modules/bots/application/services/test_grid_reconciler_adopts_executed.py` | unit (real executor over the simulated venue) |
| A transport failure of any trading request logs no signature, listen key or API key, whoever logs it | `tests/unit/modules/trading/adapters/binance/test_no_signed_url_in_a_transport_failure.py` · `test_binance_client_builder.py` | unit (the real client over a fake transport) |
| A registration derives from the history as it is now, not from a 15-second memory | `tests/unit/modules/trading/application/session/test_register_owner_budget.py` · `tests/unit/modules/trading/adapters/binance/test_cached_history_reader.py` | unit |
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
| A filter the exchange changes mid-run halts the bot with `exchange_terms_changed` and the old and new values (and a delisting with `symbol_delisted`); the read is made from the exchange, not the day-old catalog; a failed read halts nothing | `tests/unit/modules/bots/application/services/test_grid_terms_refresh.py` · `tests/unit/modules/trading/application/queries/test_get_symbol_order_rules.py` · `tests/unit/modules/trading/application/orders/test_order_entry_terms_service.py` | unit |
| A Stop pressed during a Start lays no further order and ends the bot | `tests/unit/modules/bots/application/services/test_grid_stop_during_start.py` | unit (real executor, serial queue) |
| A mainnet Start nobody confirmed is refused by the use case itself, before anything is read | `tests/unit/modules/bots/application/test_start_bot_real_money.py` | unit |
| Orders already open on the symbol are counted by the planner and advised against the open-order limit; a failed read leaves the count unread | `tests/unit/modules/bots/application/test_planner_foreign_orders.py` · `tests/unit/modules/bots/domain/grid/test_grid_checks.py` | unit |
| Shutdown joins a stuck worker with a timeout and says so | `tests/unit/modules/bots/adapters/test_thread_bot_work_queue.py` | unit |
| A BUY at the top and a SELL at the bottom owe no counter | `tests/unit/modules/bots/domain/grid/test_grid_reactions.py` | unit |
| A symbol that is not TRADING refuses a start and a resume, pauses a running bot whose order is refused for it (the order held, the ladder resting), halts for a delisting, and still cancels on Stop | `tests/unit/modules/bots/application/services/test_grid_symbol_status.py` | unit (real executor on a simulated venue) |
| An API key the exchange rejects halts the bot with `key_rejected` (on an order's gate, on a raised refusal, at Start, at Stop, at an exit slice and at a Resume's cancel) without a cancel, and a bot with orders finds a revocation by its own probe, on an interval, and not on a network fault | `tests/unit/modules/bots/application/services/test_grid_key_rejected.py` · `tests/integration/modules/bots/test_a_revoked_key_on_the_fake_exchange.py` | unit; integration (composed app on the fake exchange) |
| Total PnL is realised plus unrealised, a sell of the opening base and an exit slice book realised PnL, the HODL benchmark is the capital held from the start price | `tests/unit/modules/bots/domain/grid/test_grid_pnl.py` · `tests/unit/modules/bots/ui/bots_screen/test_bot_facts.py` | unit |
| A BNB-paid fee is converted at the fill, an unpriceable one is counted and said, and the bot saves the price it heard at most every 30 s | `tests/unit/modules/bots/application/services/test_grid_earnings_on_the_executor.py` · `tests/unit/modules/bots/application/services/test_grid_runtime_codec.py` | unit (real executor on a simulated venue) |
| An invalid parameter is explained on its field, in view, with a sign; the chart says why no grid is drawn; a Save says why Start is still blocked | `tests/unit/modules/bots/ui/bots_screen/test_bots_invalid_parameters_are_explained.py` | unit (real presenter and view) |
| The list and the bot's state line say Paused with `storage_failure` while every write still fails | `tests/unit/modules/bots/application/test_unsaved_bot_state_is_visible.py` | unit |
| Three failed saves in a row pause a running bot with `storage_failure` (its orders rest, counter orders are held); two failures then a success change nothing; Resume after the store recovers runs the bot again and places what was held; Resume while the store still fails is refused and leaves it Paused | `tests/unit/modules/bots/application/services/test_grid_storage_pause.py` | unit |
