# EPIC-047H — The host serves the market data and the refreshed exchange facts to the bridge, so the VPS tab connects to nothing at Binance

**Status:** 🔵 Backlog — the decisions are vetoable defaults (the owner, 2026-10-27: *"tự quyết, cố vấn cho tôi đi, ghi lại luôn những giả định cần kiểm chứng luôn nhé"*); the assumptions below are verified first
**Source:** the owner, 2026-10-27: *"Khi vào bot VPS thì tất cả dữ liệu từ Binance phải được lấy thông qua VPS. Bot sẽ không kết nối bất cứ gì tới Binance nữa."* (In the VPS bots tab all Binance data must come through the VPS; the app connects to nothing at Binance.) Charter objective O7, constraint §5.1 and AC10; [the decision record](../DECISION_2026-10-27_a_vps_bot_reaches_binance_only_through_the_vps.md) D1–D7.
**Risk:** 🔴 — it adds a writer and, with D4, scheduled REST reads to the real-money host, on the account and IP the bots trade on; a recorder that blocks or a refresh that spends the exit reserve would hurt the bots.
**Complexity:** L — a market-data recorder on the host, a facts refresher, the bridge's read side and wire roots for both, a verb for the on-demand refresh, and a measurement on the owner's VPS.
**Epic:** [EPIC-047](../README.md)
**Depends on:** [EPIC-047B](../completed/EPIC-047B_the_host_writes_its_in_memory_facts_to_a_file.md) (the facts file and its publisher, done) and [EPIC-047C](EPIC-047C_the_bridge_behind_a_forced_command.md) (the bridge it extends; merged first). The assumptions of the decision record's §6 gate the work that spends REST weight (the recorder's backfill and the scheduled refresh); a veto by the owner reverts a default. **Before:** [EPIC-047E](EPIC-047E_the_vps_bots_tab.md) needs its data. 047D (the transport) does not wait for it.

---

## 1. Context and problem
The VPS tab must connect to nothing at Binance (D1). The decision record's §1 table lists what the detail and the chart read from Binance today and what the host publishes after. Three things have no host source yet: the chart's candles, live candle, last price and mark price; the fills table and the planner's inputs (filters, fees, mid price, daily ATR); the symbol and precision metadata. And the 2026-10-26 D3 left exchange facts as old as the last Start or Resume, which was tolerable only because a desktop screen load re-read them; with the desktop reading nothing, a running bot's facts would age until the next Start. The bridge keeps calling no exchange and loading no key (D2): the host fetches, writes files, and the bridge reads them.

## 2. Acceptance criteria
- [ ] **First step, recorded before any code:** every assumption of the "Assumptions to verify" section below is verified as its row says, and the result (value, date, commit, command or log) is written under Implementation notes. The weight table in the decision record §4 and the defaults of D4 are corrected to the measured numbers, and a row that fails reopens the decision it names.
- [ ] **The host is the only Binance client.** The recorder reuses the host's existing stream and the mark read each beat already makes; it opens a second Binance connection only if (b) shows the host has none to reuse, and says so in the implementation notes. A test fails if the recorder creates its own exchange client.
- [ ] **Market data files (D3).** The host writes the forming candle, last price and mark price for each stored bot's symbol and each published timeframe, owner-only and atomically, at most once a second, with a revision and `heartbeat_s`, on its own daemon thread like `HostFactsPublishing`: a full disk or a slow write delays the file and nothing else. Closed candles are read by the bridge from the host's candle store, read-only. The timeframes are taken from the Bots chart's own list, not copied (P3).
- [ ] **Bridge read side.** The bridge turns a change in those files into events with its own per-key revision (the 2026-10-26 D1 rule), and a snapshot first; the wire roots are added to 047A's closed list with a contract test each. A candle window of the chart's size crosses the wire and back equal.
- [ ] **Fresh exchange facts (D4).** The host refreshes the facts of each bot with exposure every `vps_facts_refresh_interval_s` (default 120 s, lowest 30 s, 0 = off) and reads static exchange info at start and every 24 h, as `RequestPriority.ROUTINE`, so a refresh waits at the 70 % line and never uses the exit reserve. Both numbers and `vps_facts_weight_ceiling_pct` (default 3, highest 10, enforced in code) are host-profile settings, not constants, changeable without a code change. The ceiling is enforced on the weight the exchange reports (the used-weight header), not on an estimate, and the interval stretches to hold it. A test with a fake clock and a fake exchange proves: the ceiling holds at 1, 5 and 20 bots; a closed gate delays the refresh and does not queue a burst afterwards; a refresh failure leaves the last snapshot and its `read_at` and is logged once per cause.
- [ ] **On demand (D4).** A verb through `IHostControl`, judged by the host's gate and audited like the other verbs, refreshes one bot's facts at most once per 30 s, counted inside the ceiling; the answer to a request inside the interval is "already fresh, read at …". The Bots-tab-and-host parity test (`test_the_bots_tab_and_the_host_stay_in_step.py`) lists it.
- [ ] **Planner inputs and fills.** The host publishes the planner's inputs (filters, fees, mid price, daily ATR and Bollinger range) and the bot's fills and orders, each with the time it was read; static exchange info (filters, brackets, symbol list) is read at start and once a day.
- [ ] **No change to trading.** A test over the composed host proves that with the recorder and the refresher on, the number and order of the exit-guard reads, the placements and the cancels are the same as with them off, and that the recorder never touches a lease, a limit or a key.
- [ ] **The bridge still calls no exchange.** 047C's test that the bridge process imports no exchange client and opens no non-loopback connection stays green and is extended to the new read side.
- [ ] **Measured on the owner's VPS**, recorded with its output: the weight actually spent per minute at the real bot count with the used-weight header, the age of a tick and of a facts snapshot seen through the bridge, and the exit reserve untouched. Not run until the owner runs it.
- [ ] A fact never published is reported as "not published by the host", not as an empty value (D5).

