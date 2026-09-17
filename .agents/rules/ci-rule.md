---
name: Local CI Execution Rule
description: The one gate, its two-tier cadence, the diagnostic modes, the four test levels, failure handling, and the mandatory log scan.
trigger: always_on
---

# The gate

`scripts/ci-local.ps1` is the single source of truth for verification; GitHub Actions runs the same script (`.github/workflows/ci.yml`), so "green" has one definition. Never substitute a bare `pytest`, `ruff` or `mypy` for a required run: the script sets the venv, `PYTHONPATH`, offscreen Qt, the sequential Sanity job and the log scan, and `mypy` run by hand over `src` and `scripts` separately misses ABC-completeness errors (`BUG-026`).

## 1. Required verification

**Two tiers, both mandatory** (user decision 2026-09-16):

| When | What | Cost |
| :--- | :--- | :--- |
| every commit | `.\scripts\ci-local.ps1 -SkipTests` (ruff, format, mypy, reference check) **plus** `pytest tests/unit/architecture -q` **plus** the tests the diff touches | ~25 s |
| before a pull request is offered, merged or called done | `.\scripts\ci-local.ps1 -Full` on the **final** commit's tree, log file grepped | ~4 min |

- Run the 1-second checks first, every time; they catch what the 4-minute run would report four minutes later. Green here does not replace the full gate. `[gate]`
- A gate run before the last commit is not evidence (`EPIC-025` PR 1.6a). Commit after the gate → run the gate again. `[review: B6]`
- A **move** pull request adds one check: import every module in the moved tree and assert none raises (three defects in PRs 1.6d–1.6f were an import that stopped resolving, invisible to lint, mypy and tests). `[eye]`
- `-Full` runs, from the bot root: `ruff check` and `ruff format --check` over `src tests tools scripts`; `mypy` over `src` **and** `scripts` in one invocation, gated at the `EPIC-002A` baseline (`[tool.mypy]` excludes `src/presentation/` and a frozen dirty-file list that may only shrink); `scripts/check_skill_prompt_references.py`; every test under `tests/` except `tests/sanity/` (parallel) and `tests/testnet/`; `tests/sanity/` sequentially; coverage of `src/` at ≥80 %; the run-log scan (§8). Full CI must exit 0 — a passing test count while lint, format, coverage, Sanity or the scan fails is a failed verification. `[gate]`

**Exception — documentation-only.** A diff touching only the paths `ONBOARDING.md` §7 defines as documentation needs no gate run. One file able to affect build, lint, types, runtime or tests brings the whole gate back. `[review: triage]`

## 2. Diagnostic modes — never sufficient
`-UnitOnly`, `-SanityOnly`, `-SkipLint`, `-SkipTests`, `-Workers N`, `-TestnetOnly`. They MUST NOT be used to bypass a failing required gate, justify a commit, or mark a task complete.

**A run that looks hung** has two causes, told apart by `py-spy dump` on **every** worker, never by guessing: a test in an infinite loop (same stop count every run; `pytest-timeout` now turns it into a failure — `BUG-119`) or `-Workers` above the real core count. `ps`'s `%CPU` is a lifetime average and lies during a stall.

### 3a. `tests/testnet/` — real-exchange evidence, not a fifth tier
Opt-in twice: `-Full` ignores it outright **and** its conftest skips unless `SEW_TESTNET_TESTS=1` and credentials resolve. Run only with intent: `$env:SEW_TESTNET_TESTS="1"; .\scripts\ci-local.ps1 -TestnetOnly`. What it may assert: `testing-rule.md` §1. `[gate]`

## 3. Qt integration directory and Desktop E2E
`tests/integration/presentation/ui/` runs in every mode (the `-IncludeFlakyUi` switch is retired; passing it is an error). A native crash there is a **new** bug, never a reopened `BOT-038`. Desktop E2E is opt-in, on a real windowing session (never offscreen), real input, clean Qt stderr; it never replaces the gate, and a task naming a target OS still requires that OS.

## 4. Focused test workflow
Develop against one test, finish with `-Full`. Direct pytest is diagnostic only and needs the parent workspace on `PYTHONPATH` (`$env:PYTHONPATH = (Resolve-Path ..).Path`). For a regression: the new test red first, then green, then the tier, then `-Full`.

## 5. Failure handling
1. Read the first failing step; keep its output.
2. Fix the root cause. Never weaken an assertion, skip a test, lower coverage or add a broad ignore. `[review: E4, J1]`
3. `ruff --fix` and `ruff format` are developer actions on the files you own, reviewed diff by diff; CI stays read-only.
4. Never commit while a required check is red. A standing "known flaky" exclusion is re-verified, not trusted (`BOT-038` stood a year past its truth).
5. **A guard that fails correct code because a newer decision reversed the old one** (e.g. `EPIC-007F` vs ADR D20–D22): use the guard's own documented exemption naming the ADR; never raise a ceiling (a ratchet only falls); record the reversal in the guard's docstring; retiring the guard entirely is its own argued change. `[review: J6]`

## 6. Four-level test contract
| Level | Proves | Never |
| :--- | :--- | :--- |
| **Unit** | pure functions, invariants, one component (a bare widget under the `qapp` fixture counts) | real app, network, timing |
| **Integration** | a user or application journey across real collaborators with seeded/fake boundaries | a private call or a mock expectation |
| **Sanity** | the real composition root boots, resolves and shuts down in silence; a real subprocess launch | a business fact; a code-path substitute for a port (network boundary drawn at configuration) |
| **Desktop E2E** | a critical journey through the real entry point on a real display with real input | offscreen; a widget not yet reachable from the app |

A **component probe** (one widget built directly, real rendering) is evidence for a piece not yet wired into the app, never Desktop E2E. Test only as far as a feature is integrated. Benchmarks (`scripts/benchmarking/`) are diagnostics, not a gate. `[review: E1]`

## 7. One gate, two runners
`ci-local.ps1 -Full` is the handoff evidence; GitHub Actions runs the same script on push and pull request to `master-warrior`, uploading `logs/` on failure. The only differences are the machine (worker count derives from cores) and that GitHub runs after the merge as well. `[guard: none — the workflow calls the script, so there is nothing to compare]`

## 8. Static quality, read-only gate, log scan
- Static rules run on every commit and support the four levels; they never replace them.
- A CI command must not mutate the tree.
- For lifecycle/concurrency work add deterministic tests for stale-success, stale-failure, success-after-cancel and cancellation mid-phase — never timing sleeps.
- **Wait on the right stream.** The verdict is the stdout block ending `===END_CI_LOCAL_RESULT===` (`RESULT:`, `FAILED_STEPS:`, `LOG_FILE:`); `PowerShell transcript end` lives only in the log file. A wait loop on the wrong marker never terminates (55 minutes lost, 2026-09-14). `[eye]`
- **The run log is scanned** for `- (WARNING|ERROR|CRITICAL) -` records and any hit fails the run. Every hit is either a real defect (then `bug-fix-rule.md` in full) or an understood, named, expected condition; `-AllowLogWarnings` only triages hits already recorded. "It was there before" means check `Tasks/bug_report/incomplete/`, not skip (`BUG-021`, `BUG-022`). `[gate]`
- Never judge by `| tail`: offscreen Qt noise lands after pytest's summary. Redirect to a file, grep `FAILED|ERROR|Traceback|ResourceWarning` in the `LOG_FILE:` the script prints (`BUG-029`/`030`). `[review: B2]`
