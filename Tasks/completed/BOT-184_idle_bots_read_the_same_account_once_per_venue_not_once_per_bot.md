# BOT-184 — The bots of a venue read the account's positions once a beat between them, not once per bot

**Status:** ✅ Done (2026-10-21)
**Board:** The bots of a Futures venue read the account's positions once a beat between them (a shared reading, at most half a beat old and dropped by any order we send), so an idle minute reads them 60 weight at 1, 5 or 20 bots instead of 120, 600 and 2,405; the per-symbol reads (mark, open orders) are still per bot, so the idle bot costs 115, 67 and 58 weight instead of 175, and the cap is untouched.
**Source:** `EPIC-029J1b` §5a measurements (2026-10-17); the delivery coordinator, 2026-10-21, after the owner's "OK làm 5 task 1-5 luôn": idle bots read the same account once per venue, not once per bot.
**Risk:** 🟡 — the risk and mark watches are what notice a liquidation risk and a crossed stop; sharing their reads must not make a bot judge on a stale figure.
**Complexity:** M — one reader per venue per beat with a freshness bound, behind the existing watches' ports.
**Epic (optional):** [EPIC-029](../epics/EPIC-029_bots_tab_grid_fast_track/README.md)
**Depends on:** `EPIC-029J1b`.

---

## 1. Context and problem
On the fake Futures exchange's `WeightMeter`, one idle bot over a minute (12 beats of `CHECK_EVERY_SECONDS`, a tick a second) spent 175 weight: `GET /fapi/v3/positionRisk` 120 (two reads a beat, 5 each), `premiumIndex` 24, `openOrders` 12, `openAlgoOrders` 12. It scales linearly with the bots: five bots 875 (52 % of the gate's 1,680 line), ten bots 1,750 (past it), twenty bots 3,500 (past the exchange's own 2,400). A `positionRisk` without a symbol is one request for the whole account (weight 5), so N bots reading it once per beat would cost 25 a minute in all.

## 2. Acceptance criteria
- [x] The account's positions are read at most once a beat for the whole venue, however many idle bots it has: measured with `test_many_bots_on_one_venue_cost_on_the_fake_exchange.py`, an idle minute spends 60 weight on `positionRisk` at N = 1, 5 and 20 (was 120, 600, 2,405).
- [x] Each bot's liquidation-risk watch and protective-stop check still judge on a reading no older than one beat: a reading is served for at most half a beat, and is dropped by any order this app sends or cancels on the venue.
- [x] A confirmation never takes the shared reading (a close, a divergence recheck, a start, a coverage read).
- [x] The cap (`MAX_ACTIVE_BOTS_PER_VENUE`) is unchanged; raising it is the owner's, from the new figures.
- [ ] *Not met, and why:* "N idle bots cost no more than 2 × one". Sharing the account read cannot reach it: the remaining reads are scoped to the bot's symbol (mark: two `premiumIndex` reads a beat; `openOrders`; `openAlgoOrders`), so twenty bots still cost 1,160 weight a minute (58 each). Two of them are the same bot reading the same symbol's mark twice a beat (risk watch and exit watch); sharing those, and the open-order reads, is a follow-up for the owner to size (it changes what two watches may assume about one another's reading).

## 3. Design
`VenuePositionReads` (read-through with a freshness bound and an invalidation) over `IAccountSnapshot.open_positions`, one per venue, found by `SharedPositionReads.of(venue)` and built once by `grid_executor_deps`, which hands it to the risk watch (`PositionRiskSnapshots`) and, through `GridExecutorDeps.positions`, to every bot's `BotOrderGateway`. The gateway drops the reading before it sends or cancels an order and gives `BotAccountReads` the reading for `watched_position`, which `ProtectiveStopService.supervise` uses; `position()` stays the account's own read, so a close is confirmed from the exchange as it is. A single lock serialises the reads, so bots on different threads that arrive together make one request. Pattern: a read-through cache with write invalidation, the freshness bound read from the monotonic clock the bots already measure ages by (`IMonotonicClock`), not the wall clock.

**Risk weighed (and corrected by the review of round 1).** A shared figure must not make a bot judge on a stale one. The bound (half a beat) keeps the sweep of one beat on one reading and sends the next beat back to the account. The reading is dropped by every order or cancel this app sends (before the call and again after it, so a read that raced it is not kept, by a generation each read carries), and by every fill a bot hears (on the stream's thread, before any watch can look). `invalidate()` never waits for a read: two locks, one that serialises reads across the network call and one held for a few instructions. And a stop that left the open list is judged on the account's own read, never on the beat's: the first version let a stop that ran just after a beat's read look missing and be sent again, so the bot went on trading after its stop loss (journey `test_a_stop_that_runs_just_after_a_beat_read_the_positions_still_ends_the_bot_as_triggered`, red before the fix, and a second one with every invalidation off).

## 3a. Reuse
`ExchangeCallPolicy` / `RateLimitGate`: unchanged and still the one limiter. `IMonotonicClock` and `FakeMonotonicClock`: used. `GridRiskWatch`, `FuturesMarkSource` (now `ExchangeMarkSource`): unchanged.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/application/services/risk/venue_position_reads.py` | new: the shared reading |
| `bots/application/services/risk/shared_position_reads.py` | new: one per venue |
| `bots/application/services/orders/bot_account_reads.py` | `watched_position` |
| `bots/application/services/orders/bot_order_gateway.py` | the optional reading; dropped before an order or a cancel |
| `bots/application/services/risk/risk_reads_futures.py` | `PositionRiskSnapshots` reads the venue's shared reading |
| `bots/application/kinds/grid/protection/protection_futures.py` | `supervise` uses `watched_position` |
| `bots/application/kinds/grid/grid_executor_factory.py`, `bots/composition/executor_bindings.py`, `bots/composition/futures_wiring.py` | `GridExecutorDeps.positions`; built once and handed on |

## 5. Testing
`tests/unit/modules/bots/application/services/test_venue_position_reads.py` (14 cases: one request per sweep, the next beat reads again, the half-beat bound at its edge, invalidation, a failed read not kept, eight threads one request, one reading per venue, a watch shares and a confirmation asks the account, an unread account is `None`, an order and a cancel drop the reading); `test_n_idle_bots_read_the_accounts_positions_once_a_beat_between_them` (integration, N = 1, 5, 20; red against the old reads: 120, 600, 2,405). Mutated: the sharing bypassed in both readers.

## 6. Docs touched
`Docs/MODULES/bots/06-runtime.md` ("several bots on one venue"). `10-quality.md`'s cap row is unchanged, because the cap is.

## Implementation notes
Measured on the fake Futures exchange's `WeightMeter`, idle minute (12 beats): one bot 175 → 115 weight, five 875 → 335, twenty 3,512 → 1,160. The `positionRisk` weight is 60 at every N; twenty bots spent 65 in the test's minute (one extra read after an order a bot sent in its first beat dropped the reading), which the test allows.