## 2a. Assumptions to verify
The rows are the decision record's §6, with the consequence of a false row; this table is the working list and carries the method and the owner of each check. Verify them first (acceptance step one).

| # | Assumption | Method | Who | If false (the record's row) |
| :-- | :--- | :--- | :--- | :--- |
| A1 | Public streams do not count against the IP's REST weight | the used-weight header before and after a stream runs a minute, on testnet; the exchange's websocket limits page | this task, testnet | stream cost joins the ceiling; the recorder streams only while a desktop is connected |
| A2 | Limits 2 400 (Futures) and 6 000 (Spot) per minute per IP | `REQUEST_WEIGHT` in `exchangeInfo.rateLimits`; the exchange's limits page | this task | the percentage follows; redo §4 |
| A3 | The headless host holds a live stream per symbol it trades | the headless composition and a running host's stream log lines | this task (code), the owner (VPS log) | the recorder opens one stream, on demand |
| A4 | A kline backfill is about 5 weight per 500 to 1 000 candles on Futures, 2 on Spot | count requests and the header, one symbol, testnet | this task | throttled by weight; the backfill gets longer, not heavier |
| A5 | One facts read is 10 to 20 weight; one whole-account `positionRisk` serves all bots; static info is tens | recording run of the exchange-facts and planner reads at 1 and 5 bots, testnet | this task | the interval stretches; serve fewer bots per round, never a higher ceiling |
| A6 | The bridge can tail a file at 100 ms without load | ten minutes of the bridge reader on the VPS, CPU and I/O of both processes; a fake-clock unit test | this task (test), the owner (VPS) | poll at 500 ms to 1 s |
| A7 | The detail needs the facts of the six reads and the chart's candles, and no other | a recording run of the whole Bots detail and chart against a call-recording fake exchange; compare with the decision record's §1 table | this task | add the missing source to this task |
| A8 | A `VenueSnapshot` carries no mark price | read `futures_facts.py` | this task | one value less to publish |
| A9 | The bridge reads the host's candle store read-only while the host writes it | open it from a second process during a write, check the journal mode, testnet | this task | the recorder writes closed candles to a file |
| A10 | Exit-guard load is still 96, 240, ~780 per minute at 1, 5, 20 bots, and the refresh never takes the 480 reserve | a day of used-weight headers per minute and the priority class of each request in the host log, on the VPS | the owner runs it, this task records it | lower the interval or the ceiling by setting |

## 3. Design
The shapes already exist and are mirrored (P5): the facts file and its publisher (047B: atomic owner-only write, revision that grows across restarts, `heartbeat_s`, a daemon thread, failure logged once per cause, readers judge liveness by the host's own cadence); the bot-file revision (2026-10-26 D1); `RecordedVenueFacts` as the place a refresh decorates `IVenueFacts`; `RequestPriority` for the weight reserve. The refresh interval for `n` active bots is `max(60 s, n × measured_weight_per_read / ceiling × 60 s)`. The option tables and the reasons are in the decision record §3; the module's design file under `Docs/MODULES/bots/` and the operations module's description take the new parts when they are built.

## 3a. Reuse
`HostFactsPublishing`, `HostFactsPublisher`, `write_owner_only_atomically`, `HostFactsWatch`, `RecordedVenueFacts`, `ExchangeCallPolicy`, `RequestPriority`, `IMarkSource`, `MarketDataCandleFeed`'s history port: `used`; `.claude/rules/capabilities.md` rows are checked at start and listed in the notes. No UI need: the tab reads these through 047E.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/operations/…` | the market-data recorder and the facts refresher, beside `host_facts_publishing.py`; the on-demand verb's handler |
| `src/modules/bots/…` | the refresh as a decorator over `IVenueFacts`; the planner-input and fills publication |
| `src/support/wire/…` and the bridge | the new wire roots and the bridge's read side |
| `tests/…` | the criteria above; the closed-list contract tests for the new roots |
| `Docs/MODULES/bots/07-deployment.md` | the recorder, the refresh and their timing constants |

## 5. Testing
Tier: unit and integration on the composed host over the fake exchange, then the full gate. The measured weight and the tick age on the owner's VPS are the owner's run and are recorded here. Not run.

## 6. Docs touched
`Docs/MODULES/bots/07-deployment.md` (the freshness section: the 2026-10-26 D3 is replaced by the agreed cadence and ceiling; the new files), the operations module's description, `Docs/OPERATIONS/headless_runbook.md` (the new files and what a stale one means, with [EPIC-047G](EPIC-047G_the_runbook_for_the_vps_link.md)).

## Implementation notes (written when done)
Not written: not started.

## Resume (while unfinished)
Not started. D3 and D4 are vetoable defaults ([the decision record](../DECISION_2026-10-27_a_vps_bot_reaches_binance_only_through_the_vps.md) §2, §4a advice, §6 assumptions); the one open owner question there (O1: a fresher tab than the ceiling allows) blocks nothing. Start with section 2a's assumptions after 047C merges; the VPS rows (A3 log, A6, A10) are the owner's run.
