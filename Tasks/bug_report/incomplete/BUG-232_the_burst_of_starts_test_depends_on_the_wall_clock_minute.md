# BUG-232 — `test_a_burst_of_starts_stops_at_the_gate_before_the_exchange_limit` fails when its eight starts straddle a clock minute

- **Reported:** 2026-10-19 (the author session of #580, from the PR's `gate (Rest)` run and three local runs; relayed by the coordinator)
- **Severity:** 🟢 P3. Nothing in the app is wrong; a green PR goes red at random and needs a re-run, which the rules allow once.
- **Status:** Open
- **Board:** The fake exchange's request-weight meter buckets by the wall clock's calendar minute, so a burst of starts that crosses a minute boundary sees its weight reset and the gate lets all eight through; the test then fails `4 <= accepted < 8` at random.
- **Context:** `bots` start gate under load → `tests/integration/modules/bots/test_many_bots_on_one_venue_cost_on_the_fake_exchange.py`, `tests/sanity/fake_exchange/request_weight.py` (`WeightMeter`)
- **Environment:** GitHub Actions `gate (Rest)` on `cf29392` (failed, then passed on the one re-run); a developer container: 1 failure in 3 runs of the file at `a9c92b9`. Engine at `engine.ref`.

## Reproduction
Run `pytest tests/integration/modules/bots/test_many_bots_on_one_venue_cost_on_the_fake_exchange.py` repeatedly; it fails when the minute rolls over during the test's eight starts (each start takes several seconds on a loaded machine). Frequency: about 1 in 3 locally, 1 CI run in about 10 seen.

## Symptom
```text
AssertionError: the gate lets about five starts through and refuses the rest
assert 8 < 8
```
(`test_many_bots_on_one_venue_cost_on_the_fake_exchange.py:338`, `assert 4 <= accepted < 8`.)

## Root cause
Established by reading, not yet shown by a run that fixes it. `WeightMeter.record` (`tests/sanity/fake_exchange/request_weight.py`, at `c5f00e2`) assigns each request to `minute = int(self._clock() // 60)` with `_clock` defaulting to `time.time`, and answers the weight "used in the current minute". The exchange's used-weight header, which the app's gate (`exchange_call_policy.py`, `SOFT_WEIGHT_RATIO` 0.7) reads, therefore drops to zero when the wall clock crosses a minute, as Binance's own does at a window edge. The test's eight starts take long enough on a slow runner to cross one, so the gate never closes. The app behaves correctly; the test assumes the burst fits inside one calendar minute without controlling the clock.

## Fix
Not started. Likely: give the test (or the fake exchange's meter for it) a controlled clock: pass a manual `clock` into `WeightMeter` for this test, the way `app.monotonic` already controls the bots' time, so the burst cannot straddle a boundary. Do not widen `4 <= accepted < 8`.

## Regression test
Not written. The test itself is the regression: with a clock that is advanced across a minute boundary mid-burst on purpose, the old test fails deterministically and the controlled-clock version passes.

## Verification
Not run.

## Suggested next steps
1. Fix in the test's own tier (the meter's clock), in a PR of its own, only when it fails again on a PR (coordinator's instruction, 2026-10-19).
2. Check the other tests that read `WeightMeter.weight_since` for the same straddle.
