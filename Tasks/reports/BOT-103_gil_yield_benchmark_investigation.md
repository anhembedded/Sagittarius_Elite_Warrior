# BOT-103 — GIL-yield benchmark investigation (2026-09-22)

**Outcome: option (a) from the task ("nhường GIL định kỳ trong vòng lặp",
periodic `time.sleep(0)`) is measured to NOT reduce the worst-case
GIL-acquisition gap, and adds real throughput overhead. Reverted before
commit — not shipped. Task stays in `backlog/`, not moved to `completed/`.**

## What was measured

Per the task's own §4 ("đo trước/sau bằng con số thật, không chỉ 'cảm thấy
mượt hơn'"), before touching production code: a synthetic benchmark spawning
a "probe" thread (a tight loop recording `time.perf_counter()` timestamps,
standing in for the Qt main thread's own event-loop demand for the GIL)
concurrently with a synthetic CPU-bound loop shaped like
`RunHistoricalTickBacktestCommandHandler._simulate()`'s real tick loop
(600,000 iterations — `BOT-075`'s own measured worst case, 7 days at 1s
resolution).

Measured `max_gap_ms` (the worst single gap between two consecutive probe
timestamps — the number that corresponds to a real, perceptible UI stall)
and total elapsed time, with `time.sleep(0)` inserted every N ticks, N swept
from 256 (the task's own suggested reuse of the existing progress-throttle
divisor) up through 50,000, averaged over 3 trials each, on a 4-core
container:

| yield every N ticks | elapsed (avg) | max gap (avg) |
| ---: | ---: | ---: |
| none (baseline) | 2.084s | 18.575ms |
| 50,000 | 2.150s (+3%) | 28.106ms |
| 10,000 | 2.185s (+5%) | 25.675ms |
| 5,000 | 2.205s (+6%) | 27.338ms |
| 2,000 | 2.287s (+10%) | 31.497ms |
| 1,000 | 3.336s (+60%) | 26.739ms |
| 256 (task's own suggestion) | 11.584s (+456%) | 27.656ms |

At every tested interval, `max_gap_ms` did not improve over the no-yield
baseline — it was consistently *higher*, within the run-to-run noise this
synthetic benchmark shows. Elapsed time overhead grows monotonically as the
interval tightens, reaching +456% at the task's own suggested N=256.

A parallel test lowering `sys.setswitchinterval()` (CPython's own automatic
GIL-yield check period, default 5ms) to 1ms/0.5ms/0.1ms showed the same
pattern: no consistent improvement in `max_gap_ms`, this time without the
severe throughput cost, but also without evidence it helps.

## Why this rules out option (a), and does not yet answer the task

This is a real, repeated, honest measurement, not a single noisy run — it
directly contradicts the "cheap, obvious" fix suggested as option (a), which
is exactly the value of measuring before shipping: a `sleep(0)`-based fix
would have looked reasonable in review and made the real problem
*measurably worse* (up to 5.5x slower simulation) without confirmed benefit.

It does not yet answer the task's real question, for two reasons this
investigation surfaced but did not have budget to chase further:

1. **The probe is an imperfect proxy.** A real Qt event loop mostly idles in
   a blocking `poll()`-style C call that releases the GIL cooperatively,
   very unlike this benchmark's tight competing Python `while` loop (itself
   GIL-hungry). The two busy threads may be modeling GIL *handoff protocol*
   overhead more than they model real UI responsiveness.
2. **The synthetic per-tick cost is far cheaper than production's.** 50
   float additions stand in for `engine.on_forming_bar_tick()`/`.on_tick()`,
   which in production re-evaluates real indicators over a real `Series` —
   likely orders of magnitude more expensive per tick, changing the
   GIL-holding pattern this benchmark is trying to reproduce.

## Recommendation for whoever continues this task

Per the task's own option (c): profile the *real* `_simulate()` loop
end-to-end (not a synthetic stand-in) to find where tick time actually goes,
then decide between reducing that real cost and the larger, higher-risk
option (b) (`ProcessPoolExecutor`, which needs pickling ticks/results across
the process boundary and a queue/pipe replacement for the current
callable-based `cancellation_requested`/`progress_callback`). This
benchmark's harness (probe-thread pattern, `pairwise()`-based gap
statistics) is reusable for measuring whichever fix comes next — recreate it
against the real handler rather than a synthetic loop.

