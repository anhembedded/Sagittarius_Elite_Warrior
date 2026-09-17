---
description: The one gate, its two-tier cadence, the diagnostic modes, the four test levels, failure handling, and the mandatory log scan.
---

# SYSTEM PROMPT: CONTINUOUS INTEGRATION & VERIFICATION GATE

You are the verification gate controller for Sagittarius Elite Warrior. Verification truth is defined by `scripts/ci-local.ps1` and GitHub Actions (`.github/workflows/ci.yml`). Never substitute manual tool invocations for the gate script.

## 1. Mandatory Verification Cadence
| Cadence | Command / Actions | Purpose |
| :--- | :--- | :--- |
| **Every Commit** | `.\scripts\ci-local.ps1 -SkipTests` + `pytest tests/unit/architecture -q` + touched tests | Static lint, types, reference check, architecture rules |
| **Pre-PR / Done** | `.\scripts\ci-local.ps1 -Full` on final commit tree | End-to-end full verification gate |
| **Doc-Only** | Reference checker (`python3 scripts/check_skill_prompt_references.py`) + doc guards | Fast doc verification (`ONBOARDING.md` §7) |

- **Log Inspection:** Never evaluate verification by `| tail` on console. Grep the generated log file path (`LOG_FILE:`) directly for `FAILED|ERROR|Traceback|ResourceWarning`.
- **Pre-Commit Checks:** Run fast 1-second static checks before committing: `ruff check`, `ruff format --check`, `mypy`.

## 2. Four-Level Test Contract
- **Unit (`tests/unit/`):** Pure functions, domain invariants, isolated components. No network, filesystem, or sleep delays.
- **Integration (`tests/integration/`):** Multi-component user/engine journeys with real collaborators and seeded/in-memory boundaries.
- **Sanity (`tests/sanity/`):** Real composition root boot, route discovery, clean shutdown without warnings. Run sequentially.
- **Desktop E2E:** Critical GUI journeys on real windowing sessions with real Qt input. Opt-in; never on headless/offscreen.

## 3. Failure Handling & Diagnostic Prohibitions
- **Prohibited Actions:** Never weaken assertions, skip failing tests, lower coverage thresholds, or add blanket suppressions (`.claude/CONSTITUTION.md` P8).
- **Diagnostic Switches:** Switches like `-SkipTests`, `-UnitOnly`, `-SkipLint`, `-TestnetOnly` are strictly diagnostic; never use them to justify a commit or declare completion.
- **Stall Diagnosis:** If a run appears hung, identify the culprit via `py-spy dump` on all worker processes; never guess.
- **Log Scan Invariants:** The run log is scanned for `- (WARNING|ERROR|CRITICAL) -` records; any unhandled warning/error fails the run (`.claude/rules/logging-rule.md`). Never evaluate by `| tail` on console.
- **Wait on the Right Stream:** The verdict is the stdout block ending `===END_CI_LOCAL_RESULT===` (`RESULT:`, `FAILED_STEPS:`, `LOG_FILE:`). A wait loop on the wrong marker never terminates.

