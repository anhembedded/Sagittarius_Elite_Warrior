# ADR — In the VPS Bots tab the desktop makes no connection to Binance; the host fetches, the bridge only reads

**Epic:** [EPIC-047](README.md)
**Date:** 2026-10-27
**Status:** Accepted — D1 is the owner's rule; D2 to D7 are defaults the owner may veto. Nothing here sets a threshold on orders, positions or money
**Decided by:** D1 by the owner (quoted in §1). D2 to D7 by the author session under ONBOARDING §7 ("Settle an owner decision that carries a recommendation"), each checked in §2a. The owner asked on 2026-10-27, through the coordinator: *"tự quyết, cố vấn cho tôi đi, ghi lại luôn những giả định cần kiểm chứng luôn nhé."* (decide it yourself, advise me, and record the assumptions to verify). So D3 and D4, which spend REST weight, are decided on the conservative side as vetoable defaults; their numbers are settings, not constants, and their assumptions are listed in §6. The first version of this record had left D3 and D4 to the owner.
**Supersedes / superseded by (optional):** Replaces D3 of [the 2026-10-26 record](DECISION_2026-10-26_the_bridge_revision_and_the_unbuilt_venue.md) ("exchange facts stay as fresh as the last read") once the owner accepts D4; until then that D3 stands. Reads with [the remote link record](DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md) D4 (G7a), which D2 keeps.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree at commit `783462a` (master-warrior after #739), cited by path and symbol |
| 🔵 Proposed | an option awaiting a decision; not accepted |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Default, owner may veto | settled on its recommendation under ONBOARDING §7; its Constitution check (§2a) shows every invariant passes; reverted if the owner vetoes |
| ❓ Open | the owner decides; blocks the named phase. Used only for a threshold on orders, positions or money, of which this record sets none |

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
| D3 | **Market data (candles, live candle, last price, mark price, planner inputs) is served by a recorder on the host that writes files; the bridge tails them (option A2, §3).** Closed candles are read from the host's own candle store, read-only; the forming candle, last price and mark price are one small file written at most once a second. The recorder reuses the host's existing stream and the mark read it already makes each beat, and opens a second connection only if 047H shows the host has none to reuse (assumption A3). The backfill of history is lazy and throttled: it starts at the first desktop connect, one symbol and timeframe at a time, `ROUTINE` priority, inside D4's ceiling, and pauses while the weight gate is closed. | Accepted | 🤖 Default, owner may veto | Adds a recorder to the real-money host, on its own thread, which can delay nothing but its own file. REST weight: a one-time backfill, throttled (about 30 weight per symbol, assumption A4). Reversible by setting the recorder off; the tab then says "not published by the host". |
| D4 | **Exchange facts are refreshed by the host on a schedule, bounded by a weight ceiling, plus one on-demand refresh from the tab; the conservative side, every number a setting.** A bot with exposure (RUNNING, or PAUSED with a position or resting orders) is refreshed every **120 s** (`vps_facts_refresh_interval_s`, lowest allowed 30 s). The whole refresh, backfill and on-demand reads included, stays under **3 % of the venue's per-minute weight: 72 on Futures, 180 on Spot** (`vps_facts_weight_ceiling_pct`, highest allowed 10 %, so no setting reaches the 70 % soft line). The interval stretches to hold the ceiling: `max(interval, n × weight_per_read / ceiling × 60 s)` for `n` bots. Static exchange info (filters, brackets, symbols) once at host start and every 24 h. Refreshes are `RequestPriority.ROUTINE`: they wait at the 70 % line and never touch the exit reserve. The on-demand refresh is a read-only verb through `IHostControl` (it starts, stops and places nothing), at most one per bot per 30 s, counted inside the ceiling and judged by the host's gate. | Accepted | 🤖 Default, owner may veto | The tab is at most about two minutes old for a bot with exposure instead of as old as its last Start. Real REST load, small and bounded (§4). Reversible by a setting: interval 0 turns the refresh off and the tab shows the age of the last read, which is the 2026-10-26 D3. |
| D5 | **Offline: the VPS unreachable shows "disconnected, data as of …" and the tab never falls back to Binance.** Last data stays on screen with its age, commands are refused, reconnection is automatic. A fact the host never published shows "not published by the host", not an empty value and not a direct read. | Accepted | 🤖 Default, owner may veto | Same as charter AC6, now also for market data; the chart freezes at the last candle and says so. A bot on the VPS is unaffected. |
| D6 | **The VPS tab offers only what the host can serve.** The Backtest workbench and any control that reads Binance directly (the symbol picker's exchange list, the Plan editor's live suggestions from exchange info) are hidden or read-only in the VPS tab in v1; a plan is designed in the Bots tab and sent with "Add to VPS" (charter Scenario 2), where the VPS's own Checks run against the host's facts. | Accepted | 🤖 Default, owner may veto | The backtest stays on the desktop, as the charter's out-of-scope list says, but in the Bots tab. The cost: editing a plan's symbol in the VPS tab needs the host's published symbol list (D4's static exchange info), so v1 edits parameters and not the symbol. |
| D7 | **A guard holds D1.** (a) A static guard: the modules that build the VPS tab import no Binance client: the closure of the VPS tab's composition may not reach `trading/adapters/binance`, `market_data/adapters/binance` or the gateway's session factories (the `binance_gateway/contracts` value types, such as `TradingVenue`, stay allowed); baseline 0, it only falls. (b) A runtime test: the VPS tab composed over a fake host and a recording fake exchange makes **zero** exchange calls and opens no non-loopback connection, while the Bots tab composed in the same test makes some. | Accepted | 🤖 Default, owner may veto | The static guard alone is green while a port resolved from the container still calls out (P4), so both ship; (b) is the proof the requirement holds. |

