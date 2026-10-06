# BOT-160 — The GitHub gate runs in two parallel parts

**Status:** ✅ Done (2026-10-06)
**Source:** the user, 2026-10-06: "oki tách 2 job song song đi" (okay, split it into two parallel jobs). This followed the CI timing measurement.
**Risk:** 🟡 — the required check must keep its name, and it must fail, not be skipped, when a part fails
**Complexity:** S — the gate script and the workflow
**Depends on:** BOT-159

---

## 1. Context and problem
The gate ran as one GitHub job of about 6.4 minutes; 306 s of it was one pytest run of unit and integration with coverage. The unit tier was about three quarters of that test time (177 s of 234 s locally). The measurement estimated about 4.7 minutes if unit ran on its own runner, beside the static checks, integration and sanity.

## 2. Acceptance criteria
- [x] Two parts run at once and together run what `-Full` runs: `-Part Unit` runs tests/unit alone; `-Part Rest` runs the static checks, every other tier and sanity.
- [x] The required check `ci-local.ps1 -Full` keeps its name. It passes only when both parts passed and their combined coverage holds the 80% floor. It runs and fails, rather than being skipped, when a part fails.
- [x] A local `-Full` run is unchanged.

## 3. Design
- `ci-local.ps1 -Part {All|Unit|Rest}`, where `All` is the default. A part leaves the coverage floor to the combining job, since half the tests' percentage means nothing, and prints no coverage report. The Unit part skips lint and sanity, which the Rest part runs.
- The workflow has three jobs:
  - a matrix job `gate (Unit)` / `gate (Rest)`, each part writing `COVERAGE_FILE` and uploading it;
  - the job `ci-local.ps1 -Full` (`needs: part`, `if: always()`), which fails on any part that did not succeed, runs `coverage combine` and `coverage report --fail-under=80`, and prints the result block.
- `ci-rule.md` §1 says the job logs to read are the two parts'.

## Implementation notes (written when done)
- Local proof, both parts at once with 2 workers each:
  - Unit: 8,443 passed, sanity deferred to Rest.
  - Rest: lint, format, mypy and reference check passed; 292 passed and 3 skipped; sanity passed.
  - Each run's verdict was `RESULT: PASS`.
  - Their coverage files combined to 97%, and `coverage report --fail-under=80` exited 0.
- The first proof on GitHub is this pull request's own run: two `gate` part jobs and the combining check.
