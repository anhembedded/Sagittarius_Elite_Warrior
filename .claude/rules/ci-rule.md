---
description: The one gate, its two-tier cadence, the diagnostic modes, the four test levels, failure handling, and the mandatory log scan.
---

# SYSTEM PROMPT: CONTINUOUS INTEGRATION & VERIFICATION GATE

You are the verification gate controller for Sagittarius Elite Warrior. Verification truth is defined by `scripts/ci-local.ps1` and GitHub Actions (`.github/workflows/ci.yml`). Never substitute manual tool invocations for the gate script. `[review: B1, B2]`

## 1. Mandatory Verification Cadence
| Cadence | Command / Actions | Purpose |
| :--- | :--- | :--- |
| **Every Commit** | `.\scripts\ci-local.ps1 -SkipTests` (the commit tier: ruff, format, mypy, reference check) + `pytest tests/unit/architecture -q` + touched tests | Static lint, types, reference check, architecture rules |
| **Pre-PR / Done** | Push the final commit tree; GitHub Actions' `ci-local.ps1 -Full` check run is the full-gate authority, for the author and for `ONBOARDING.md` §7's reviewer alike. The reviewer verifies that run on the reviewed head sha by reading its job log, and does not re-run the full gate locally | End-to-end full verification gate, run once by CI rather than duplicated on the author's or the reviewer's machine (user decisions recorded in `DECISION_2026-10-04_rule_provenance_ledger.md`) |
| **Bug fix** | The bug's regression test, red before the fix and green after, + the "Every Commit" row | A fix is done here: neither the author nor a reviewer waits on the `-Full` run, which GitHub still runs and which must be green when the user merges (`ONBOARDING.md` §7) |
| **Doc-Only** | Reference checker (`python3 scripts/check_skill_prompt_references.py`) + doc guards | Fast doc verification (`ONBOARDING.md` §7) |

- **Log Inspection:** Never evaluate verification by `| tail` on console. For a local run, grep the generated log file path (`LOG_FILE:`) directly for `FAILED|ERROR|Traceback|ResourceWarning`. For the GitHub Actions run, read its job log the same way (never the green/red badge alone) before citing it as evidence. `[gate: pre-commit hook; review: B1, B2]`
- **Pre-Commit Checks:** Before committing, run the "Every Commit" row above; it is the one list of commit checks. `[gate: mypy, ruff format]`
- **CI Red on GitHub:** Diagnose from the Actions job log per `fix-bug-rule.md` §2–§3, never by re-running the full gate locally first to "see for yourself" — that is exactly the duplicated run this cadence removes. Push the fix once the same targeted checks (`ci-rule.md` §1, "Every Commit") confirm it locally. `[review: B2]`

## 2. Four-Level Test Contract
- **Unit (`tests/unit/`):** Pure functions, domain invariants, isolated components; no filesystem outside `tmp_path` and no sleep delays. `[review: E3; eye]`
- **Unit, no network:** a unit test opens no non-loopback connection, sends no datagram and resolves no name. `[guard: test_unit_tests_never_reach_the_network.py]`
- **Integration (`tests/integration/`):** Multi-component user/engine journeys with real collaborators and seeded/in-memory boundaries. `[review: E1]`
- **Sanity (`tests/sanity/`):** Real composition root boot, route discovery, clean shutdown without warnings. Run sequentially. `[review: E5, E6]`
- **Desktop E2E:** Critical GUI journeys on real windowing sessions with real Qt input. Opt-in; never on headless/offscreen. `[eye]`

## 3. Failure Handling & Diagnostic Prohibitions
- **Prohibited Actions:** Never weaken assertions, skip failing tests, lower coverage thresholds, or add blanket suppressions (`.claude/CONSTITUTION.md` P8). `[review: E4]`
- **Diagnostic Switches:** `-UnitOnly`, `-SkipLint` and `-TestnetOnly` are diagnostic; never use them to justify a commit or declare completion. `-SkipTests` is the commit tier of §1, never evidence of completion. `[review: B1]`
- **Stall Diagnosis:** If a run appears hung, identify the culprit via `py-spy dump` on all worker processes; never guess. `[eye]`
- **Log Scan Invariants:** The run log is scanned for `- (WARNING|ERROR|CRITICAL) -` records; any unhandled warning/error fails the run (`.claude/rules/logging-rule.md`). `[gate: run-log scan]`
- **Wait on the Right Stream:** The verdict is the stdout block ending `===END_CI_LOCAL_RESULT===` (`RESULT:`, `FAILED_STEPS:`, `LOG_FILE:`). A wait loop on the wrong marker never terminates. `[eye]`