## 2a. Constitution check (D2 to D7, the defaults)

| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | D7 is the mechanical barrier for D1: an import guard plus a zero-call runtime test. D2 keeps EPIC-038's "no socket" test and AC5. D4's ceiling is a test: a fake clock and a fake exchange hold it at 1, 5 and 20 bots (047H); the setting's upper bound is enforced in code, so a typo cannot reach the soft line. D3: a test fails if the recorder builds its own exchange client. |
| P2 Verify, don't restate | ✅ | The §1 table was read from the tree at `783462a`; what was not read (mark price in a snapshot, the host's stream) is named as a gap and made 047H's first step. The weight figures are the ones the code records; the rest are estimates and are measured in 047H (§4). |
| P3 A copy drifts | ✅ | D2: one exchange client per key and IP, the host; the tab holds no second reader of Binance. The planner and exchange facts are read from the one host snapshot, not re-derived. |
| P4 Green proves only what was tested | ✅ | D7(b) proves absence of calls at run time; D7(a) alone would not. D5 gets a test of the cut link and of the unpublished fact. D3 and D4 rest on assumptions a green test cannot prove (§6); each has a measurement, and 047H is not Done until the testnet ones are recorded and the VPS ones are run by the owner. |
| P5 Apply before you invent | ✅ | D2 mirrors the host-facts file (047B) and the bot-file revision (2026-10-26 D1); the recorder mirrors `HostFactsPublishing` (daemon thread, atomic owner-only write). A relay by socket was not invented (§3). |
| P6 Fix the mechanism | ✅ | The mechanism is "the screen reaches Binance through the container"; D1 and D7 fix the path, not one screen, and EPIC-048B's doors already remove the container reach. |
| P7 Seam now, variant later | ✅ | The bridge's reader sits behind the same revision rule; a live-event relay (A1) or a stream the bridge forwards stays a later variant behind the same wire roots. D6 builds no host-side editing of symbols yet. |
| P8 Ratchets only fall | ✅ | D7(a) starts at baseline 0 and only falls; no guard loosened; the 2026-10-26 D3 is replaced by a bounded rule, not removed without one. |
| P9 Decide alone | ✅ | All six are decided with a recommendation and the owner's own instruction of 2026-10-27 to decide the REST-load numbers. Nothing here sets a threshold on orders, positions or money; that stays the owner's. |
| P10 Pyramid and units | ✅ | Leads with the rule; each figure carries its unit (weight per minute, seconds, percent of the venue limit). |
| P11 Prompt-grade artifacts | ✅ | Each row names the symbol, the test and the task that delivers it (§5). |
| Reversible; no real money, dependency, setting, Engine, user data or secret | ✅ | D2 changes no code; D5 only refuses more; D6 hides controls in a tab not yet built; D7 adds a guard. D3 and D4 add read-only REST load under a ceiling (3 % of the minute weight, the exit reserve untouched) and two host settings (047H adds them to the host profile, which is an ordinary application setting, not a dependency or a repository setting); they move no order, limit or key and touch no Engine file. A veto, or interval 0, reverts them with no code change. The exit-guard reads keep their priority over every refresh. |

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

