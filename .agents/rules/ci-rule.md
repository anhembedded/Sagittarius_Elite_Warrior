---
name: Local CI Execution Rule
description: Mandatory local CI commands, verification tiers, and failure handling.
trigger: always_on
---

# Local CI Rule & Run Guide

`scripts/ci-local.ps1` is the single source of truth for local verification.
Run it from the bot root (`Sagittarius_Elite_Warrior/`), not from the parent
workspace:

```powershell
cd Sagittarius_Elite_Warrior
.\scripts\ci-local.ps1 -Full
```

The script finds the local virtual environment, establishes the required Python
package alias/PYTHONPATH, sets Qt to offscreen mode, and keeps Sanity sequential
while running the primary test tier in parallel. Do not replace a required CI
run with a bare `pytest.exe` command; it may not boot the project under the same
import or Qt environment.

## 1. Required verification

### Full gate — required before handoff, commit, merge, or claiming completion

```powershell
.\scripts\ci-local.ps1 -Full
# equivalent default:
.\scripts\ci-local.ps1
```

`-Full` runs:

- CMake configure/build for the `Sagittarius.NativeChart` QML plugin, using a
  Qt SDK whose version exactly matches the active PySide6 runtime;
- `ruff check src tests` (read-only lint check);
- `ruff format --check src tests` (read-only format check);
- all primary tests under `tests/`, excluding `tests/sanity/` and the known
  unstable `tests/integration/presentation/ui/` group by default;
- `tests/sanity/` sequentially in a separate job;
- coverage for `src/`, with the required 80% threshold.

Full CI MUST exit `0`. A passing test count while lint, formatting, coverage, or
Sanity fails is a failed verification, not a successful handoff.

`-SkipNativeBuild` is a Python-only diagnostic escape hatch. Like `-SkipLint`
and `-SkipTests`, it never qualifies as commit, merge, or release evidence.

## 2. Diagnostic modes — never enough by themselves

| Purpose | Command | What it does | May replace Full? |
| --- | --- | --- | :---: |
| Fast local feedback | `.\scripts\ci-local.ps1 -UnitOnly` | Unit tests plus sequential Sanity, no lint/format or coverage gate | No |
| Boot/DI/QML diagnosis | `.\scripts\ci-local.ps1 -SanityOnly` | Sanity only, sequential, no lint/format or coverage gate | No |
| Reproduce a parallel issue | `.\scripts\ci-local.ps1 -Full -Workers 1` | Full gate with deterministic single-worker primary tests | No |
| Use fewer/more workers | `.\scripts\ci-local.ps1 -Full -Workers 4` | Full gate with the requested primary-test worker count | No |
| Diagnose tests only | `.\scripts\ci-local.ps1 -Full -SkipLint` | Full test/coverage tier without static checks | No |
| Diagnose static checks only | `.\scripts\ci-local.ps1 -Full -SkipTests` | Ruff checks without tests | No |

`-SkipLint`, `-SkipTests`, `-UnitOnly`, and `-SanityOnly` are diagnostic tools.
They MUST NOT be used to bypass a failing required gate, justify a commit, or
mark a task complete.

## 3. Qt integration exception (BOT-038)

`tests/integration/presentation/ui/` is excluded from ordinary Full CI because
it has a known intermittent native Qt/PySide crash (`BOT-038`). When a change
touches that directory, QML object lifetime, native chart rendering, or shared
Qt fixtures, run the affected test(s) directly as a focused diagnosis and then
attempt the opt-in suite:

```powershell
.\scripts\ci-local.ps1 -Full -IncludeFlakyUi
```

If the native suite crashes or hangs, do not hide it with `-SkipTests`. Record
the command, environment, affected test(s), and failure output against
`BOT-038`. A targeted non-flaky regression test is still required for the code
change.

Desktop E2E is a separate opt-in tier: it requires a Windows desktop runner,
real Qt mouse/keyboard interaction, deterministic local data, and an assertion
that Qt stderr/message capture is clean. It does not replace Full CI.

## 4. Focused test workflow

Use a focused test while developing, then finish with `-Full`. If direct pytest
is needed, run it with the parent workspace on `PYTHONPATH`; this is diagnostic
only and does not replace the script:

```powershell
$workspaceRoot = (Resolve-Path ..).Path
$env:PYTHONPATH = $workspaceRoot
& .\.venv\Scripts\python.exe -m pytest tests\unit\domain\strategies\test_multi_ema_trend_follower_strategy.py -v
```

For a regression, run the single new test first to show it fails before the
fix, then passes after the fix; retain it permanently. Run the relevant unit /
integration tier next, and run `-Full` last.

## 5. Failure handling

1. Read the first failing step and preserve its output.
2. Fix the root cause; do not weaken assertions, skip tests, lower coverage, or
   add a broad ignore merely to turn the gate green.
3. If Ruff reports a fixable issue, formatting is an explicit developer action,
   not a CI action:

   ```powershell
   & .\.venv\Scripts\ruff.exe check --fix src tests
   & .\.venv\Scripts\ruff.exe format src tests
   ```

   Review every resulting diff, especially unrelated files, then rerun
   `.\scripts\ci-local.ps1 -Full`. CI itself MUST remain read-only and MUST
   use neither `--fix` nor formatter writes.
4. Do not commit while Full CI is red. If the failure is an established external
   blocker (for example the native crash documented in `BOT-038`), report the
   evidence and keep the required deterministic coverage rather than declaring
   an unverified success.

## 6. Test-tier contract

- **Unit:** pure business rules and invariants.
- **Application/integration:** deterministic command/query and UI user flows.
- **Sanity:** app boot, DI wiring, and QML construction only; no user action,
  background dispatch, or network.
- **Desktop E2E:** critical visible journeys with real desktop input, opt-in.
- **External smoke:** opt-in real-service boundary checks; never a normal gate.

Passing a lower tier proves only that tier's contract. In particular, a green
Sanity or UnitOnly run never proves a user journey, native render runtime, or
business acceptance contract.
