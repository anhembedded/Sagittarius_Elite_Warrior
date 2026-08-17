# BOT-098A1 — Marker density performance evidence

**Machine:** Windows 11, Python 3.14.6, PySide6/Qt 6.11.1, pyqtgraph 0.14.0  
**Backend:** Windows CPU viewport, layered antialias, 1600×900  
**Fixture:** 6,420 candles, volume, 5 indicators, 1,112 entry/exit markers

Timing is diagnostic evidence from the same local machine, not a hard shared-CI
gate. CI owns deterministic structural budgets: retained source count,
represented event count and active display item count.

## Before pixel-budget marker LOD

| Viewport | Active markers | Median | p95 | Updates/s |
| --- | ---: | ---: | ---: | ---: |
| 150 candles, full + crosshair | 31 | 40.839 ms | 82.785 ms | 21.71 |
| 5,000 candles, full + crosshair | 980–1,039 | 518–556 ms | 569–642 ms | 1.8–2.0 |
| 5,000 candles, 5 indicators, no marker/crosshair | 0 | 173.252 ms | 190.391 ms | 5.79 |
| 5,000 candles, + markers, no crosshair | 1,039 | 285.298 ms | 541.274 ms | 3.17 |

## After pixel-budget marker LOD

| Viewport | Active / represented | Median | p95 | Updates/s |
| --- | ---: | ---: | ---: | ---: |
| 150 candles, full + crosshair | 12 / 31 | 37.065 ms | 57.458 ms | 24.87 |
| 5,000 candles, full + crosshair | 12 / 980 | 370.198 ms | 492.295 ms | 2.96 |
| 5,000 candles, 5 indicators, no marker/crosshair | 0 | 206.582 ms | 257.277 ms | 4.72 |
| 5,000 candles, + markers, no crosshair | 12 / 980 | 194.062 ms | 235.218 ms | 4.97 |

Run-to-run paint variance is visible in the no-marker indicator profile, so
the meaningful marker result is structural as well as timing-based: 1,039
individual `TextItem`s became 12 truthful aggregate badges. In the measured
wide profile the marker layer no longer added detectable median cost above the
same 5-indicator profile.

The full chart is still below the 60 FPS target. Remaining wide-view cost is
Qt painting of five indicators and crosshair-triggered frame work, not marker
materialization. That work remains under parent `BOT-098` / native renderer
migration and must not be described as solved by this subtask.

## Cached interaction (render on release)

Backtest production wiring already enables `CachedFrameInteractionController`
by default. A real Windows/hybrid Qt input probe confirmed that pan/zoom keeps
the exact data range unchanged throughout the gesture and commits it only on
mouse release (or after the wheel burst):

- cached pixel-transform preview median: **0.737 ms**;
- preview p95: **1.170 ms**;
- preview throughput: **1,263 updates/s**;
- exact final commit: **27.178 ms** in the focused fixture;
- hybrid pan/zoom frame non-empty and no forbidden Qt render warnings.

The retained unit regression sends ten real `QTest.mouseMove` events and
requires zero expensive range applies during drag, followed by exactly one
apply on release. This is a structural performance gate and is stable enough
for CI; the millisecond values remain an external benchmark report.

## Reproduce

```powershell
# Run from the Sagittarius-Engine workspace root.
.\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m `
  Sagittarius_Elite_Warrior.scripts.benchmarking.backtest_chart_interaction `
  --profile all --visible-candles 5000 --measured-frames 30 --warmup-frames 5

.\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m `
  Sagittarius_Elite_Warrior.scripts.benchmarking.backtest_chart_interaction `
  --profile full --visible-candles 150 --measured-frames 60 --warmup-frames 10
```
