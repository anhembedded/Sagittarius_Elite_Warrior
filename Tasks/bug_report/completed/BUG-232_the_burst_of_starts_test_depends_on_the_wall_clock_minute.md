# BUG-232 — `test_a_burst_of_starts_stops_at_the_gate_before_the_exchange_limit` fails when its eight starts straddle a clock minute

- **Reported:** 2026-10-19 (the author session of #580, from the PR's `gate (Rest)` run and three local runs; relayed by the coordinator)
- **Severity:** 🟢 P3. Nothing in the app is wrong; a green PR goes red at random and needs a re-run, which the rules allow once.
- **Status:** ✅ Fixed (2026-10-19)
- **Board:** `test_a_burst_of_starts_stops_at_the_gate_before_the_exchange_limit` failed at random (it failed the first CI run of #580 and of #589) because the fake exchange's `WeightMeter` buckets by the wall clock's calendar minute, so eight starts that crossed a minute edge saw the weight reset. Fix: `WeightMeter.use_clock`, and the test holds the clock still.
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
`WeightMeter.use_clock(clock)` (`tests/sanity/fake_exchange/request_weight.py`) swaps the meter's clock; the burst test holds it still (`meter.use_clock(lambda: 0.0)`), so the eight starts are inside one minute by construction. The app, the gate and `4 <= accepted < 8` are untouched; no assertion was loosened.

## Regression test
- `tests/unit/fake_exchange/test_fake_request_weight_window.py`: the weight resets at the minute edge (the behaviour the fake shares with Binance), and a held clock keeps every request in one minute.
- The burst test itself, deterministic: with a clock that advances 20 s per charge (crossing minute edges mid-burst) the old test fails with `assert 8 < 8`, the symptom of the CI failures; with the held clock it passes (3 of 3 local runs).

## Verification
The tests above, red-before (mutation: the crossing clock) and green after; commit tier. Other tests that read `weight_since` against the gate were not changed; none has failed.
