# ADR — In the VPS Bots tab the desktop makes no connection to Binance; the host fetches, the bridge only reads

**Epic:** [EPIC-047](README.md)
**Date:** 2026-10-27
**Status:** Proposed — D1, D2, D5, D6 and D7 are accepted defaults the owner may veto; D3 and D4 are the owner's to decide and are not defaulted (O1, O2)
**Decided by:** D1 by the owner (quoted in §1). D2, D5, D6, D7 by the author session under ONBOARDING §7 ("Settle an owner decision that carries a recommendation"), each checked in §2a. D3 and D4 touch real-money behaviour or REST weight on the account and IP the bots trade on, so they wait for the owner.
**Supersedes / superseded by (optional):** Replaces D3 of [the 2026-10-26 record](DECISION_2026-10-26_the_bridge_revision_and_the_unbuilt_venue.md) ("exchange facts stay as fresh as the last read") once the owner accepts D4; until then that D3 stands. Reads with [the remote link record](DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md) D4 (G7a), which D2 keeps.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree at commit `783462a` (master-warrior after #739), cited by path and symbol |
| 🔵 Proposed | an option awaiting a decision; not accepted |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Default, owner may veto | settled on its recommendation under ONBOARDING §7; its Constitution check (§2a) shows every invariant passes; reverted if the owner vetoes |
| ❓ Open | the owner decides; blocks the named phase |

## 1. Context

**The requirement.** The owner, 2026-10-27: *"Khi vào bot VPS thì tất cả dữ liệu từ Binance phải được lấy thông qua VPS. Bot sẽ không kết nối bất cứ gì tới Binance nữa."* (In the VPS bots tab, all Binance data must come through the VPS; the app connects to nothing at Binance any more.) Read as: in the VPS Bots tab the desktop opens no connection to Binance, signed or public. Everything Binance-derived the tab shows for a VPS bot reaches the desktop over the bridge, from the host.

**What the Bots detail and its chart touch on Binance today** (✅ read in the tree; the tab is built by `src/modules/bots/ui/bots_screen/bots_dependencies.py` → `bots_dependencies_for` from the desktop's own container):

| What the tab shows | Read through | Binance contact on the desktop today | Host source after this record |
| :--- | :--- | :--- | :--- |
| Bot list, Plan, state, earnings | `ListBotsQuery`, `GetBotQuery` (`get_bot`, `list_bots` handlers): the bot store only | none | the bridge's bot files (047C), unchanged |
| Account facts, position, resting orders, leverage brackets, margin | `GetExchangeFactsQuery` → `IVenueFacts` (`futures_facts_reader.py` → `FuturesFactsReader`, `exchange_facts_reader.py` → `ExchangeFactsReader`): `account_snapshot`, `account_activity.open_orders`, `order_entry_terms.futures_setting_for` / `leverage_brackets_for` | signed REST (balance, `positionRisk` v3, open orders, symbol config, brackets) | host-facts file, `VenueSnapshot` (047B); freshness is D4 |
| Plan risk figures | `GetPlanRiskFactsQuery` → the same `IVenueFacts` | as above | as above |
| Filters, fees, mid price, daily ATR and Bollinger | `GetPlannerMarketQuery` → `planner_numbers.py` → `read_planner_numbers` (`order_entry_terms`: exchange info, commission rate, `best_bid_ask_for`) and `DailyAtrReader` over the local candle store | REST: exchange info, commission rate (signed), `bookTicker`; the daily candles come from the desktop's store, which is filled by a REST kline sync | **new**: the planner's inputs published by the host (D3, D4) |
| Orders and fills tables | `GetBotFillsQuery` → `IVenueTradingPorts` account history | signed REST, weight 20 per day window (`i_account_history_reader.py`) | **new**: the host serves it (047H); today's host publishes none |
| Venue choices, connection state, key saved | `venue_choice.py` → `_connection_of` → `IVenueContexts.get(venue).credentials_provider`; `GetVenueConnectionQuery` → `IVenueAccounts` | the desktop's **own** key store, and a signed account check | host-facts: key state (047C `IVenueKeyStates`) and the venue's connection state |
| Run facts (leases, enabled venues, caps) | `GetBotRunFactsQuery` → `BotRunFactsReader` | none (in-process) | host-facts (047B) |
| Chart history | `MarketDataCandleFeed` (`market_data/contracts/market_data_candle_feed.py`): `sync` and `load_older` call `IMarketDataSync` (REST klines); `load_history` reads the local store | REST klines | **new**: the host's candles (D3) |
| Chart live candle and last price | `start_stream` → `IMarketStream` → `MarketStreamService` (a public kline websocket); `bots/ui/bot_tick_feed.py` → `BotTickFeed` re-emits `MarketTickEvent` | public websocket | **new**: the host's live candle (D3) |
| Mark price | `GetMarkPriceQuery` (trading) → `mark_price_reader` (`premiumIndex`); the screen never dispatches it itself (grep of `src/modules/bots`), the host's exit watch reads it each beat (`i_mark_source.py`) | public REST, reached inside the facts and planner reads | **new**: the value the host already reads each beat (D3) |
| Precision of orders and fills, the symbol picker | `FilterPrecisions` over `contexts.get(venue).metadata_cache`; `ISymbolCatalog` | REST exchange info | **new**: static exchange info published by the host (D4) |
| Backtest workbench | `workbench_ports` → `candles(venue).sync` | REST klines | not offered in the VPS tab (D6) |

Not yet read, so a gap and not a fact: whether a `VenueSnapshot` carries the mark price, and whether the headless host already streams a candle for every bot symbol. Both are the first step of 047H.

**What the host already has, and the numbers on its account** (✅). The host is the only exchange client of its keys. `ExchangeCallPolicy` closes the venue's weight gate for routine reads at 70 % of the per-minute weight and for everything at 90 % (`trading/adapters/binance/exchange_call_policy.py` → `SOFT_WEIGHT_RATIO`, `HARD_WEIGHT_RATIO`), against 2 400 weight per minute for a Futures IP (`venue_sessions.py` → `FUTURES_WEIGHT_LIMIT`) and 6 000 for Spot (`SPOT_WEIGHT_LIMIT`). That is 1 680 and 2 160 on Futures; the 480 between the lines is the reserve for the three reads that guard an exit (`request_priority.py` → `RequestPriority.EXIT_GUARD`). The three reads cost an idle minute of 96, 240 and about 780 weight at 1, 5 and 20 bots (`BOT-226`, in the same file), so 20 bots already hold about a third of a Futures IP. Per-read weights the code records: `positionRisk` v3 5, multi-assets mode 30 (cached five minutes), `premiumIndex` 1, account history 20 per day window.

**Why the 2026-10-26 D3 no longer holds.** It left exchange facts "as fresh as the last Start, Resume or screen read". The screen read was the *desktop's* read: once the VPS tab reads nothing from Binance, no screen load reaches the exchange, and on the host only a Start or a Resume reads these facts. A running bot's account facts and orders shown in the tab would be as old as its last Start, which can be days. On a real-money host that is a stale picture that looks live. So D3 needs an answer, and the answer costs REST weight.

**Settled earlier and kept.** The bridge calls no exchange and loads no key (remote link record D4, G7a; `Docs/MODULES/bots/07-deployment.md`). The host listens on no socket (AC5). The host stays the single writer and the single exchange client.

## 2. Decisions

| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **The VPS Bots tab opens no connection to Binance, signed or public.** Every Binance-derived fact it shows comes from the host over the bridge: account facts, orders, positions, mark price, live ticks, candles, exchange info (filters, brackets, symbols), venue choices. The rule is a charter objective (O7), a constraint and acceptance criterion AC10. | Accepted | 🟢 User decision (quoted in §1) | Every row of the §1 table marked **new** becomes work on the host (047H) before the tab (047E) can show it. The Bots tab (local) is unchanged and keeps its own Binance reads (AC8). |
| D2 | **The host fetches; the bridge only reads.** The bridge keeps calling no exchange and loading no key. New data reaches it as files the host writes (owner-only, atomic, `heartbeat_s`, a revision), read the way `state/host-facts.json` is read. No new socket on the host. | Accepted | 🤖 Default, owner may veto | The earlier rule needs no change: the requirement says the *desktop* does not connect, and the host already may. One Binance client per key and IP stays (P3). Cost: the host grows a writer for market data (D3). |
| D3 | **Market data (candles, live candle, last price, mark price, planner inputs) is served by a recorder on the host that writes files; the bridge tails them.** Closed candles are read from the host's own candle store, read-only; the forming candle, last price and mark price are one small file written at most once a second. The recorder reuses the host's existing stream and the mark read it already makes each beat, and opens a second connection only if 047H shows the host has none to reuse. | ❓ Open: the owner decides (O1) | Pending | Touches REST weight on the trading IP (backfill) and adds a recorder to the real-money host. Options and weights in §3. |
| D4 | **Exchange facts are refreshed by the host on a schedule, bounded by a weight ceiling, plus one on-demand refresh from the tab.** Proposed: a bot with exposure (RUNNING or PAUSED with a position or resting orders) refreshed every 60 s; static exchange info once at start and daily; refreshes are `RequestPriority.ROUTINE` so they wait at the 70 % line and never use the exit reserve; the whole refresh stays under **5 % of the venue's minute weight (120 on Futures, 300 on Spot)** and its interval stretches to hold that; an on-demand refresh is a new verb through `IHostControl`, at most one per bot per 10 s, judged by the host. | ❓ Open: the owner decides (O2) | Pending | Real REST load on the account and IP the bots trade on, and a new verb on the real-money control door. Without it the tab shows facts as old as the last Start (§1). Figures in §4. |
| D5 | **Offline: the VPS unreachable shows "disconnected, data as of …" and the tab never falls back to Binance.** Last data stays on screen with its age, commands are refused, reconnection is automatic. A fact the host never published shows "not published by the host", not an empty value and not a direct read. | Accepted | 🤖 Default, owner may veto | Same as charter AC6, now also for market data; the chart freezes at the last candle and says so. A bot on the VPS is unaffected. |
| D6 | **The VPS tab offers only what the host can serve.** The Backtest workbench and any control that reads Binance directly (the symbol picker's exchange list, the Plan editor's live suggestions from exchange info) are hidden or read-only in the VPS tab in v1; a plan is designed in the Bots tab and sent with "Add to VPS" (charter Scenario 2), where the VPS's own Checks run against the host's facts. | Accepted | 🤖 Default, owner may veto | The backtest stays on the desktop, as the charter's out-of-scope list says, but in the Bots tab. The cost: editing a plan's symbol in the VPS tab needs the host's published symbol list (D4's static exchange info), so v1 edits parameters and not the symbol. |
| D7 | **A guard holds D1.** (a) A static guard: the modules that build the VPS tab import no Binance client: the closure of the VPS tab's composition may not reach `trading/adapters/binance`, `market_data/adapters/binance` or the gateway's session factories (the `binance_gateway/contracts` value types, such as `TradingVenue`, stay allowed); baseline 0, it only falls. (b) A runtime test: the VPS tab composed over a fake host and a recording fake exchange makes **zero** exchange calls and opens no non-loopback connection, while the Bots tab composed in the same test makes some. | Accepted | 🤖 Default, owner may veto | The static guard alone is green while a port resolved from the container still calls out (P4), so both ship; (b) is the proof the requirement holds. |

## 2a. Constitution check (D2, D5, D6, D7, the defaults)

| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | D7 is the mechanical barrier for D1: an import guard plus a zero-call runtime test. D2 keeps EPIC-038's "no socket" test and AC5. |
| P2 Verify, don't restate | ✅ | The §1 table was read from the tree at `783462a`; what was not read (mark price in a snapshot, the host's stream) is named as a gap and made 047H's first step. The weight figures are the ones the code records; the rest are estimates and are measured in 047H (§4). |
| P3 A copy drifts | ✅ | D2: one exchange client per key and IP, the host; the tab holds no second reader of Binance. The planner and exchange facts are read from the one host snapshot, not re-derived. |
| P4 Green proves only what was tested | ✅ | D7(b) proves absence of calls at run time; D7(a) alone would not. D5 gets a test of the cut link and of the unpublished fact. |
| P5 Apply before you invent | ✅ | D2 mirrors the host-facts file (047B) and the bot-file revision (2026-10-26 D1); the recorder mirrors `HostFactsPublishing` (daemon thread, atomic owner-only write). A relay by socket was not invented (§3). |
| P6 Fix the mechanism | ✅ | The mechanism is "the screen reaches Binance through the container"; D1 and D7 fix the path, not one screen, and EPIC-048B's doors already remove the container reach. |
| P7 Seam now, variant later | ✅ | The bridge's reader sits behind the same revision rule; a live-event relay (A1) or a stream the bridge forwards stays a later variant behind the same wire roots. D6 builds no host-side editing of symbols yet. |
| P8 Ratchets only fall | ✅ | D7(a) starts at baseline 0 and only falls; no guard loosened; the 2026-10-26 D3 is replaced by a bounded rule, not removed without one. |
| P9 Decide alone | ✅ | D2, D5, D6, D7 are decided with a recommendation; D3 and D4 are the only questions that name real money or REST load, and they are the owner's, as ONBOARDING §7 requires. |
| P10 Pyramid and units | ✅ | Leads with the rule; each figure carries its unit (weight per minute, seconds, percent of the venue limit). |
| P11 Prompt-grade artifacts | ✅ | Each row names the symbol, the test and the task that delivers it (§5). |
| Reversible; no real money, dependency, setting, Engine, user data or secret | ✅ for D2, D5, D6, D7 | D2 changes no code; D5 only refuses more; D6 hides controls in a tab not yet built; D7 adds a guard. None moves an order, a limit or a key, adds a dependency or touches the Engine. A veto reverts the row. D3 and D4 do touch REST load and the control door and are therefore not defaulted. |

