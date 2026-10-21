# BOT-221 — The two watches of a bot read its symbol's mark price once a beat, not twice

**Status:** ✅ Done (2026-10-21)
**Board:** The exit watch and the risk watch of a bot share one reading of the symbol's mark price (at most half a beat old, dropped by any order, cancel or fill of the bot), so an idle bot costs 103, 55 and 46 weight a minute at 1, 5 and 20 bots instead of 115, 67 and 58; open orders are not shared (one read a beat and no second reader: nothing to save), the absent-stop decision still asks the account, and the cap is untouched.
**Source:** The delivery coordinator, 2026-10-21 (owner: "oki"), after `BOT-184` (#664) and `BUG-247` (#669): share the mark-price and open-order reads of a venue's bots, with `BOT-184`'s discipline, for headroom on the owner's VPS.
**Risk:** 🟡 — the mark judges a stop loss, a take profit and the risk watch; a shared figure must not make a bot judge on a stale one.
**Complexity:** M — one generic bounded-age reading (extracted from `BOT-184`) and one more instance of it, behind the existing mark source.
**Epic (optional):** [EPIC-029](../epics/EPIC-029_bots_tab_grid_fast_track/README.md)
**Depends on:** `BOT-184`.

---

## 1. Context and problem
After `BOT-184` an idle Futures bot spent 115 weight a minute alone and 58 each at twenty bots (`positionRisk` 60 in all). What remained was symbol-scoped: `premiumIndex` 24 a minute (two reads a beat), `openOrders` 12 and `openAlgoOrders` 12 (one read a beat each). `BOT-184` §2 listed sharing the mark and open-order reads as the follow-up; the owner's VPS run (two Futures grids) had shown the request-weight pause about hourly before `BUG-247`.

**What the measurement changes.** The ask was "one read per symbol per beat for all bots on that symbol". `other_active_bot` forbids two bots on one symbol of a venue, so no two bots ever share a symbol and a per-symbol reading shared *across bots* saves nothing today. The mark's two readers are the exit watch and the risk watch **of the same bot** (`futures_wiring.futures_exposure` and `risk_watches` each build an `ExchangeMarkSource`), and that is the saving. The open orders have one reader a beat (`ProtectiveStopService.supervise` → `_open_stops`), so there is nothing to share.

## 2. Acceptance criteria
- [x] A bot's two watches read the symbol's mark once a beat: measured on the fake exchange, `premiumIndex` is 12 weight a minute per bot at N = 1, 5 and 20 (was 24).
- [x] A reading is never older than half a beat, and any order, cancel or fill of the bot drops it; a read in flight when it was dropped is not kept; a failed read is never kept.
- [x] A stop is never hidden by it: a stop that runs between two beats still ends the bot as triggered (journey, with the mark and the positions both just shared); a stop taken off the exchange by hand right after a beat is seen at the next look (the open orders are read every look).
- [x] The absent-protective-stop decision still asks the account (`ProtectiveStopService._explain_absence`, `BOT-184`): unchanged.
- [x] Measured weight per idle minute at 1, 5 and 20 bots, before and after (§5).
- [x] The cap, the caps of the owner, config, settings, dependencies and the Engine: untouched. When stops are judged: untouched.
- [ ] *Not built, on purpose:* a shared open-orders reading. One read a beat has no second reader, so it saves 0 weight, and it would stand between a bot and the question whether its stop still stands. The seam is stated in `BoundedAgeReading`'s docstring.
- [ ] *Not reached:* "N idle bots cost little more than one". Twenty bots still cost 920 weight a minute (38 % of the exchange's 2,400, 55 % of the gate's line): marks, open orders and open algo orders are symbol-scoped and the bots are on distinct symbols. The next lever is `premiumIndex` without a symbol (weight 10 for all symbols, 120 a minute at any N against 12 × N): worth it only above about ten bots on a venue, past the cap of 5, so it is a decision for the owner.

## 3. Design
`BoundedAgeReading[T]` (new, generic) is the read-through reading `VenuePositionReads` was: bounded age, a generation per read so one that raced an invalidation is not kept, two locks so `invalidate()` never waits behind a network read. `VenuePositionReads` is now a thin subclass (`positions()`); `SharedMarkReads.of(venue, symbol)` is the second instance, one per venue and symbol, reading through `read_mark_price` (the translation `ExchangeMarkSource` already did, extracted). A bot's gateway holds a `BotSharedReads(positions, mark)`; `BotAccountReads.shared_mark` hands the mark reading to `ExchangeMarkSource`, and `account_changed()` (before and after every order and cancel, on every fill) drops both. Pattern: the read-through cache with write invalidation of `BOT-184`, applied again rather than a second mechanism.

**Risk weighed.** The mark is the figure an exit fires on. The bound (half a beat, `SHARED_READING_MAX_AGE_SECONDS`) keeps the watches of one beat on one reading and sends the next beat back to the exchange, so no watch judges on anything older than one beat, today's worst case. A reading is served only to the readers of this bot's own symbol.

## 3a. Reuse
`BoundedAgeReading` is `VenuePositionReads`' mechanism extracted, not copied. `ExchangeMarkSource`, `IMonotonicClock`, `FakeMonotonicClock`, `FakeOrderEntryTerms`, `WeightMeter`: used. `ExchangeCallPolicy`: unchanged. `.claude/rules/capabilities.md`: no row fits (no UI or support-package need).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/application/services/risk/bounded_age_reading.py` | new: the generic bounded-age reading, extracted from `VenuePositionReads` |
| `bots/application/services/risk/venue_position_reads.py` | a subclass of it |
| `bots/application/services/risk/shared_mark_reads.py` | new: one mark reading per venue and symbol |
| `bots/application/services/orders/bot_shared_reads.py` | new: the readings one bot's gateway holds |
| `bots/application/services/orders/bot_account_reads.py`, `bot_order_gateway.py` | `shared_mark`; `account_changed` drops both readings; the gateway takes `BotSharedReads` |
| `bots/application/services/venue/mark_source_futures.py` | `read_mark_price`; `ExchangeMarkSource` serves from the shared reading when there is one |
| `bots/application/kinds/grid/grid_executor_factory.py`, `bots/composition/executor_bindings.py` | `GridExecutorDeps.marks`; built once |

## 5. Testing
Measured on the fake Futures exchange's `WeightMeter`, an idle minute (12 beats, a tick a second), `test_a_shared_mark_never_hides_a_stop_on_the_fake_exchange.py` (`pytest -k n_idle_bots_read_each_mark -s`):

| Bots | Before: total / per bot / mark | After: total / per bot / mark |
| ---: | :--- | :--- |
| 1 | 115 / 115 / 24 | 103 / 103 / 12 |
| 5 | 335 / 67 / 120 | 275 / 55 / 60 |
| 20 | 1,160 / 58 / 480 | 920 / 46 / 240 |

(`positionRisk` 60, open orders and open algo orders 12 per bot, unchanged.) Before = master `ed2bc9a`, after = this branch.

Unit, `test_shared_mark_reads.py` (10 cases): one request for the two watches, the next beat reads again, the half-beat bound at its edge, one reading per venue and symbol, a failed read not kept, a venue with no mark is an unread mark, an order and a fill each drop the reading, a read that raced an order is not kept, a bot without a shared reading. Integration (9 cases): the figures above, a second look inside half a beat reads nothing and one after it reads, a fill drops the mark, the limit with every drop switched off, a stop that runs between two beats ends the bot as triggered with the mark shared, a stop cancelled by hand is seen at the next look. Mutated, each red: marks not shared (7 integration cases), no mark invalidation (the fill journey and 3 unit cases), the age bound tripled (3 cases).

## 6. Docs touched
`Docs/MODULES/bots/06-runtime.md` ("several bots on one venue": the shared mark, its bound and invalidation, the figures, what is not shared and why, the limit).

## Implementation notes
The ask assumed bots share symbols; they cannot (`other_active_bot`), which is why the saving is the bot's own second mark read and why the open orders are not shared. Reported to the delivery coordinator before building. `BotOrderGateway` kept its four constructor arguments by taking one `BotSharedReads` where it took the positions reading; the one test file that built it with a positions reading wraps it.
