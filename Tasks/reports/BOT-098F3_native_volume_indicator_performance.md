# BOT-098F3 — Native volume and indicator performance evidence

**Fixture:** 6,420 OHLCV candles, 5 price-overlay indicators, 150-candle
viewport, retained `NativeChartItem` on Windows / Qt 6.11.1.

The probe calls the real C++ QML item, measures `setViewport()` plus a real
window grab, and fails if pan causes volume or indicator geometry to rebuild.
It is diagnostic evidence from the local machine, not a shared CI time gate.

| Display scale | DPR | Physical indicator columns | Median camera | p95 | Updates/s | Geometry rebuilt during pan |
| --- | ---: | ---: | ---: | ---: | ---: | :---: |
| 100% | 1.0 | 1,600 | 8.312 ms | 8.837 ms | 119.27 | No |
| 200% (`QT_SCALE_FACTOR=2`) | 2.0 | 3,200 | 16.617 ms | 19.385 ms | 59.37 | No |

At 100%, retained geometry contains 38,520 volume vertices and 32,100
indicator vertices. The source geometry is intentionally retained across a
same-span pan; only the camera transform changes. Scale 200% roughly doubles
the physical rendering work, which is expected: visual fidelity is preserved
rather than silently lowering resolution.

## Comparison with the current Python chart

The two probes were rerun consecutively on the same Windows machine at 100%
scale, `1600x900`, with the same 6,420-candle source and 150-candle viewport.
Both measurements include a real window grab rather than timing a setter
alone.

| Renderer / payload | Median | p95 | Updates/s |
| --- | ---: | ---: | ---: |
| Current PyQtGraph Backtest: candles, volume, 5 indicators, 1,112 stored markers (12 active), crosshair | 41.089 ms | 75.444 ms | 22.05 |
| Native F3: retained candles, volume, 5 indicators, camera-only pan | 8.313 ms | 8.787 ms | 120.17 |

For the overlapping candle/volume/indicator rendering path, native F3 is
about **4.9x lower median latency**, **8.6x lower p95**, and **5.5x higher
update throughput** in this local run. The important architectural difference
is that a same-span pan retains its volume/indicator GPU geometry instead of
asking Qt's Python/QGraphicsView pipeline to repaint and re-submit the visible
data on each range change.

This is deliberately **not yet a full end-user A/B claim**: the production
Python measurement includes truthful marker labels and crosshair/tooltip;
native F3 does not yet implement those layers and is not wired into the
Backtest screen. `BOT-098F4` must add native marker/crosshair/tooltip plus dev
FPS, then `BOT-098F5` can measure the production integration with an
equivalent interaction payload. Until then, users still see the PyQtGraph
chart and therefore do not automatically receive this improvement.

## Semantic proof

- Volume buckets retain the exact sum of their source values and take the final
  candle's direction only as their display color.
- Every dense indicator pixel column retains both its minimum and maximum;
  sparse columns become exact samples.
- Device pixel ratio affects native geometry's physical-column budget only. It
  does not affect the Backtest marker readability budget, which is correctly
  measured in logical UI pixels.

## Reproduce

```powershell
# From Sagittarius-Engine workspace root.
.\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m `
  Sagittarius_Elite_Warrior.scripts.benchmarking.native_chart_camera_probe

$env:QT_SCALE_FACTOR = '2'
.\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m `
  Sagittarius_Elite_Warrior.scripts.benchmarking.native_chart_camera_probe
Remove-Item Env:QT_SCALE_FACTOR
```
