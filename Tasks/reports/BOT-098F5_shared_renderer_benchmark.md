# BOT-098F5 — Shared Backtest renderer benchmark (Python vs native)

**Status:** Local diagnostic evidence — not a shared-CI timing gate.
**Task:** [`BOT-098F5`](../cancelled/BOT-098F5_shared_backtest_renderer_benchmark.md)
**Reference machine:** local Linux dev box (see Environment below). This is a
renderer-level A/B, not a claim about the production `QQuickWidget` host —
`BOT-098F6D` must rerun this profile after production host wiring before
native becomes default.

## Command line

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=<repo-root> \
  python -m Sagittarius_Elite_Warrior.scripts.benchmarking.chart_migration_benchmark \
  --backend both --ci-contract --report Tasks/reports/BOT-098F5_dpr1_both.json
```

DPR 2 run used the same command with `QT_SCALE_FACTOR=2` set to force a 2x
device pixel ratio under the offscreen platform (there is no physical display
to read a real scale factor from on this machine).

## Environment

| | |
| --- | --- |
| OS | `Linux-7.0.0-29-generic-x86_64-with-glibc2.43` (Ubuntu 26.04) |
| Python | 3.14.4 |
| PySide6 / Qt runtime | 6.11.1 |
| pyqtgraph | 0.14.0 |
| Native Qt SDK | Qt 6.11.1, `linux_gcc_64`, installed via `aqtinstall` to exactly match the PySide6 ABI (same mechanism the project's local build script and prior CI used) |
| `QT_QPA_PLATFORM` | `offscreen` for both runs (no physical display attached to this box) |

Both backends measured through the same frozen fixture: 6,420 candles,
6,420 volume bars, 5 price-overlay indicators, 1,112 trade markers, 150
visible candles at 1,600×900 logical resolution, 20 warmup + 120 measured
camera updates, completion via `QWidget.grab()` (Python) /
`QQuickView.grabWindow()` (native).

## Results

### DPR 1

Full JSON: [`BOT-098F5_dpr1_both.json`](BOT-098F5_dpr1_both.json)

| | Python | Native |
| --- | ---: | ---: |
| Backend reported | `cpu` | `qt-quick-scene-graph` |
| Median | 41.327 ms | **0.320 ms** |
| p95 | 44.332 ms | **0.564 ms** |
| Updates/s | 26.55 | 2,751.53 |
| Physical width (px) | 1,570 | 1,600 |
| Displayed / represented markers | 12 / 31 | 26 / 26 |
| Crosshair final candle index | — (not exercised) | 5,278 (expected 5,278 ✅) |
| Qt warnings | 0 | 0 |

**Native/Python median speedup: 129.1×**

### DPR 2

Full JSON: [`BOT-098F5_dpr2_both.json`](BOT-098F5_dpr2_both.json)

| | Python | Native |
| --- | ---: | ---: |
| Backend reported | `cpu` | `qt-quick-scene-graph` |
| Median | 72.736 ms | **1.449 ms** |
| p95 | 77.915 ms | **1.611 ms** |
| Updates/s | 15.17 | 681.72 |
| Physical width (px) | 3,140 | 3,200 |
| Displayed / represented markers | 12 / 31 | 26 / 26 |
| Crosshair final candle index | — (not exercised) | 5,278 (expected 5,278 ✅) |
| Qt warnings | 0 | 0 |

**Native/Python median speedup: 50.2×**

Both runs report `device_pixel_ratio` correctly as `1.0` / `2.0` and scale
`physical_width` accordingly, confirming the DPR path is exercised, not
hardcoded.

## Retained-geometry semantic checks (native)

The native backend proves it does not rebuild bulk geometry on camera-only
movement, matching the `BOT-098F3`/`BOT-098F4` retained-renderer contract:

| Buffer | Retained across camera pan | Retained across pointer/crosshair move |
| --- | :---: | :---: |
| OHLCV | ✅ | ✅ |
| Volume | ✅ | ✅ |
| Indicator | ✅ | ✅ |
| Marker | ❌ (expected — see note) | ✅ |

Marker geometry is intentionally excluded from the camera-movement retention
claim: marker LOD is viewport-dependent (which markers are visible/collapsed
changes with the pan range), so it is recorded as an explicit diagnostic
rather than misreported as retained. Pointer-only movement has no viewport
change, so all four buffers — including markers — are required and confirmed
retained there.

## Visual semantic checks

`--ci-contract` intentionally does not assert real pixel colors offscreen —
that evidence is `--desktop-contract` territory (Windows RHI, real GPU
output), not a portable claim. The Python backend's offscreen `QWidget.grab()`
capture did happen to sample all four expected candle/indicator colors
(`#00c087`, `#f6465d`, `#00bfff`, `#f0b90b`) as `true` in both runs; the
native offscreen capture reported them `false`, which is expected and
non-blocking under `--ci-contract` for the reason above.

## Known-benign warning filtered from the contract

Both runs report `qt_warnings: []`. During harness development, the Python
backend's `QWidget.show()` under `QT_QPA_PLATFORM=offscreen` reliably emits
`"This plugin does not support propagateSizeHints()"` — a known limitation of
Qt's offscreen platform plugin (it has no real window to propagate size hints
to), unrelated to this application. `chart_migration_benchmark.py` filters
only this exact message; any other Qt warning or critical message still fails
the `qt_warnings must be empty` contract.

## What this does and does not prove

- **Proves:** on this machine, the native Qt Quick Scene Graph renderer is
  50–129× faster per camera update than the Python `pyqtgraph`-backed
  `ChartCard` on the identical fixture, at both DPR 1 and DPR 2; retains bulk
  geometry correctly during both camera and pointer interaction (except the
  documented marker/camera case); and produces zero Qt warnings.
- **Does not prove:** production-host performance (`BOT-098F6D` must rerun
  this profile after the `QQuickWidget` production host is wired), real
  desktop pixel-color correctness under a real GPU/RHI backend, or anything
  about Windows-specific rendering behavior — those remain
  `--desktop-contract` / Desktop E2E evidence on an actual Windows machine.
