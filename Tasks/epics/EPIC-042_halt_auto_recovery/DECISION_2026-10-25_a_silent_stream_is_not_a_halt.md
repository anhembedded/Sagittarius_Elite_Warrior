# ADR — A silent price stream is not a halt: the bot reads the price over REST, and a Futures bot under a standing stop waits instead of closing

**Epic:** [EPIC-042](README.md)
**Date:** 2026-10-25
**Status:** Accepted (the owner confirmed in the author session, 2026-10-25)
**Decided by:** The owner. Relayed 2026-10-25 through the coordinating session (session_016sGQHsRy729Fp4cY1cTXfu): *"Items 1, 2 and 3 as you suggested; no further network check is needed, I approve the suggestion, let's do it."* (translated). Confirmed by the owner's own words in the author session the same day, answering O1 and O2: *"đồng ý ba việc, chờ tối đa 15 phút, chỉ Futures"* (translated: agreed to the three items, wait at most 15 minutes, Futures only). D2 and D5 to D9 are the author's shapes; the owner may veto them.
**Supersedes / superseded by (optional):** extends [ADR 042 D5](DECISION_2026-10-17_halt_auto_recovery.md) (Futures declares nothing but the exchange's pause) by one reason, and applies [ADR 038M O12](../EPIC-038_headless_operation/DECISION_2026-10-20_a_futures_bot_at_host_stop.md) ("a Futures bot is left alone while a stop covers its position") to the price-feed halt. Bug: [BUG-270](../../bug_report/incomplete/BUG-270_a_silent_price_stream_halts_a_futures_bot_that_a_stop_covers_and_closes_its_position.md).

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the code tree at `bfae44f` (`master-warrior`, 2026-10-25); cited by path and symbol |
| 🟢 User decision | decided by the owner, relayed; quoted, then translated |
| 🤖 Agent decision | the author's shape of an owner decision; the owner may veto |
| ❓ Open | needs the owner's answer before the named part is built |

## 1. Context
`y3embt`, a Futures mainnet BNBUSDT Grid with 31 grid orders and a protective stop standing, was halted at 11:32:58 by `price_feed_stale` after its price WebSocket died, and the halt cancelled the ladder and closed the position at market (BUG-270 has the journal).

**Established facts**
- ✅ REST worked throughout; only the WebSocket died. The library notices a dead connection after about 40 s (20 s ping interval plus 20 s ping timeout) and then reconnects, against `PRICE_STALE_AFTER_SECONDS` of 60 s (`domain/grid/price_freshness.py` → `PRICE_STALE_AFTER_SECONDS`).
- ✅ **A Futures bot already reads its mark price over REST on every beat of the price watch** (5 s, `BotPriceWatch` → `CHECK_EVERY_SECONDS`): `GridMarkExit.check` through `GridFacts.on_price_age_check`, and `GridReference`-side exits are judged on it (`GridPriceReaction.on_mark`). The age check (`GridPriceReaction.check_age`) never looks at that read. So on Futures the exits were being judged on a fresh price while the halt said "no price".
- ✅ A Spot Grid judges its exits on the streamed last price only (`GridPriceReaction.on_tick`); it has `IFreshPriceReader` (middle of the book) for resumes and wakes (`contracts/i_fresh_price_reader.py`), not on a beat.
- ✅ The Futures venue layer clears the lower layers and lists `rate_limited` alone (`contracts/venue_profile.py` → `_FUTURES`); a halt that is not recoverable parks the bot, and on a position venue the park closes the position (`GridParking.park` → `_close_position`).
- ✅ Whether a stop covers the position is read fresh from the exchange by one reader: `StopCoverageReader.read` (`StopCoverage.COVERED`, `UNCOVERED`, `NOTHING_EXPOSED`, `UNREAD`), already used for the host stop (ADR 038M D4) and the halt's words.
- ✅ A rate-limit halt is the precedent for a halt that cancels nothing: its reason is in `_NOT_PARKED` (`GridTaskGuard`), it waits in `AWAITING_RECOVERY`, and it recovers through the Resume's propose and confirm with a 2 s dwell (`PAUSE_RULE`).
- ✅ The library logs through `logging.getLogger("binance.ws.reconnecting_websocket")`, outside `App.*`; its ERROR records reach stderr unformatted and are in no log file.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **A price read over REST counts as a price heard.** A stream silent for more than **15 s** (`STREAM_SILENT_AFTER_SECONDS`) is said once, and the bot goes on judging its stop loss and take profit on the price it reads over REST each beat; the age check treats that read like a tick. **Futures only** (O2). | 🟢 Accepted (owner item 1; the 15 s from the owner) | Owner, relayed 2026-10-25 | A dead stream no longer halts a bot whose REST works. `price_feed_stale` then means "no price from either source for 60 s". |
| D2 | **One mechanism, fed by the venue's own price read.** `GridPriceAge` gets a second input, `note_poll()`, and `stale_detail` judges the younger of the last tick and the last poll. The poll is the mark read a position venue's bot already makes each beat (`GridMarkExit` → `GridPriceReaction.on_mark`), so **no new request**. A venue with no such read (Spot) has no poll and is unchanged: no `IFreshPriceReader` read is added (O2). | 🤖 Agent decision, scope fixed by the owner | Author, under D1 and O2 | No `if futures` in the reaction: the call is in the handler of the mark, which only a position venue has. A Spot fallback would be one more source feeding `note_poll`. |
| D3 | **On a Futures venue `price_feed_stale` is a transient halt that recovers by itself** by the rule of `rate_limited`'s kind: 120 s of continuous clear signal (`DEFAULT_RULE.dwell`), at most 3 attempts in 24 h, through the same propose and confirm. One `RuleChange()` in the Futures layer, which keeps `clears_lower_layers`: `user_stream_down` and any kind-added reason stay unrecovered on Futures. | 🟢 Accepted (owner item 2) | Owner, relayed 2026-10-25 | The table changes by one row; `bot show` prints it. |
| D4 | **...only while a protective stop stands and covers the position.** The halt asks `StopCoverageReader.read()` first. `COVERED` makes the halt transient and **cancels nothing and closes nothing**: the ladder and the stop stay on the exchange. Anything else (`UNCOVERED`, `UNREAD`, `NOTHING_EXPOSED` with a ladder resting, a bot with no stop in its plan) is the plain halt that parks and closes at market, unchanged. An unread answer is not a covering stop (ADR 038M D2). | 🟢 Accepted (owner item 2) | Owner, relayed 2026-10-25 | The decision is made at the halt, from the exchange, never from the bot's record. The unchanged path keeps its own test. |
| D5 | **The coverage precondition is a parameter of the halt, not a branch on the bot kind.** `BotRunState.halt` already takes `plain_because` (a caller that knows the cause cannot be waited out). The reaction passes it when the venue's protection says the position is not covered; nothing else in the director changes. The "wait without parking" is decided by the venue's closer (`closes_on_halt()`) in `GridTaskGuard`, the same switch `GridParking` already uses, with `price_feed_stale` joining `_NOT_PARKED` for a bot that closes on halt and is in `AWAITING_RECOVERY`. | 🤖 Agent decision | Author | Spot (no closer on halt) parks as today; the Futures wait keeps its orders. One shared layer (P6). |
| D6 | **A covered wait is supervised like a running bot.** `AWAITING_RECOVERY` joins `_SUPERVISED` in the protective stop service for a position venue, so a stop that vanishes is replaced (or fails the bot into the plain halt that closes) and a stop that fired ends the bot. The exits stay watched (`_WATCHES_EXITS` already holds the state). | 🤖 Agent decision | Author | Without it the wait would be the one state where nothing looks at the stop. Cost: the supervision's reads already made for a RUNNING bot (position, protective orders), no new kind of request. |
| D7 | **The covered wait ends in the existing path.** When the wait ends without recovery (the 3 attempts used up, or the stop stops covering or cannot be read three times in a row (a read every three beats), or the wait outlasts **15 minutes** (`COVERED_WAIT_LIMIT`, O1)) the bot is halted by the plain path: the ladder is cancelled and the position closed at market. | 🟢 15 minutes from the owner; the rest 🤖 | Owner (limit); author | "Existing path unchanged" is a test, not a sentence (§5). |
| D8 | **The library's log records go through the application log** (`shell/binance_client_log.py` → `route_binance_client_logs`, installed by `create_app`). A handler on the library's `binance` logger forwards each record to `App.BinanceClient` with the tag `[binance-client]` in the standard format; the library's own logger stops reaching stderr. The forwarded level is capped at WARNING: the library's ERROR is a failure it reconnects from by itself, and a stream the application sees dead is logged by `BinanceWebsocketService._reconnect_after` at ERROR. | 🟢 Accepted (owner item 3); the level cap is 🤖 | Owner (the routing); author (the cap) | The next incident has timestamps. The log template catalogue is regenerated. |
| D9 | **The queue overflow was a consumer that did not read, not a burst on reconnect.** Measured with the real service and the real library against a local server (the one-off probe of BUG-270, described there): the consumer leaves the socket on the library's error message, the library's `__aexit__` waits for a read loop that its own reconnect keeps alive, and the consumer is held in that exit, reading nothing, until the overflow ends the loop (25 s at the Futures rate). A 35 s stall of the event loop produced no overflow. Written into BUG-270. | ✅ Established (probe) | Author | The stream is blind about 25 s longer than the connection is dead; items 1 and 2 keep a bot alive through it, they do not shorten it. Shortening it is a change to the stream's exit, **proposed to the owner, not built** (O3). |

### 2.1 Polling cost of D1 (requests per minute, only while a stream is silent for more than 15 s)
The beat is 5 s, so a polling bot makes 12 reads a minute.

| Venue | Read | Extra requests per bot | 3 bots all silent | 10 bots all silent |
| :--- | :--- | :--- | :--- | :--- |
| Futures | `premiumIndex` mark (weight 1) | **0**: the same read `GridMarkExit` makes every beat, silent or not | 0 | 0 |
| Spot | `bookTicker` of one symbol (weight 2, to be measured in the fake exchange's weight meter) | 12 a minute, 24 weight | 36 a minute, 72 weight | 120 a minute, 240 weight |

The reads are not orders: the owner's caps (150 open orders, 60 orders a minute, 250 ms spacing) are untouched, and the Futures read is already `EXIT_GUARD` (BOT-226), served in the weight reserve above the 70 % line. The Spot read is `ROUTINE`: in the reserve band it waits, as any routine read does, and the staleness limit then decides as before. When the stream lives, the cost is 0 on both venues. Futures weight limit is 2,400 a minute; Spot's 6,000.

## 2a. Constitution check
Not claimed as a "default" decision: the owner decided and the confirmation is pending in this session, so there is no §7 default to check. The invariants that shape the design: **P6** one shared layer (the age, the layer table, the guard's switch), no per-kind branch; **P5** the mark read, `StopCoverageReader`, `plain_because`, `_NOT_PARKED` and the Resume path are reused; **P7** the poll source is a port per venue profile; **P4** each item's test is red first and the unchanged paths keep tests of their own.

## 3. Alternatives considered
| Alternative | Why it lost |
| :--- | :--- |
| Raise `PRICE_STALE_AFTER_SECONDS` | One constant for two meanings (a dead feed and a slow reconnect); a longer blind window for Spot, where nothing else judges the exits. Does not use the REST price that was already being read. |
| Shorten the library's ping | Changes a dependency's behaviour from outside and still halts a bot for any outage longer than the limit. |
| Make Futures `price_feed_stale` recoverable without the coverage test | Leaves a position with no managed ladder and no stop recovering by itself; contradicts the owner's "only while a stop covers". |
| Special-case Futures in the reaction (`if futures`) | Forbidden by the owner's method (shared layer) and by `test_bots_decide_the_market_in_one_place`. |
| Forward the library's records at their own level | An ERROR the library recovers from would fail every run-log scan for a reconnect the application survives. |

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | How long may a covered Futures wait last? **Answered: 15 minutes** (owner, 2026-10-25). | none | 2026-10-25 |
| O2 | Does item 1 reach Spot? **Answered: Futures only** (owner, 2026-10-25). | none | 2026-10-25 |
| O3 | **New, for the owner:** should the stream leave a failed socket without waiting for the library's read loop (D9)? It would turn about 65 s of blindness into about 45 s, and it touches the Engine-free market-data adapter only. Not built here. | a follow-up | 2026-10-25 |
| O4 | **A note, not a question:** with D1 on Futures a quiet stream no longer halts a bot whose mark is readable, so D3 and D4 are reached only when the mark price cannot be read for 60 s while the position and protective-order reads still can. Item 2's value is therefore narrow; the owner approved it knowing the incident, and it is built as decided. | none | 2026-10-25 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1, D2 | [BUG-270](../../bug_report/incomplete/BUG-270_a_silent_price_stream_halts_a_futures_bot_that_a_stop_covers_and_closes_its_position.md) item 1 | Verified on the simulated venue and the composed fake exchange | `test_a_silent_stream_with_a_readable_mark_is_not_a_halt.py`, the composed `test_a_silent_feed_does_not_halt_a_bot_whose_mark_price_is_read`. |
| D3 to D7 | BUG-270 item 2 | Verified on the simulated venue (unit tier) | `test_a_futures_wait_under_a_covering_stop.py`, `test_a_wait_under_the_stop_is_supervised.py`. Not proven on the composed fake: it has no mark-read fault. |
| D8 | BUG-270 item 3 | Verified | `test_the_binance_client_log_goes_through_the_app_log.py`, wiring included. |
| D9 | BUG-270 | Measured | the one-off probe of BUG-270 (method and output in the report). |
