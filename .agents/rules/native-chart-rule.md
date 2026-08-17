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