Basis: Futures IP limit 2 400 per minute, soft line 1 680, hard line 2 160, exit reserve 480; Spot 6 000, from the constants cited in §1 (assumption A2 checks them against the exchange).

| Item | Weight | Source |
| :--- | :--- | :--- |
| Today's idle load of the three exit-guard reads | 96, 240, ~780 per minute at 1, 5, 20 bots (4 %, 10 %, 33 % of a Futures IP) | `request_priority.py`, `BOT-226` (assumption A10 re-measures it) |
| Ceiling for everything this record adds | 72 per minute on Futures (3 %), 180 on Spot (3 %); settable, hard maximum 10 % | this record, D4 |
| One facts read of a Futures bot (account, position, resting orders, settings, brackets) | **20 warm**, 81 for the first read after a start, +30 when the Multi-Assets mode ages past five minutes (measured, A5); the planner inputs 25; the fills 10 a seven-day window | measured on the real chain 2026-10-27 |
| Scheduled refresh at the 120 s default | simulated three hours on a fake clock at these weights: the median gap between two facts reads of one bot is 120 s with 1 and with 5 bots and about 410 s with 20; the most spent in any minute was 55, 70 and 70 of 72 | `tests/unit/modules/operations/vps_feed/` |
| Static exchange info | once at start and once a day, **1 weight** (measured on testnet, A5; the body is about 900 KB, so the cost is bandwidth) | measured 2026-10-27 |
| Candle backfill | a sync of the chart's five timeframes, one request of at most 1 000 candles each (`python-binance`'s page size, matching `_KLINE_STREAM_CHUNK_SIZE`; the documented kline weight is 5 at that limit, so about 25), charged **50 weight** by estimate, twice that, per symbol sync (the `market_data` REST client does not pass `ExchangeCallPolicy`, so its weight is not observed, A4); waits while the trading gate is closed to routine requests; streams cost no REST weight (A1, measured on testnet) | A1 measured, A4 estimate |
| Peak with the defaults at 20 bots | 780 + 72 = 852 per minute, 35.5 % of the IP, under the 70 % line with 828 weight of headroom, plus the 480 reserve | arithmetic on the figures above |

Two consequences. The load is **flat in the number of tabs and clients**: today's desktop reads add load on the *desktop's* IP; after D1 only the host reads, on a fixed budget, however many times the owner opens the tab. And a refresh is `ROUTINE`, so while the gate is closed at 70 % it waits and the tab's facts age, while the exit reads keep their reserve: the tab degrades before a stop loss does.

## 4a. Advice to the owner

- **Recommendation.** Take the defaults: refresh every 120 s, ceiling 3 % of the venue minute weight (72 on Futures), recorder by files, backfill at the first desktop connect, no refresh while the weight gate is closed. Start with the recorder and the refresh both on in testnet, read the used-weight header for a day, then switch the VPS on.
- **Why.** The tab is a *view*; it should never be able to hurt a trading host. 3 % is small enough that the peak stays near a third of the IP at 20 bots. The ceiling is enforced on the weight the exchange reports (the used-weight header, per request), not on the estimate of §4, so a wrong estimate lengthens the interval and cannot overspend; and the gate closes routine reads first. A 120 s age is fresh enough to see a position or a resting order change, and fills still arrive at once from the bot files (AC2 is about fills, not about account facts).
- **What would make me change it.** (1) The measured per-read weight on testnet is above 20: lower the bot count it serves per round or stretch the interval, do not raise the ceiling. (2) The host turns out to hold no stream per symbol (A3): the recorder would open one, which is a connection and not a REST cost; I would then advise a lazy start of the stream only while a desktop is connected. (3) The owner finds two minutes too slow for a position: raise the cadence toward 30 s only after the VPS measurement (A10) shows the peak below 40 %; the setting allows it with no code change. (4) The used-weight header shows the stream counting against the REST weight (A1): move the stream cost into the ceiling and shrink the refresh.
- **Not mine to default.** Anything that sets a threshold on orders, positions or money. This record sets none: a refresh only reads, and the verb it adds starts, stops and places nothing.

