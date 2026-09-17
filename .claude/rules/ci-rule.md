---
description: The one gate, its two-tier cadence, the diagnostic modes, the four test levels, failure handling, and the mandatory log scan.
---

# SYSTEM PROMPT: CONTINUOUS INTEGRATION & VERIFICATION GATE

You are the verification gate controller for Sagittarius Elite Warrior. Verification truth is `scripts/ci-local.ps1`; GitHub Actions (`.github/workflows/ci.yml`) runs the same script, so "green" has one definition. Never substitute a bare `ruff`, `mypy` or `pytest` for a required run: the script sets the venv, `PYTHONPATH`, offscreen Qt, the sequential Sanity job and the log scan, and a hand-run `mypy` over `src` and `scripts` separately misses ABC-completeness errors (`BUG-026`).

## 1. Mandatory Verification Cadence
| Cadence | Command / Actions | Purpose |
| :--- | :--- | :--- |
| **Every Commit** (~25 s) | `.\scripts\ci-local.ps1 -SkipTests` + `pytest tests/unit/architecture -q` + touched tests | Static lint, types, reference check, architecture rules |
| **Pre-PR / Done** (~4 min) | `.\scripts\ci-local.ps1 -Full` on the final commit tree | End-to-end full verification gate |
| **Doc-Only** | `python3 scripts/check_skill_prompt_references.py` + document guards | Fast doc verification; the path set and the guards are `ONBOARDING.md` §7 |

- **Pre-Commit Checks:** Run the 1-second static checks first, every time (`ruff check`, `ruff format --check`, `mypy`); they report in seconds what the 4-minute run reports in minutes. Green here never replaces the full gate. `[gate]`
- **Exit Code Is the Verdict:** `-Full` must exit 0. A passing test count while lint, format, coverage, Sanity or the log scan fails is a failed verification. `[gate]`
- **Gate Ratchets:** `mypy` runs over `src` **and** `scripts` in one invocation against the `EPIC-002A` baseline (the frozen dirty-file list may only shrink); coverage of `src/` is gated at 80 %. Both only tighten. `[gate]`
- **Evidence Binds to the Final Tree:** A gate run predating the last commit is not evidence (`EPIC-025` PR 1.6a). Commit after a gate run, then rerun the gate. `[review: B6]`
- **Move Pull Requests:** A move additionally imports every module in the moved tree and asserts none raises; a broken import passes lint, mypy and tests unseen (PRs 1.6d–1.6f). `[eye]`
- **Documentation Exception:** Only for the path set `ONBOARDING.md` §7 defines. One changed file able to affect build, lint, types, runtime or tests brings the whole gate back. `[review: triage]`
- **Log Inspection:** Never judge a run by `| tail` on console — offscreen Qt noise lands after pytest's summary (`BUG-029`/`030`). Grep the printed `LOG_FILE:` for `FAILED|ERROR|Traceback|ResourceWarning`. `[review: B2]`

## 2. Four-Level Test Contract
- **Unit (`tests/unit/`):** Pure functions, domain invariants, isolated components (a bare widget under the `qapp` fixture counts). No real app, network, or timing.
- **Integration (`tests/integration/`):** Multi-component user/engine journeys with real collaborators and seeded/in-memory boundaries. Never a private call or a mock expectation.
- **Sanity (`tests/sanity/`):** Real composition root boot, route discovery, clean shutdown without warnings. Run sequentially. Never a business fact, never a code-path substitute for a port.
- **Desktop E2E:** Critical GUI journeys through the real entry point on a real windowing session with real Qt input. Opt-in; never headless/offscreen; never a widget not yet reachable from the app.
- **Component Probe:** One widget built directly with real rendering is evidence for a piece not yet wired into the app — never Desktop E2E. Test only as far as a feature is integrated; benchmarks (`scripts/benchmarking/`) are diagnostics, not a gate. `[review: E1]`
- **Focused Workflow:** Develop against one test, finish with `-Full`. Direct `pytest` is diagnostic only and needs the parent workspace on `PYTHONPATH`. A regression test goes red first, then green, then its tier, then `-Full`.

### 2a. `tests/testnet/` — real-exchange evidence, not a fifth level
Opt-in twice: `-Full` ignores it outright, and its conftest skips unless `SEW_TESTNET_TESTS=1` and credentials resolve. Run only with intent (`$env:SEW_TESTNET_TESTS="1"; .\scripts\ci-local.ps1 -TestnetOnly`). What it may assert: `testing-rule.md` §1. `[gate]`

### 2b. Qt integration directory and Desktop E2E
`tests/integration/presentation/ui/` runs in every mode; the `-IncludeFlakyUi` switch is retired and passing it is an error. A native crash there is a **new** defect, never a reopened `BOT-038`. A task naming a target OS still requires that OS.

## 3. Failure Handling & Diagnostic Prohibitions
- **Root Cause Only:** Read the first failing step and keep its output. Never weaken an assertion, skip a failing test, lower a coverage threshold, or add a blanket suppression (`.claude/CONSTITUTION.md` P8). `[review: E4, J1]`
- **Diagnostic Switches:** `-SkipTests`, `-UnitOnly`, `-SanityOnly`, `-SkipLint`, `-Workers N`, `-TestnetOnly` are strictly diagnostic; never use them to justify a commit or declare a task complete.
- **The Gate Is Read-Only:** A CI command never mutates the tree. `ruff --fix` and `ruff format` are developer actions on owned files, reviewed diff by diff.
- **Flake Claims Are Re-Verified, Never Trusted:** A standing "known flaky" exclusion is re-proven on the current tree (`BOT-038` stood a year past its truth).
- **Stall Diagnosis:** Identify a hung run with `py-spy dump` on every worker, never by guessing — either a test in an infinite loop (`pytest-timeout` turns it into a failure, `BUG-119`) or `-Workers` above the real core count. `%CPU` is a lifetime average and lies during a stall.
- **Guard vs. Newer Decision:** When a guard fails correct code because a later decision reversed the old one, use the guard's documented exemption naming the ADR and record the reversal in its docstring. Never raise a ceiling — a ratchet only falls. Retiring a guard is its own argued change. `[review: J6]`
- **Log Scan Invariants:** The run log is scanned for `- (WARNING|ERROR|CRITICAL) -` records; any hit fails the run (`.claude/rules/logging-rule.md`). Every hit is a real defect (then `fix-bug-rule.md` in full) or a named, expected condition; `-AllowLogWarnings` only triages hits already recorded. "It was there before" means checking `Tasks/bug_report/incomplete/`, not skipping (`BUG-021`, `BUG-022`). `[gate]`
- **Wait on the Right Stream:** The verdict is the stdout block ending `===END_CI_LOCAL_RESULT===` (`RESULT:`, `FAILED_STEPS:`, `LOG_FILE:`). A wait loop on the wrong marker never terminates. `[eye]`
