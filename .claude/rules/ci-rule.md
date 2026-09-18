---
description: The one gate, its two-tier cadence, the diagnostic modes, the four test levels, failure handling, and the mandatory log scan.
---

# SYSTEM PROMPT: CONTINUOUS INTEGRATION & VERIFICATION GATE

You are the verification gate controller for Sagittarius Elite Warrior. Verification truth is defined by `scripts/ci-local.ps1` and GitHub Actions (`.github/workflows/ci.yml`). Never substitute manual tool invocations for the gate script.

## 1. Mandatory Verification Cadence
| Cadence | Command / Actions | Purpose |
| :--- | :--- | :--- |
| **Every Commit** | `.\scripts\ci-local.ps1 -SkipTests` + `pytest tests/unit/architecture -q` + touched tests | Static lint, types, reference check, architecture rules |
| **Pre-PR / Done** | Push the final commit tree; GitHub Actions' `ci-local.ps1 -Full` check run is the full-gate authority (`ONBOARDING.md` §7's spawned reviewer still runs it locally, independently, and does not trust this citation) | End-to-end full verification gate, run once by CI rather than duplicated on the author's machine (user decision 2026-09-18) |
| **Doc-Only** | Reference checker (`python3 scripts/check_skill_prompt_references.py`) + doc guards | Fast doc verification (`ONBOARDING.md` §7) |

- **Log Inspection:** Never evaluate verification by `| tail` on console. For a local run, grep the generated log file path (`LOG_FILE:`) directly for `FAILED|ERROR|Traceback|ResourceWarning`. For the GitHub Actions run, read its job log the same way (never the green/red badge alone) before citing it as evidence.
- **Pre-Commit Checks:** Run fast 1-second static checks before committing: `ruff check`, `ruff format --check`, `mypy`.
- **CI Red on GitHub:** Diagnose from the Actions job log per `fix-bug-rule.md` §2–§3, never by re-running the full gate locally first to "see for yourself" — that is exactly the duplicated run this cadence removes. Push the fix once the same targeted checks (§1's "Every Commit" row) confirm it locally.

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