## Update 2026-09-26 — option (c) executed: real-handler `cProfile` run

`scripts/benchmarking/tick_backtest_profile.py` calls the real
`RunHistoricalTickBacktestCommandHandler.execute()` end-to-end (real
`EmaCrossoverStrategy`, real `StrategyEngineFactory`/`StrategyRegistry`,
real `PaperExchange`) under `cProfile`, 600,000 synthetic ticks (`BOT-075`'s
own worst case). Two methodological traps found and fixed before the numbers
below are trustworthy — both are the finding #2 warning above, applied
concretely:

1. **`unittest.mock.Mock()` as the `event_publisher`** inflated the profile
   with `unittest.mock` bookkeeping (~1.15M `Mock.__init__`/`__new__` calls,
   ~289k `Mock.__call__`) that production's real (cheap) publisher never
   pays — replaced with a hand-written `NoOpEventPublisher(IEventPublisher)`
   (`testing-rule.md`'s "use the real, cheap thing over a Mock" — the port is
   one method, trivially real).
2. **A price oscillation flipping direction every 50 ticks** made ~48% of
   all ticks fire a real trading signal (`strategy_engine.py:124/145`'s
   `publish(SignalGeneratedEvent(...))`), far more often than real market
   data crosses two EMAs — replaced with a slow `math.sin()` drift that
   crosses only a handful of times across the full run.

**Clean result: 600,000 ticks, 20.464s wall-clock, 37,642,473 function
calls** (the first, polluted run measured 52.25s / 58.9M calls — confirms
both fixes mattered). Top self-time (`tottime`) contributors:

| Function | Calls | tottime | cumtime |
| :--- | ---: | ---: | ---: |
| `_simulate` (loop overhead itself) | 1 | 1.920s | 24.155s |
| `EmaCrossoverStrategy.decide` | 598,441 | 1.595s | 9.469s |
| `series._pair` | 1,196,609 | 1.417s | 4.515s |
| `Series.__getitem__` | 4,786,436 | 1.192s | 1.471s |
| `BaseStrategy.series` (accessor) | 1,196,882 | 1.042s | 2.101s |
| `StrategyEngine.on_forming_bar_tick` | 590,000 | 1.037s | 13.704s |
| `FormingBar.to_candle` | 600,000 | 0.997s | 3.254s |
| `PaperExchange.check_intrabar_stops` | 600,000 | 0.975s | 3.251s |
| `Series.__init__` | 1,196,882 | 0.819s | 0.819s |

**Finding: the dominant cost (~42% of total wall time, summing the
`Series`/crossover-detection rows plus `decide`/`series()`/`evaluate`) is the
strategy-evaluation path — and it is *not* incidental overhead to cut.**
`on_forming_bar_tick` runs a full `strategy.evaluate()` (crossover detection
via `Series._pair`/`crossed_above`/`crossed_below`) on **every** tick, not
just at bar close, by deliberate design (BOT-042D/BOT-076: catching a
signal or stop the instant a real tick crosses it is this handler's entire
reason to exist over the Static engine). Removing or throttling this
per-tick evaluation would change observable trading behavior — exactly the
kind of "hack that also breaks the promise" `domain-truth-rule.md` and
`fix-bug-rule.md` §1 rule out; it is not a legitimate optimization target.
No other row is disproportionate to its own necessary work
(`check_intrabar_stops`, `to_candle`, indicator bookkeeping — all O(1) per
tick, no redundant recomputation found).

**Conclusion: this investigation does not find a safe, local per-tick cost
to cut.** Combined with the prior finding that periodic GIL-yielding
(option a) does not reduce `max_gap_ms` at any interval, the two
candidate directions left in the task's own §3 are: (b) `ProcessPoolExecutor`
— a real architectural change (pickling ticks/results across a process
boundary, replacing the callable-based `cancellation_requested`/
`progress_callback` with a queue/pipe mechanism) — or accepting the current
~5x-over-16.7ms-budget UI responsiveness during a realtime tick backtest as
a known, documented limitation. Both are product/risk trade-off calls, not
implementation details a task-execution pass should decide unilaterally;
recorded here as **BOT-103 not closed**, escalated to the user for a
direction before further code changes.
