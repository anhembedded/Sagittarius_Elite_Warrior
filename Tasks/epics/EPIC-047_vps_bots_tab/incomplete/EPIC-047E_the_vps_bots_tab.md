# EPIC-047E — The VPS Bots tab shows and controls the host's bots with the Bots tab's own classes

**Status:** 🔵 Backlog
**Source:** the owner's request of 2026-10-24: *"2 modules share everything"* (charter O4) and the delegation settled as G2, G3 and G5; charter objectives O1, O2, O3, O5, O7 and acceptance AC1, AC3, AC4, AC7, AC8, AC10 (the owner, 2026-10-27: the VPS tab connects to nothing at Binance).
**Risk:** 🔴 — it sends real-money commands from the desktop to the host; the tab must show which host and which account it is on, and refuse commands while disconnected.
**Complexity:** L — a second backend for the same screen, the connection line, the read-only state and the "Add to VPS" flow.
**Epic:** [EPIC-047](../README.md)
**Depends on:** [EPIC-047D](EPIC-047D_the_desktop_transport_profiles_and_the_options_page.md) (the transport and profiles), [EPIC-047H](EPIC-047H_the_host_serves_market_data_and_refreshed_facts_to_the_bridge.md) (the host serves the market data and the refreshed exchange facts; the tab reads nothing at Binance, [decision of 2026-10-27](../DECISION_2026-10-27_a_vps_bot_reaches_binance_only_through_the_vps.md)), [EPIC-048A](../../EPIC-048_ui_reaches_the_application_through_its_doors/completed/EPIC-048A_the_doors_rule_and_its_guard.md) and [EPIC-048B](../../EPIC-048_ui_reaches_the_application_through_its_doors/incomplete/EPIC-048B_the_bots_screen_through_the_doors.md) (the screen reaches the application only through the doors)

---

## 1. Context and problem
The owner added a rule on 2026-10-27: in the VPS tab all Binance data comes through the VPS and the app connects to nothing at Binance. Today the detail and the chart reach Binance through the desktop's own container (the table in the [decision record](../DECISION_2026-10-27_a_vps_bot_reaches_binance_only_through_the_vps.md)'s §1), so 048B's second pull request, which removes the container reach, and 047H, which gives the host the missing sources, are both prerequisites. Until 047H lands, this task may build everything that reads no market data and no refreshed facts (the connection line, the commands, the list and the detail from the bot files and the host-facts file).

After EPIC-048B the Bots screen receives host facts through queries and events only, and the pure assessment runs on the desktop. A remote dispatcher and event stream over the transport of 047D can therefore stand behind the same screen. De-risk R1 rendered the real view from six wire-borne reads with the detail equal to the in-process one. The owner's pain (charter §1.2): the VPS is read through SSH text, plans reach it by export, `scp` and `M bot add`, and the desktop and the VPS read different exchange accounts.

