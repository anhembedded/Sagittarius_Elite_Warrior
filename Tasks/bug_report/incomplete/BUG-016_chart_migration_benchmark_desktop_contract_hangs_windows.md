# BUG-016 — `chart_migration_benchmark.py --backend both --desktop-contract` hangs indefinitely on Windows

**Reported:** 2026-08-19, same investigation as `BUG-015`.
**Severity:** P1 — this is the exact script `BOT-098F5` acceptance criterion 6
requires to run to completion for Windows Desktop E2E evidence; it currently
cannot run to completion at all.
**Status:** 🔴 **Open — root cause narrowed to one exact API call (2026-08-21),
not yet fixed.** Real-world impact is low (see note at the end) — this only
blocks closing `BOT-098F5`/`F6D`'s own bookkeeping/acceptance criteria, not
anything shipped: native chart is already the production default
(`BOT-098F6E`, done) and already has real Desktop E2E evidence on Windows
from a different script (`BUG-015`'s probe).

## Symptom

```powershell
$env:PYTHONPATH = "."
python -m Sagittarius_Elite_Warrior.scripts.benchmarking.chart_migration_benchmark `
    --backend both --ci-contract --desktop-contract --report f5_windows_report.json
```

Run on a real Windows 11 machine (confirmed genuine Direct3D11 RHI, native
chart plugin freshly rebuilt against the exact installed `PySide6==6.11.1`
ABI via `.\scripts\build-native-chart.ps1` immediately beforehand — so this
is not a stale-DLL or ABI-mismatch symptom).

The process produced **zero stdout output** — not even the first informational
line the script normally prints before doing any real work — and sat idle for
over 15 minutes. `Get-Process` showed `Responding: False` and CPU time
essentially flat. Process was force-killed; no report, no partial output, no
traceback was ever produced.

## Root cause — narrowed 2026-08-21, real Windows 11 / D3D11 / NVIDIA RTX 3060 session

Reproduced on demand: hangs on every run, including the smallest possible
invocation (`--backend native`, no `--ci-contract`/`--desktop-contract` at
all) within ~60-90s of real time — so the hang is not specific to the
`--desktop-contract` evidence branch or to `--backend both`; it is in code
every invocation goes through.

Isolated by temporarily adding `print(..., flush=True)` checkpoints after
every meaningful statement in `run_benchmark()`/`_run_native()` (this file
has exactly one `print()` normally, the final JSON dump at the very end — so
"zero output" was expected and uninformative on its own; the checkpoints were
temporary and have been fully reverted, `git diff` on this file is empty).
Ran repeatedly with a bounded ~45-60s timeout instead of waiting the full
~15 minutes each time.

**Trace, in order, every single run:**

```
all imports finished
run_benchmark start
constructing QApplication
QApplication constructed
fixture built
_run_native start, constructing QQuickView
QQuickView constructed
setResizeMode done
configure_native_chart_engine done
component.setData done
component.create() done
about to call view.show()
view.show() returned, waiting for expose
qWaitForWindowExposed returned True      <- window genuinely shows and exposes
first processEvents after show done
submitSnapshot done                       <- OHLCV data submitted fine
submitIndicatorSnapshot done              <- indicator data submitted fine
submitMarkerSnapshot done, about to grabWindow
                                           <- nothing further, ever
```

**The hang is exactly, and only, at `view.grabWindow()`** — a bare
`QQuickView.grabWindow()` call on a real top-level window
(`chart_migration_benchmark.py` around what was line 532 at investigation
time). Everything before it — window construction, QML load, show, real
expose, all three data submissions — completes normally and quickly on this
machine. `QQuickView.grabWindow()` is a known-fragile API on Windows under
certain Direct3D11/RHI render-loop conditions (it forces a synchronous
render-thread grab-and-readback); this is consistent with a Qt-level
render-thread synchronization stall, not an app-level logic bug.

### Why this isn't a one-line fix

The file's own docstring is explicit and deliberate about this exact API
choice:

> "The Python path completes captures through `QWidget.grab`; the native
> path uses `QQuickView.grabWindow`. Production `QQuickWidget` host
> performance remains a separate F6D validation gate."

`BUG-015`'s probe script (`native_backtest_chart_interaction_probe.py`,
which runs to completion reliably on this same machine) captures via
`widget.grab().toImage()` — `QWidget.grab()` on a `NativeChartItem` hosted
inside a real `QQuickWidget`, matching production's actual hosting pattern
(`BOT-098F6B`). Simply copying that approach here would work, but would
**silently stop testing what this benchmark says it intentionally tests** —
the bare-`QQuickView` capture path, kept deliberately separate from the
`QQuickWidget`-hosted production path per the docstring. That's a real
design decision to revisit, not something to change as a drive-by inside a
bug fix.

## Suggested next steps (not yet attempted)

1. **Decide whether the bare-`QQuickView` + `grabWindow()` path is still
   worth testing separately**, now that production has run on native
   `QQuickWidget` hosting since `BOT-098F6D`/`F6E` and has its own real
   Windows Desktop E2E evidence via `BUG-015`'s probe. If not, retiring this
   specific code path (and its docstring's stated rationale) in favor of
   `QQuickWidget`+`grab()` is the pragmatic fix — but that's a scope decision
   for whoever owns `BOT-098F5`, not a unilateral call.
2. **If the `QQuickView` path is still wanted**, research known Qt
   workarounds for `grabWindow()` hangs under threaded-render-loop D3D11 —
   candidates worth trying (none attempted yet): forcing
   `QQuickWindow::setPersistentGraphics/SceneGraph` settings, waiting for a
   real `frameSwapped` signal before the first `grabWindow()` call instead of
   just `qWaitForWindowExposed`, or trying `QQuickRenderControl`-based
   offscreen rendering instead of grabbing a real shown window at all.
3. Re-run the same checkpoint-trace method used here (see Root cause) to
   confirm any candidate fix actually gets past `grabWindow()`, not just
   that the symptom looks different.

## Note on real-world impact

Confirmed via `Tasks/ROADMAP.md`: `BOT-098F6E` (native chart as the
production default, Python kept only as an emergency kill-switch) is
**done**. This benchmark script is local diagnostic/evidence tooling for
`BOT-098F5`'s own acceptance criteria — its hang does not affect the running
app or any real user; it only blocks formally closing out `BOT-098F5` and,
transitively, one criterion of `BOT-098F6D`. Deprioritize accordingly against
anything that touches the shipped app.