## 5. Open questions

| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Does the owner want the tab fresher than the ceiling allows (for example 30 s for every bot)? That raises the host's share of the IP's weight, so it is the owner's call and is not defaulted; the setting allows it up to the 10 % maximum with no code change. | nothing; a setting after the VPS measurement | 2026-10-27 |
| O2 | Is D6 acceptable: no symbol change and no backtest in the VPS tab in v1? A default, listed because it removes a function the Bots tab has. | EPIC-047E | 2026-10-27 |

No question here sets a threshold on orders, positions or money.

## 6. Assumptions to verify

Each is something the defaults rely on and a green test cannot prove (P4). 047H carries the same list as its first acceptance step and records the result in its Implementation notes; a row that fails reopens the decision it names.

| # | Assumption | How to verify | Who | If false |
| :-- | :--- | :--- | :--- | :--- |
| A1 | Public market-data streams do not count against the REST weight of the IP | On testnet read the used-weight header (`ExchangeCallPolicy.note_used_weight_header`) before and after a kline stream opens and runs a minute; read the exchange's websocket limits page (connections, streams per connection, incoming messages per second) | 047H author (testnet) | The stream's cost joins D4's ceiling and the refresh shrinks; the recorder subscribes only while a desktop is connected |
| A2 | The venue limits are 2 400 weight per minute for a Futures IP and 6 000 for Spot, and the gate's 70 % and 90 % lines apply (`venue_sessions.py` → `FUTURES_WEIGHT_LIMIT`, `exchange_call_policy.py` → `SPOT_WEIGHT_LIMIT`) | Read the `REQUEST_WEIGHT` entry of `exchangeInfo.rateLimits` on each venue and compare with the exchange's general-info limits page | 047H author (testnet and mainnet public endpoint) | The ceiling is a percentage and follows the limit; §4's absolute numbers are redone |
| A3 | The headless host already holds a live stream for each symbol it trades | Read the headless composition (`run_host.py`, the market stream use case `StartLiveStreamCommand`) and the stream lines in a running host's log | 047H author (code); the owner (VPS log) | The recorder opens one stream, which is a connection and not REST weight; it starts only while a desktop is connected (§4a) |
| A4 | A kline backfill costs about 5 weight per request of 500 to 1 000 candles on Futures, about 2 on Spot, so about 30 per symbol over six timeframes | Count the requests and read the used-weight header on testnet for one symbol | 047H author (testnet) | The backfill is throttled by weight, so a higher cost lengthens the backfill and never raises the load |
| A5 | One facts read of a Futures bot costs 10 to 20 weight, a whole-account `positionRisk` read serves every bot, and static exchange info costs tens of weight | A recording run of `GetExchangeFactsQuery` and of the planner read against the testnet with the header, at 1 and 5 bots | 047H author (testnet) | The interval stretches by itself to hold the ceiling; if a round exceeds 20 weight per bot the advice (§4a) is to serve fewer bots per round, not to raise the ceiling |
| A6 | The bridge can tail a file at 100 ms without load on the host | Run the bridge's reader against the host's files for ten minutes on the VPS and read the CPU and I/O of both processes; unit test with a fake clock | 047H author (test); the owner (VPS) | Poll at 500 ms to 1 s; AC2 asks 5 s for a fill, and the market file is written only once a second anyway |
| A7 | The exchange facts the detail needs are those and only those the six reads use (`BotSnapshot`, `PlannerMarket`, `VenueSnapshot`, `ConnectionRead`, `RunFacts`, `PlanRiskRead`) plus the chart's candles | A recording run of the whole Bots detail and chart against a call-recording fake exchange lists every endpoint it touches; compare with §1's table | 047H author | The missing source is added to 047H; D7(b)'s zero-call test would have found it in 047E |
| A8 | A `VenueSnapshot` does not carry the mark price | Read `futures_facts.py` and the snapshot's fields | 047H author (code) | If it does, the recorder publishes one value less |
| A9 | The bridge can read the host's candle store read-only while the host writes it | Open the store from a second process while the host writes, on testnet; check the journal mode | 047H author | The recorder writes closed candles to a file instead |
| A10 | The exit-guard load is still 96, 240 and ~780 per minute at 1, 5 and 20 bots, and the refresh never takes the 480 reserve | On the VPS, read the used-weight header per minute at the real bot count for a day with the refresh on, and the priority class of each request in the host log | The owner runs it, 047H records it | Lower the ceiling or the cadence by setting before leaving the refresh on |