## 3. Alternatives considered

**How market data reaches the bridge (D3).** The bridge is a short-lived process started by `sshd` per session, so the host cannot push to it without a channel.

| Option | Idea | Weight on the trading IP | Verdict |
| :--- | :--- | :--- | :--- |
| A1 Relay as events | The host publishes ticks and candles as events and the bridge forwards them | none beyond the host's own streams | Needs a host-to-bridge channel: a Unix socket makes the host a listener (the EPIC-038 test and AC5 forbid it), a FIFO per session is new machinery. Lost for v1; stays the variant if a file's latency is not enough |
| **A2 Files the bridge tails** (recommended) | Closed candles from the host's candle store read-only; the forming candle, last price and mark price in one small atomic file, at most once a second | a one-time backfill (about 30 weight per symbol across six timeframes, Binance's published kline weights, unverified) then none: the stream and the mark read already exist | Uses the pattern the host-facts file proved (P5). Disk writes stay small (a few hundred bytes a second per symbol); the bridge numbers a change with its own revision as for bot files. Cost: a recorder on the host |
| A2b One file per window, rewritten each second | Simpler, but 1 000 candles × six timeframes × each symbol rewritten every second | none | Lost: megabytes a second of writes on the real-money host |
| A3 The bridge fetches public data itself | The bridge calls the public endpoints and the stream (no key) | public REST weight shares the *IP* with the bots; each reconnect of the desktop starts a new client and a new backfill | Satisfies the owner's words literally, but breaks the bridge-calls-no-exchange rule for no gain and ties trading-IP load to how often the laptop reconnects. Lost; the variant if A2's recorder proves too heavy for the host |
| A4 The desktop fetches public data | status quo | none on the VPS IP | Rejected by the owner (D1) |

