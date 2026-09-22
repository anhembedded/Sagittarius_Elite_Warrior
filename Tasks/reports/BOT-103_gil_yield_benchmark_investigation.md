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