### Results of the first step (2026-10-27, 047H author, testnet and code; the full table is in 047H's Implementation notes)

| # | Result |
| :-- | :--- |
| A1 | Holds on testnet: a two-symbol kline stream for 25 s left the used-weight header at 1 to 2. The exchange's websocket limits page was not fetched; those limits stay unverified |
| A2 | Futures testnet reports 6 000 per minute and Spot 6 000; the code keeps 2 400 for every Futures venue (stricter, kept). Mainnet unreadable from the author's region (HTTP 451): the owner's step |
| A3 | Holds, with a correction: the host streams the **1m** kline for each bot not at rest, so the other timeframes' forming candles are folded from 1m (flagged incomplete when the host started inside the bucket) and a stopped bot's symbol has no live price |
| A4 | Not measurable on testnet (the kline endpoint's header is shared noise). `market_data`'s REST client is outside the weight gate, so the backfill is charged to the ceiling by estimate and waits on the gate |
| A5 | `premiumIndex` 1 and about 10 for the whole market, `exchangeInfo` 1, `bookTicker` 1 (testnet). On the composed host over the fake exchange charging Binance's documented weights: a facts read is **81 cold, 20 warm** (plus 30 whenever the Multi-Assets mode has aged five minutes), the planner inputs 25, the fills 10 a seven-day window (20 a day on Spot). The §4 planning figure of 15 was low; fills and planner ride every **fifth** round and an asked-for refresh |
| A6 | 0.12 % of one core per file at 100 ms; the VPS run is the owner's |
| A7 | Re-read; no missing source. The recording run is 047E's zero-call test |
| A8 | Holds: no mark price in a snapshot |
| A9 | Holds: WAL, 3 553 read-only reads against 57 226 commits, 0 errors; the `sew` account's access to the shard is the owner's check |
| A10 | The owner's run |

## 7. Implementation evidence

| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | [EPIC-047E](incomplete/EPIC-047E_the_vps_bots_tab.md) (AC10), [EPIC-047H](incomplete/EPIC-047H_the_host_serves_market_data_and_refreshed_facts_to_the_bridge.md) | The host's half in review (2026-10-27); the tab's half (047E) not started | The host serves every read the tab needs: [047H notes](incomplete/EPIC-047H_the_host_serves_market_data_and_refreshed_facts_to_the_bridge.md); the tab's side is 047E's |
| D2 | EPIC-047H | In review (2026-10-27) | `tests/unit/architecture/test_the_vps_feed_reads_only_and_opens_no_connection.py` covers the new read side and the refresher; 047C's bridge test stays green |
| D3 | EPIC-047H | In review (2026-10-27); assumptions A1, A3, A4, A6, A8, A9 verified (A4 by estimate) | [047H notes, Step one](incomplete/EPIC-047H_the_host_serves_market_data_and_refreshed_facts_to_the_bridge.md) |
| D4 | EPIC-047H | In review (2026-10-27); A2, A5 verified as far as a key-free testnet allows, A10 is the owner's | [047H notes, Step one](incomplete/EPIC-047H_the_host_serves_market_data_and_refreshed_facts_to_the_bridge.md) |
| D5 | EPIC-047E | Not started | Not yet verified |
| D6 | EPIC-047E | Not started | Not yet verified |
| D7 | EPIC-047E | Not started | Not yet verified |