**How fresh the exchange facts are (D4).**

| Option | Behaviour | Added weight | Verdict |
| :--- | :--- | :--- | :--- |
| R1 No refresh (2026-10-26 D3) | A fact is as old as the last Start or Resume | none | Stale for a running bot, which looks live. Safe for the account, wrong for the tab |
| R2 Fixed schedule only | Every active bot every T seconds | rises with the number of bots | Simple, but load grows with bots unless capped |
| R3 On demand only | The tab asks; the host reads | zero while nobody looks | A new verb; a stale tab until someone clicks; weight is bounded by a per-bot minimum interval only |
| **R4 Scheduled under a ceiling, plus on demand** (recommended) | R2 whose interval stretches to hold a weight ceiling, plus R3 | at most the ceiling | The tab is never older than the cadence, the load never exceeds the ceiling |
| R5 Record what the host's watchers already read | Decorate the three `EXIT_GUARD` reads so their answers feed the snapshot | zero | Covers position, mark and protective stops only; balances, brackets and settings stay uncovered. Adopted *inside* R4 as the first source, reducing the scheduled reads |

**Where the owner's rule is read.** *Stricter*: the desktop process loads no Binance code at all in any tab. Lost: the Bots tab needs it (AC8). *Looser*: public data direct, private data through the VPS. Lost: the owner said "bất cứ gì" (anything), and a public tick from the desktop is the connection they ruled out.