## 2. Acceptance criteria
- [ ] **Two tabs, one set of classes (AC7):** the Bots tab and the VPS Bots tab are built from the same view, presenter and widget classes, on different backends; an architecture test proves it by class identity, not by name.
- [ ] **AC1:** for each VPS bot, every field of `M bot show` appears in the tab with an identical value, checked side by side on the owner's VPS: list, state, earnings, chart lines (ladder, SL, TP, trigger), Checks, Plan rows (loss at stop, result at take profit, liquidation estimate), orders and fills.
- [ ] **AC3:** each Bots tab action (start, pause, resume, confirm resume, stop, edit, add, delete, move, arm or disarm a strategy) works on a VPS bot through `IHostControl`, with the same verdict and an audit line as the same `M bot …` command; the host's own answer is shown.
- [ ] **AC4:** a mainnet start or resume without the venue confirmation is refused by the host, and the tab asks "Type futures_mainnet to confirm" as the CLI does (G3); no real-money rule lives in the tab.
- [ ] **O5, honest state:** the tab always shows the host name, the exchange account (masked), connected or not, and the age of its data ("nathan-warrior · Futures Mainnet account …1a2b · connected · updated 2 s ago"); when disconnected it shows the last data with its age, refuses commands and reconnects by itself.
- [ ] **AC6:** a cut during a command and while idle leaves the bots unaffected; after the reconnect the tab shows whether the command was carried out, read from the host's audit; no command is sent twice.
- [ ] **Add to VPS:** a plan designed in the Bots tab lands on the VPS as DRAFT with no file copied by hand; the VPS's own Checks run against the VPS's account (charter Scenario 2).
- [ ] **AC2:** a fill on the VPS appears in the tab in ≤ 5 s, measured fill timestamp against the tab's update.
- [ ] **AC10, no Binance contact:** the VPS tab makes no connection to Binance, signed or public. (a) A static guard: the closure of the tab's composition reaches no Binance client (`trading/adapters/binance`, `market_data/adapters/binance`, the gateway's session factories), baseline 0 and only falling. (b) A runtime test: the tab composed over a fake host and a recording fake exchange makes zero exchange calls and opens no non-loopback connection, while the Bots tab composed in the same test makes some. Every fact the tab shows (account facts, orders, positions, mark price, live ticks, chart candles, filters, brackets, venue choices) is read from the host over the bridge, with the age it was read; the chart's candles and live candle come from 047H's files.
- [ ] **Offline, no fallback (decision D5):** with the link cut the tab shows "disconnected, data as of …", the chart freezes at its last candle and says so, commands are refused, and a test proves no Binance call is made to fill the gap. A fact the host never published reads "not published by the host".
- [ ] **Scope of the tab (decision D6):** the Backtest workbench and any control that reads Binance directly (the exchange symbol list, live suggestions from exchange info) are hidden or read-only; "Add to VPS" from the Bots tab is the way to create a bot.
- [ ] **AC8:** the Bots tab's existing tests are unchanged and green and its frames are unchanged; the full gate is green.
- [ ] A version difference refuses the link and shows "the VPS host runs build X, this desktop runs Y: run `sudo sew-update`".

## 3. Design
The remote backend is one more implementation of the screen's gateway ([EPIC-048C](../../EPIC-048_ui_reaches_the_application_through_its_doors/incomplete/EPIC-048C_presenters_receive_a_narrow_gateway.md) provides the shape for the Bots screen; if 048C is not done, 047E uses the screen's existing dependencies object with the same seam). Reads and events travel as in the remote link record; commands through `IHostControl`. The screen is read-only while disconnected. One host at a time with a picker over the profiles (G2).

## 3a. Reuse
`BotsView`, `BotsPresenter`, the connection line widgets and the screen registry (`ScreenDescriptor`): `used`, with the tab a second descriptor. `.claude/rules/capabilities.md` rows are listed at start; no second copy of any widget (O4). The chart takes a host-backed `ICandleFeed` (history from the host, live candle from the host's file) in place of `MarketDataCandleFeed`, and `BotTickFeed` is fed from the bridge's events and not from the desktop's market stream.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/…` | a second descriptor and the remote backend wiring; the connection line |
| `src/…` (remote gateway/dispatcher adapter) | the remote implementation over 047D's transport |
| `tests/…` | the AC7 architecture test; the fake-host integration tests for AC1, AC3, AC4, AC6; the AC10 guard and the zero-call runtime test |

## 5. Testing
Tier: unit, architecture and offscreen UI on a fake host; then the full gate. AC1, AC4 and AC2 are also checked on the owner's testnet bots, then the mainnet dry run, and recorded. Not run.

## 6. Docs touched
`Docs/MODULES/bots/` (building blocks and runtime: the second backend, the connection line), `Docs/SPEC/` (a use case for the VPS tab, one file per use case), `Docs/LEARNING/` page on the design with [EPIC-047G](EPIC-047G_the_runbook_for_the_vps_link.md).

## Implementation notes (written when done)
Not written: not started.
