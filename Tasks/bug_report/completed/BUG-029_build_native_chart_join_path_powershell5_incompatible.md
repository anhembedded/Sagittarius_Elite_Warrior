# BUG-029 — `build-native-chart.ps1` uses 3-4 argument `Join-Path`, incompatible with Windows PowerShell 5.1

**Reported:** 2026-08-21 — found while actually running `.\scripts\ci-local.ps1 -Full`
for the first time this session (previously only ran raw `pytest` commands,
never the real gate — a process gap the user called out directly).
**Severity:** 🔴 P1 — silently broke the mandatory `-Full` gate's native-build
step for anyone invoking it via Windows PowerShell 5.1 (`powershell.exe`),
which is the DEFAULT `powershell` on any Windows machine unless the user
explicitly runs `pwsh`. `ci-local.ps1` itself declares `#Requires -Version
5.1`, so this broke the exact compatibility contract the script claims.
**Status:** ✅ **Fixed 2026-08-21** — root-caused, fixed, verified on the
actual failing shell (PowerShell 5.1 with `$ErrorActionPreference = "Stop"`,
matching `ci-local.ps1`'s own invocation).

## Symptom

```
▶  CMake — Native Chart QML Plugin
❌  Native Chart Build FAILED
A positional parameter cannot be found that accepts argument 'Scripts'.
```

No stack trace in `ci-local.ps1`'s own output — its `try { & (Join-Path
$scriptDir "build-native-chart.ps1") } catch { Write-Host
$_.Exception.Message }` only prints the bare message.

Confusingly, calling `.\scripts\build-native-chart.ps1` directly (no
wrapping `ci-local.ps1`) worked fine — including via this session's own
`PowerShell` tool, which the harness documents as running **PowerShell 7+
(`pwsh`)**. That masked the bug for a while: every manual verification of
the native build this session used that tool and never hit it.

## Root cause

`Join-Path` gained multi-argument support (`-AdditionalChildPath`) in
**PowerShell 6+**. In **Windows PowerShell 5.1** (`powershell.exe` — the
default `powershell` on Windows, distinct from `pwsh.exe`), `Join-Path`
only accepts two positional arguments (`-Path`, `-ChildPath`). A 3rd or 4th
positional argument has nowhere to bind, and PowerShell reports it as
"a positional parameter cannot be found that accepts argument '<value>'"
— an unhelpful message that names the argument value, not the real cause.

`scripts/build-native-chart.ps1` had **four** such calls, all written
assuming PS7+ semantics:

```powershell
# line 41 — 4 args
$pythonExe = Join-Path $botRoot ".venv" $venvBinSubdir "python$exeSuffix"
# line 62 — 4 args
$qtRoot = Join-Path $toolchainsBase "Qt" $pysideVersion $qtToolchain
# line 65 — 5 args
$qtConfig = Join-Path $qtRoot "lib" "cmake" "Qt6" "Qt6Config.cmake"
# line 66 — 3 args
$qmakeExe = Join-Path $qtRoot "bin" "qmake$exeSuffix"
```

`ci-local.ps1` invokes this script from inside a `try` block with
`$ErrorActionPreference = "Stop"` set globally at its own top (line 74) —
promoting `Join-Path`'s non-terminating parameter-binding error into a
terminating exception, which is what the `catch` block actually caught.
Line 41 is reached first (before Qt SDK resolution), so that's the only one
that ever surfaced — lines 62/65/66 have the identical bug and would have
failed next, one at a time, on each successive re-run after fixing the
previous line, had they been fixed by trial and error instead of grepped
for as a class.

## Fix

`scripts/build-native-chart.ps1`: rewrote all four call sites as nested
2-argument `Join-Path` calls (PS 5.1-safe), e.g.:

```powershell
$pythonExe = Join-Path (Join-Path (Join-Path $botRoot ".venv") $venvBinSubdir) "python$exeSuffix"
$qtRoot = Join-Path (Join-Path (Join-Path $toolchainsBase "Qt") $pysideVersion) $qtToolchain
$qtConfig = Join-Path (Join-Path (Join-Path (Join-Path $qtRoot "lib") "cmake") "Qt6") "Qt6Config.cmake"
$qmakeExe = Join-Path (Join-Path $qtRoot "bin") "qmake$exeSuffix"
```

Matches the nested-`Join-Path` pattern already used elsewhere in this same
file (lines 32-33) and in `ci-local.ps1` itself (line 158) — this file was
the only one in `scripts/` with the multi-arg form; `ci-local.ps1`,
`run-chart-benchmark.ps1`, `preview-qml.ps1` were all already PS5.1-safe
(checked by grepping every `Join-Path` call site in `scripts/`).

## Regression test / verification

No unit test — this is a PowerShell script bug, no Python test tier covers
it. Verified by direct reproduction and re-run on the actual failing shell:

- **Before fix:** `powershell -Command` (Windows PowerShell 5.1) with
  `$ErrorActionPreference = 'Stop'` set (matching `ci-local.ps1`'s own top-
  of-file setting) → reproduced the exact reported failure, with a full,
  unswallowed exception confirming `ParameterBindingException` at
  `build-native-chart.ps1: line 41`.
- **After fix:** identical invocation → completes end-to-end, "Native chart
  plugin ready." Then ran the full `.\scripts\ci-local.ps1 -Full` (no
  `-SkipNativeBuild`) via the same PowerShell 5.1 shell — the native build
  step no longer appears in the failed-steps list.

## Note

Found only because the user pushed back on relying on the `PowerShell` tool
(PS7+) as a stand-in for how this project's own `ci-local.ps1` actually gets
invoked in practice (PS5.1, per its own `#Requires`). Verifying a script
compatibility claim requires running it on the shell it claims compatibility
with, not a more capable one that happens to be available.