## 4. REST weight on the account and IP the bots use (D3, D4)

Basis: Futures IP limit 2 400 per minute, soft line 1 680, hard line 2 160, exit reserve 480; Spot 6 000. All from §1's cited constants.

| Item | Weight | Source |
| :--- | :--- | :--- |
| Today's idle load of the three exit-guard reads | 96, 240, ~780 per minute at 1, 5, 20 bots (4 %, 10 %, 33 % of a Futures IP) | `request_priority.py`, `BOT-226` |
| Proposed refresh ceiling | 120 per minute on Futures (5 %), 300 on Spot (5 %) | proposal, owner decides |
| One facts read of a Futures bot (account, position, resting orders, settings, brackets) | estimate 10 to 20 per bot, to be measured with the used-weight header (`ExchangeCallPolicy.note_used_weight_header`); `positionRisk` v3 is 5 and one whole-account read serves every bot | estimate, unverified |
| Scheduled refresh at 60 s | 5 bots: about 75 per minute (3 %); 20 bots: about 300 would exceed the ceiling, so the interval stretches to about 150 s | estimate, follows from the line above |
| Static exchange info | once at start and once a day, tens of weight | estimate, unverified |
| Candle backfill | about 30 weight per symbol once, then gap fills; streams cost no REST weight | Binance's published kline weights, unverified |
| Peak with the proposal at 20 bots | 780 + 120 = 900 per minute, 37.5 % of the IP, under the 70 % line | arithmetic on the figures above |

