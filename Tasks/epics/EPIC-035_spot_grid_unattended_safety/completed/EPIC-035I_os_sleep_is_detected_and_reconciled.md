# EPIC-035I — OS sleep is detected and reconciled

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M8 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 2 of [EPIC-035](../README.md), approved 2026-10-08.
**Risk:** 🟡 — after wake the bot behaves as in a stream gap and a stop-loss crossed in sleep goes unnoticed
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), extended by this task
**Depends on:** EPIC-035B

---

## 1. Context and problem
**M8 — sleep and hibernate are not detected. Verified ✅ on `be67b47`.** A search of `src/` for sleep, hibernate, suspend, wake and power finds no handling in the bots module: the only clocks it holds are `IBotClock` (wall) and `IMonotonicClock` (`EPIC-035A`), read for a price's age. A suspended laptop stops the process, so the price stream and the user-data stream die with the connection. `EPIC-035B` reconciles when the user-data stream *reports* `CONNECTED`, and `EPIC-035A` halts a bot whose feed went quiet; neither reads the night's price against the stop loss, and a fill the stream missed waits for the stream's own reconnect (or, at worst, the five-minute re-check). Nothing in the tree tells the bot "you were asleep".

**One fact the audit did not state, and the design depends on it.** `time.monotonic` is not the same clock on both platforms: on Windows it keeps counting through sleep, on Linux (`CLOCK_MONOTONIC`) it stops. A detector on the monotonic clock alone would work on the owner's machine and silently never fire on Linux. The detector therefore also reads the wall clock.

## 2. Acceptance criteria
- [x] A gap in the clocks larger than a named threshold (`SleepLimits.gap_over`, 60 s over the heartbeat's 15 s) is detected by one service, `SleepWatch`.
- [x] On detection every bot with an executor runs the gap reconcile of `EPIC-035B` — `reconcile_after_gap()`, the entry point `UserStreamWatch` calls, not a second reconcile — and its stop loss and take profit meet a **fresh** price read from the venue (`IFreshPriceReader`), not the last tick.
- [x] The event is logged (`[sleep-detected]`, `[sleep-exit-check]`) and shown to the user as one notice naming the length of the sleep and the number of bots re-checked.
- [x] A price the venue will not give straight after the wake is tried again, bounded (4 reads, 15 s apart); past that the staleness rule of `EPIC-035A` takes over.
- [x] `GridExecutor` gains nothing (it is over its public-surface limit): the service uses `reconcile_after_gap()` and `on_tick()`, both already on `IBotExecutor`.

## 3. Design
- **Detector** (`ClockGapDetector`): at each look, `max(monotonic elapsed, wall elapsed)` minus the expected interval; a wall clock set back is a negative elapsed time and ignored; one set forward reads as a sleep, and the catch-up it causes changes nothing when nothing was missed (idempotent).
- **Catch-up** (`SleepWatch`): per executor `reconcile_after_gap()`, then `WakeExitCheck`, in that order on each bot's own queue, so a fill the night held is booked before the exit rule looks at the price.
- **Exit check** (`WakeExitCheck`): one fresh read per (venue, symbol) among the executors, given to each bot as `on_tick` — the exit rules are the ones a live bot has, nothing is duplicated. A newer wake supersedes a retry chain still running.
- **Port** `IFreshPriceReader` with the adapter `VenueFreshPriceReader` (the middle of the best bid and ask through the venue's `order_entry_terms`, the read a bot's own market price uses); every failure becomes one `FreshPriceUnavailableError`.
- **Heartbeat** on `IBotRetryScheduler`, the seam `EPIC-035C` and `035B` use; `shutdown()` closes it. Nothing sleeps.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/clock_gap_detector.py` | New: the two-clock gap detector |
| `src/modules/bots/application/services/sleep_watch.py` | New: `SleepWatch`, `SleepLimits`, `SleepWatchDeps` |
| `src/modules/bots/application/services/wake_exit_check.py` | New: the fresh-price exit check with bounded retry |
| `src/modules/bots/contracts/i_fresh_price_reader.py` | New port and its error |
| `src/modules/bots/adapters/venue_fresh_price_reader.py` | New adapter over `IVenueTradingPorts` |
| `src/modules/bots/composition/executor_bindings.py`, `src/modules/bots/module.py` | Bind the reader; build and begin the watch in `boot()` |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md` | The journey "the machine slept" |
| `tests/unit/modules/bots/application/services/test_sleep_watch.py` (+ `sleep_world.py`), `tests/unit/modules/bots/adapters/test_venue_fresh_price_reader.py`, `tests/integration/modules/bots/test_sleep_watch_wiring.py` | The tests of §5 |

## 5. Testing
| Criterion | Test | Tier |
| :--- | :--- | :--- |
| Gap → reconcile + exit check | `test_a_clock_gap_triggers_a_reconcile_and_an_exit_check` (a BUY filled and the stop loss crossed in the night); `test_a_gap_reconciles_a_fill_missed_in_sleep_before_the_price_is_checked`; `test_a_take_profit_crossed_in_sleep_is_taken_on_wake` | Unit, real executors over the simulated venue, fake clocks |
| Fresh, not the last tick | `test_the_exit_check_reads_the_price_afresh_not_the_last_tick` | Unit |
| Threshold | `test_a_beat_late_by_exactly_the_limit_is_not_a_gap`, `…_more_than_the_limit_is_a_gap`, `test_ordinary_beats_do_nothing` | Unit |
| Both clocks | `test_a_sleep_the_monotonic_clock_did_not_count_is_still_a_gap`, `test_a_wall_clock_set_back_is_not_a_gap` | Unit |
| One sleep, one catch-up; told once | `test_one_sleep_is_one_catch_up`, `test_the_wake_is_logged_and_told_to_the_user` | Unit |
| Retry, bounded | `test_a_price_the_venue_will_not_give_is_retried_until_it_does`, `test_the_retries_are_bounded` | Unit |
| Wiring (`CS-002`) | `test_boot_arms_the_sleep_watch_heartbeat`, `test_the_fresh_price_comes_from_the_venues_own_ports` | Integration, real container |

## Implementation notes (written when done)

**Evidence.** The new tests were red first: `test_sleep_watch.py` and the wiring file failed at collection / resolution (no service, no port). Mutations measured on the finished code: removing `self._exits.begin()` fails 8 tests; replacing `executor.reconcile_after_gap()` fails `test_a_gap_reconciles_a_fill_missed_in_sleep_before_the_price_is_checked`.

**Deviations, for the owner.**
1. *"Shown on the bot."* The bot has no field for a wake event, and the only writer of a bot's record is its executor, which this task may not grow. The event is shown as **one notice to the user** (a toast, plus the log line) and is not drawn on the bot itself. The per-bot strip that would show "last woke at …" is `EPIC-035W` (not started, by the owner's wish); its snapshot can read the same facts. This acceptance line is met in letter for the log and in part for the screen.
2. The bot count in the notice is the number of executors, which includes a Stopped bot whose executor is still held; a wake reads its price and ticks it to no effect. Harmless, slightly generous in the count.
3. The detector uses the wall clock beside the monotonic one (§1); the task text said monotonic only.

**Not proven here.** A real suspend/resume on Windows. The behaviour is proven with fake clocks; the owner's Testnet run (Phase 1 exit) is the place to close the lid on a running bot.

**Verification.** Commit tier PASS; `tests/unit/architecture` green; `tests/unit/modules/bots` and `tests/integration/modules/bots` green. The `-Full` gate is GitHub Actions' (see the pull request).
