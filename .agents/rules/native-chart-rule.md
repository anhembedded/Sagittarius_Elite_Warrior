---
name: Native Chart Build and Deployment Rule
description: Mandatory build, ABI, staging, and verification rules for Sagittarius.NativeChart.
trigger: always_on
---

# Native Chart Build & Deployment Rule

This rule applies whenever an AI edits or verifies:

- `native/chart_renderer/`;
- native snapshot serialization/runtime discovery;
- CMake/native toolchain configuration;
- QML or Python code that requires `Sagittarius.NativeChart`;
- desktop packaging containing the native chart.

The user-facing command guide is
[`Docs/NATIVE_CHART_BUILD_AND_DEPLOY.md`](../../Docs/NATIVE_CHART_BUILD_AND_DEPLOY.md).

## 1. Build contract

Run from the bot root:

```powershell
.\scripts\build-native-chart.ps1
```

Use `-Clean` after a Qt/PySide/toolchain change or when stale CMake output is a
credible cause. Development output belongs only under
`build/native-chart/qml`; generated DLLs and CMake artifacts MUST NOT be
committed.

`run-ui.ps1 -Dev` does not build automatically. Before launching dev mode, the
AI MUST build the plugin when native source changed or no compatible runtime
exists. Never diagnose the UI against a stale DLL.

## 2. ABI safety

- The Qt MSVC SDK version MUST exactly equal `PySide6.__version__`.
- Never bypass the build script's mismatch check, edit the runtime manifest to
  fake compatibility, or copy a plugin built against another Qt version.
- A snapshot ABI change is atomic across native parser, Python serializer,
  manifest/expected ABI, tests, and documentation. Partial ABI migrations are
  forbidden.
- Native input remains untrusted at the boundary even if Python already
  validates it.

## 3. Deploy/stage contract

Ordinary source development needs build, not deploy. Deploy/stage is required
only for an explicitly requested packaged/frozen desktop artifact or package
verification.

Use CMake install; do not hand-copy individual DLLs:

```powershell
cmake --install .\build\native-chart `
    --config Release `
    --prefix <package-or-stage-root>
```

The deployed module is valid only when all of these exist under the same QML
import root:

```text
qml/native-chart-runtime.json
qml/Sagittarius/NativeChart/qmldir
qml/Sagittarius/NativeChart/sagittarius_native_chart.dll
qml/Sagittarius/NativeChart/sagittarius_native_chartplugin.dll
qml/Sagittarius/NativeChart/sagittarius_native_chart.qmltypes
```

For a frozen app, `qml/` belongs beside the executable. For an isolated stage,
verify through `SAGITTARIUS_NATIVE_QML_IMPORT_PATH`. CMake install does not
bundle the Python app or PySide6's Qt runtime; never claim a complete desktop
deployment from native staging alone.

Deploying into a user-selected package/release directory is an external write
and requires explicit user authorization. A requested code change or CI run
does not implicitly authorize release deployment.

## 4. Required verification

During development, run the focused native sanity/visual regression relevant
to the change. Before handoff, commit, merge, or completion, run:

```powershell
.\scripts\ci-local.ps1 -Full
```

Full CI must build native successfully and exit zero. `-SkipNativeBuild`,
`-UnitOnly`, or a successful CMake compilation alone is diagnostic evidence,
not completion evidence.

When staging a package, also verify that runtime discovery accepts the staged
manifest/module and that all five required artifacts exist. Do not weaken the
real Windows-backend visual probe merely because headless Qt cannot rasterize
custom scene-graph material.

## 5. Backtest migration and benchmark governance

- Native chart work follows independently verifiable slices: retained renderer
  (`BOT-098F1`…`F4`) → shared production-host A/B benchmark (`F5`) → Backtest
  port/Python adapter (`F6A`) → native snapshot host (`F6B`) → interaction
  wrapper (`F6C`) → opt-in cutover (`F6D`) → default rollout (`F6E`). An
  umbrella task is never evidence that its child slices are done.
- A native `QQuickView` probe is not a production Backtest performance claim.
  Before default selection, benchmark the real embedded `QQuickWidget` host
  with the same full fixture, `processEvents()` and completed `grabWindow()`.
- The standard profile is 6,420 ordered OHLCV candles, volume, five price
  overlays, 1,112 semantic markers, crosshair and 150 visible candles at
  1,600×900. Report DPR and physical-pixel column budget. Do not lower the
  workload, hide a feature or omit the final grab to obtain a better score.
- Performance reports are local diagnostic evidence, never a shared CI timing
  threshold. They must report median/p95, updates/s, requested/actual backend,
  environment, Qt warnings, visual color samples and retained-geometry
  diagnostics.
- The Backtest host contract is narrow and presentation-scoped. Only its
  factory/host modules may import both `ChartCard` and `NativeChartItem`; do
  not create a global ChartCard abstraction or make Dashboard adopt Backtest
  behavior.
- A `QWidget`/`QQuickWidget` host is transient and owned by one BackTestView.
  Backend selection occurs at view construction; live hot-swapping is forbidden.
- `auto` or `native` selects native only after runtime ABI validation and for a
  capability that native demonstrably supports. Unsupported Equity/BOTH/script
  annotations remain on the Python host; visual data must never silently vanish.
- Runtime, ABI, QML construction, snapshot or viewport failure must fall back
  to Python with one actionable diagnostic. A blank chart is never an allowed
  fallback state.
- Python prepares immutable snapshots and native validates them again. The
  adapter owns monotonically increasing revisions, action/preview fencing and
  timestamp-to-index alignment; camera/pointer movement must not rebuild bulk
  OHLCV/volume/indicator/marker geometry.