Two consequences. The load is **flat in the number of tabs and clients**: today's desktop reads add load on the *desktop's* IP; after D1 only the host reads, on a fixed budget, however many times the owner opens the tab. And a refresh is `ROUTINE`, so while the gate is closed at 70 % it waits and the tab's facts age, while the exit reads keep their reserve: the tab degrades before a stop loss does.

## 5. Open questions

| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | **Owner decides (real-money host, REST load).** Accept D3: a market-data recorder on the host, by files (A2)? Which timeframes does it publish (proposed: those the Bots chart offers) and for which symbols (proposed: the symbols of the stored bots)? | EPIC-047H, 047E | 2026-10-27 |
| O2 | **Owner decides (real-money host, REST load, control door).** Accept D4: refresh every 60 s under a 5 % weight ceiling plus an on-demand verb, or a different cadence or ceiling, or R1 and a tab that says the fact is old? | EPIC-047H, 047E | 2026-10-27 |
| O3 | **Owner decides (REST load).** May the host's first recorder backfill run at host start (about 30 weight per symbol), or only when the first desktop connects? | EPIC-047H | 2026-10-27 |
| O4 | Is D6 acceptable: no symbol change and no backtest in the VPS tab in v1? (A default; listed because it removes a function the Bots tab has.) | EPIC-047E | 2026-10-27 |

Until O1 and O2 are answered, 047H is written but not started, and 047E may build everything that does not read market data or fresh facts (its connection line, the commands, the list and detail from the bot files and host-facts).

## 6. Implementation evidence

| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | [EPIC-047E](incomplete/EPIC-047E_the_vps_bots_tab.md) (AC10), [EPIC-047H](incomplete/EPIC-047H_the_host_serves_market_data_and_refreshed_facts_to_the_bridge.md) | Not started | Not yet verified |
| D2 | EPIC-047H | Not started | Not yet verified; the bridge's "calls no exchange" test (047C) must still pass |
| D3 | EPIC-047H | Not started, waits for O1 | Not yet verified |
| D4 | EPIC-047H | Not started, waits for O2 | Not yet verified |
| D5 | EPIC-047E | Not started | Not yet verified |
| D6 | EPIC-047E | Not started | Not yet verified |
| D7 | EPIC-047E | Not started | Not yet verified |
