---
name: Local CI Execution Rule
description: Mandatory local CI commands, verification tiers, and failure handling.
trigger: always_on
---

# Local CI Rule & Run Guide

`scripts/ci-local.ps1` is the single source of truth for local verification. It finds the local
venv, sets the required package alias/PYTHONPATH, forces Qt offscreen, keeps Sanity sequential
and runs the primary tier in parallel. Never substitute a bare `pytest.exe` for a required CI
run — it may not boot the project under the same import or Qt environment.

## 1. Required verification

### Run the 1-second checks first — always, before the 4-minute one

```powershell
.\scripts\ci-local.ps1 -SkipTests   # Ruff lint + Ruff format + Mypy + skill refs
```

**Measured 2026-09-14: this takes 1 second.** It runs the *same* four static steps
the full gate runs, with the same configuration — so anything it catches, the full
gate would have caught four minutes later.

This is not a style preference, it is a lesson with a receipt. On 2026-09-14 the
full gate was run 23 times in one session and blocked 5 times. Every block was a
real defect and none was a false alarm — but **two of the five were Mypy-only**
(`EPIC-025` PR 0.4a: five baseline entries still keyed to pre-move paths, exposing
21 pre-existing SQLAlchemy errors; PR 0.4a-3: a `sum(1 for ...)` resolving to the
wrong overload). Both were catchable in one second, and both were instead
discovered after a four-minute test run. That is ~8 minutes spent learning what a
2-second habit would have said, plus the cost of losing the thread while waiting.

Do not substitute a bare `ruff`/`mypy` invocation for it. `mypy` run by hand over
`src` and `scripts` separately, or without the script's `MYPYPATH`, fails on a
duplicate `__main__` module and resolves imports differently — the script exists
because the environment matters (§"Never substitute a bare `pytest.exe`" applies
to the type checker too).

Green here does **not** replace the full gate; it only means the full gate will not
fail on lint or typing.

### Full gate — required before handoff, commit, merge, or claiming completion

Run from the bot root (`Sagittarius_Elite_Warrior/`), not the parent workspace:

```powershell
cd Sagittarius_Elite_Warrior
.\scripts\ci-local.ps1 -Full   # -Full is also the default: .\scripts\ci-local.ps1
```

`-Full` runs:

- `ruff check src tests` and `ruff format --check src tests` (both read-only). `ruff check` is not
  style-only: `EPIC-004` extended `[tool.ruff.lint] extend-select` in `pyproject.toml` with `S`
  (Bandit-equivalent security rules — hardcoded secrets, unsafe `subprocess`), `PLR2004` (magic
  number), `B` (bug pattern), `SIM` (code smell), `ERA` (dead code), and `N` (naming) — the closest
  Python equivalent to a MISRA-style safety/quality layer, since `mypy` alone only catches type
  errors. Gated at a measured baseline the same way mypy is: baseline audit first
  (`Tasks/reports/EPIC-004A_ruff_security_quality_baseline_audit.md` — ~48 real findings out of
  4491 raw hits, ~99% system noise), then wired in as a hard gate with the real findings fixed
  (`EPIC-004D`). Every per-file-ignore this required lives in `pyproject.toml` itself
  (`[tool.ruff.lint.per-file-ignores]`), each with an inline comment naming the reason (e.g.
  `assert` in tests, Qt override methods forced into camelCase) — never a bare suppression;
- `mypy` over `src` **and** `scripts` **in one invocation** (`EPIC-002`). Checked separately, mypy
  never resolves a Port's own defining module in the same pass, so an ABC-completeness error goes
  undetected — that is `BUG-026`, a class implementing a Port silently falling behind an interface
  change, which ruff cannot catch (verified empirically, `Tasks/reports/EPIC-002A_mypy_baseline_audit.md` §3).
  Gated at the `EPIC-002A` baseline, not zero: `[tool.mypy]` in `pyproject.toml` excludes
  `src/presentation/` wholesale (one systemic PySide6 `@Property` false positive, not real defects)
  plus a frozen dirty-file list (`EPIC-002D` shrinks it). A file off that list must pass clean;
- `scripts/check_skill_prompt_references.py` — every repository path named by the unattended
  scheduled-agent prompts under `.agents/Skills/` must still resolve (`EPIC-011`/`EPIC-012`); a
  dangling reference fails silently and still reports success (`sentinel.prompt.md` pointed at a
  nonexistent rule file for months);
- all primary tests under `tests/`, excluding `tests/sanity/`;
- `tests/sanity/` sequentially in a separate job;
- coverage for `src/`, with the required 80% threshold.

Full CI MUST exit `0`. A passing test count while lint, formatting, coverage or Sanity fails is
a failed verification, not a successful handoff.

### Exception — commits that touch no code file

A commit whose diff touches **no** file under `src/`, `tests/`, `scripts/`, and no file affecting
build, dependency or runtime behavior (`pyproject.toml`, `requirements.txt`, `.qml`) needs no CI
run — nothing to verify; typically a diff limited to `Tasks/`, `.agents/`, `README.md`, `Docs/` or
other Markdown. Applies only when *none* of the diff is code, not merely when most of it is docs:
one file able to affect build, runtime, lint, type check or test behavior brings back the gate.

## 2. Diagnostic modes — never enough by themselves

| Purpose | Command | What it does | May replace Full? |
| --- | --- | --- | :---: |
| Fast local feedback | `.\scripts\ci-local.ps1 -UnitOnly` | Unit tests plus sequential Sanity, no lint/format or coverage gate | No |
| Boot/DI/QML diagnosis | `.\scripts\ci-local.ps1 -SanityOnly` | Sanity only, sequential, no lint/format or coverage gate | No |
| Reproduce a parallel issue | `.\scripts\ci-local.ps1 -Full -Workers 1` | Full gate with deterministic single-worker primary tests | No |
| Use fewer/more workers | `.\scripts\ci-local.ps1 -Full -Workers 4` | Full gate with the requested primary-test worker count | No |
| Diagnose tests only | `.\scripts\ci-local.ps1 -Full -SkipLint` | Full test/coverage tier without static checks | No |
| Static checks only — **run this first, every time** (§1) | `.\scripts\ci-local.ps1 -SkipTests` | Ruff lint + Ruff format + Mypy + skill refs, no tests. 1 second. Not a substitute for the gate | No |
| Real Binance Futures Testnet (`EPIC-021J`) | `$env:SEW_TESTNET_TESTS=1; .\scripts\ci-local.ps1 -TestnetOnly` | `tests/testnet/` only, sequential, no lint/format or coverage gate | No |

`-SkipLint`, `-SkipTests`, `-UnitOnly`, `-SanityOnly` and `-TestnetOnly` are diagnostic tools.
They MUST NOT be used to bypass a failing required gate, justify a commit, or mark a task complete.

**A run that looks hung has two causes, and they are told apart by `py-spy`, not by guessing.**

*Cause 1 — a test in an infinite loop* (`BUG-119`, 2026-09-14). One test never returns, so its
worker never reports, the xdist controller waits for it forever, and the other workers drain their
queues and go idle. It looks exactly like a deadlock and it is not: it is one ordinary bug. Tells:
the run stops at the **same test count every time** (three runs stopped at 3993, two logs
byte-identical in size), and `py-spy dump --pid <worker>` shows one worker inside application code
while the rest sit in `execnet.serve()`. `pytest-timeout` (§1) now turns this into a normal failure
naming the test and the line, so it should not recur silently — but read the dump before concluding.

*Cause 2 — `-n` oversubscribing past actual core count* on a box with fewer than 6 real cores: most
workers' CPU time frozen for minutes while only one or two still tick up. Several xdist workers end
up CPU-starved rather than making forward progress, and no worker is stuck in application code.

**Two traps when diagnosing either.** `ps`'s `%CPU` is an average over each process's whole
lifetime, not an instantaneous reading — during a stall it shows idle workers at 40-95%, which reads
as "busy" and is wrong. And **dump every worker**: on 2026-09-14 only the two with the largest
resident memory were dumped, the result was stated as if all four, and the hanging worker was one of
the two skipped — which is how `BUG-119` was first filed with the wrong root cause. `$Workers`' default (`min(logical processor
count, 6)`) already avoids this on a smaller machine; it only resurfaces if `-Workers` is passed
explicitly above the real core count. Confirm before killing anything: `ps aux` (Linux) / Task
Manager (Windows) — worker CPU time genuinely frozen across two checks a few seconds apart, not
merely low, is the tell; a worker still climbing, even slowly, is not hung.

`-TestnetOnly` is not a fifth mandatory tier — see §3a. `-Full` (and every other mode) excludes
`tests/testnet/` via `--ignore`, never runs it, and never will: it touches the real exchange with
real credentials, which a gate that runs on every commit must never depend on.

### 3a. `tests/testnet/` — real-exchange evidence, not a fifth test tier

Opt-in only, gated twice: `-Full`'s own `--ignore` (never runs it, any mode) **and** the tier's own
`conftest.py` fixture (`SEW_TESTNET_TESTS=1` *and* resolvable Futures Testnet credentials, checked
separately so a missing-one run skips with a reason naming which). One gate already failed once in
this repo's history — a conditional-skip-only tier ran for real the moment someone had the right
environment variable set by accident — so two independent layers is the fix, not decoration.

Run it only with intent, never as part of a routine gate:

```powershell
$env:SEW_TESTNET_TESTS = "1"
.\scripts\ci-local.ps1 -TestnetOnly
```

Missing either gate condition skips with a distinct, readable reason. `testing-rule.md`'s own
testnet-tier section covers what this tier is allowed to assert and why it stays this small.

## 3. Qt integration directory and Desktop E2E

`tests/integration/presentation/ui/` runs by default in every mode. The `-IncludeFlakyUi` switch
that used to control it was **retired 2026-09-07** — passing it is now an error, not a no-op.
Its old `BOT-038` exclusion was cleared by re-verification
on 2026-08-25 (7 runs, sequential and under `-n 6` with `tests/sanity` concurrent, zero crash
markers; closing note in `Tasks/completed/`). **A native crash resurfacing here is a *new*
finding — file a fresh bug, do not reopen `BOT-038`:** that bug's mechanism may no longer exist,
and treating a new crash as a known-flaky recurrence is how a real regression hides.

Desktop E2E is a separate opt-in tier and never replaces Full CI. It requires a real windowing
session (never `QT_QPA_PLATFORM=offscreen`), real Qt mouse/keyboard interaction, deterministic
local data, and clean Qt stderr/message capture asserted. Windows and macOS always have a
compositor; Linux only with a running X11/Wayland session (`DISPLAY`/`WAYLAND_DISPLAY`), which
typical headless runners lack — detect this generically, not via `sys.platform == "win32"`. A task
whose proof requirements name a production target OS (e.g. real pixel color under Windows' RHI
backend) still requires that OS; a same-machine real-display run is supplementary, not a substitute.

## 4. Focused test workflow

Develop against a focused test, finish with `-Full`. Direct pytest is diagnostic only (never a
substitute for the script) and needs the parent workspace on `PYTHONPATH`:

```powershell
$workspaceRoot = (Resolve-Path ..).Path
$env:PYTHONPATH = $workspaceRoot
& .\.venv\Scripts\python.exe -m pytest tests\unit\domain\strategies\test_multi_ema_trend_follower_strategy.py -v
```

For a regression: run the single new test first to show it fails before the fix and passes
after, retain it permanently, then the relevant unit/integration tier, then `-Full`.

## 5. Failure handling

1. Read the first failing step and preserve its output.
2. Fix the root cause; never weaken assertions, skip tests, lower coverage, or add a broad
   ignore to turn the gate green.
3. Ruff auto-fixing is an explicit developer action, never a CI action:

   ```powershell
   & .\.venv\Scripts\ruff.exe check --fix src tests
   & .\.venv\Scripts\ruff.exe format src tests
   ```

   Review every resulting diff, especially in unrelated files, then rerun
   `.\scripts\ci-local.ps1 -Full`. CI itself MUST stay read-only: no `--fix`, no formatter writes.
4. Do not commit while Full CI is red. For an established external blocker, report the evidence
   and keep the deterministic coverage rather than declaring an unverified success. Re-verify
   any standing "known flaky/crashy" exclusion periodically instead of trusting it indefinitely
   — `BOT-038`'s stood for over a year and had silently stopped being true (§3).
5. **A guard that fails on correct code because a newer decision reversed the old one** is the one
   case item 2 above does not cover, and it is ordinary in a repository mid-redesign rather than
   exotic. `EPIC-007F` required every new widget to inherit the kit's `Card`/`Panel`/`Overlay`;
   ADR D20–D22 then made a dialog a plain `QDialog`, so `test_widget_guards_hold.py` reported
   correct code as a violation. The resolution, in this order:

   1. Use the guard's **own documented exemption** — `# base-exempt: <reason>`,
      `# token-exempt: <reason>` — and name the ADR in the reason. The line goes through review,
      which is the point: each exception stays deliberate and countable.
   2. **Never raise the ceiling instead.** A ratchet raised to admit new code admits the old
      shape too, and the number stops meaning anything. A ratchet may only fall.
   3. Record the reversal in **that guard's docstring**, so the next reader finds the decision
      instead of re-deriving it — and the guard keeps earning its keep by making every exception
      a reviewed line.
   4. A guard the newer decision has overtaken **completely** is its own change, argued in the
      guard and in the ADR that replaced it — never loosened in passing to get a diff through.

## 6. Four-level test contract

Every feature is verified through exactly four levels. Each proves only its own contract; higher
levels never replace lower-level deterministic coverage.

1. **Unit:** pure functions, data contracts, invariants, deterministic component behavior. No
   real app/container, network or timing gate. Constructing a bare widget/component directly
   (e.g. `ChartCard(...)`, `BackTestView()`) is still Unit as long as it does not boot the real
   app/DI container — this codebase's existing `qapp`-fixture convention.
2. **Integration:** deterministic application or visible UI journeys across real collaborators,
   with local seeded/fake boundaries. Proves the user flow, not a private call or a mock
   expectation.
3. **Sanity:** real app boot, DI wiring and View/Presenter construction only; no user action, no
   background dispatch. Proves composition health — the app assembles, resolves and shuts down
   in silence — via a real composition-root boot plus a real subprocess launch, not QML checks
   (retired with `EPIC-006`, zero QML left). "No network" means no code-path substitution for a
   port (that shape produced `BUG-026`/`BUG-027`); the boundary is drawn at configuration —
   see `testing-rule.md`'s Sanity bullet and `Tasks/epics/EPIC-009_sanity_tier_redesign/`.
4. **Desktop E2E:** a critical visible journey through the **real running app** — its real entry
   point (e.g. `main.py` / `create_app()` booted for real) into the real production window a
   user would see — on a real windowing session (not offscreen), with real Qt mouse/keyboard
   input, real render backend and clean Qt stderr/message capture. Opt-in local or nightly, but
   mandatory evidence for changed rendering-critical UI code or reported GUI runtime defects. A
   task naming a production target OS (e.g. Windows RHI pixel evidence) still requires that OS;
   this tier's own definition does not restrict "real display" to Windows.

**Component probe (not a test level, not Desktop E2E):** a script constructing one isolated
widget/host/QML piece directly (real rendering, real Qt input) without the real app's entry point or
production wiring — e.g. proving a not-yet-integrated widget works before any screen uses it.
Legitimate opt-in local evidence for a piece not yet reachable from the real app, but **never
interchangeable with Desktop E2E and never reportable as satisfying it.** The instant a feature
becomes reachable from the real running app (wired into production selection, not merely built and
tested standalone), Desktop E2E — real entry point, real screen — is required evidence before it
counts as done. A passing probe proves the piece works in isolation, not that the app does.

An external-service smoke check is an opt-in operational check, not a fifth level and never a normal
CI requirement. Passing a lower tier proves only that tier's contract: a green Sanity or UnitOnly
run never proves a user journey or a business acceptance contract.

**Why these levels, in this order — a V-model reading:** each tier verifies exactly the artifact its
matching development stage produces, as in the V-model's level-to-level mapping, but without its
waterfall sequencing. This codebase ships incrementally (BOT-098F6A→F6B→F6C→F6D→F6E), so the mapping
is read per-feature and live, against how far that feature has actually been built:

| Development stage | Test level |
| --- | --- |
| Module/function implementation | **Unit** |
| Cross-collaborator wiring within a feature | **Integration** |
| Whole-app boot/composition | **Sanity** |
| A piece built but not yet reachable from the real app | **Component probe** |
| Feature actually wired into the real running app | **Desktop E2E** |

The practical rule: test only as far as a feature has actually been integrated, never further
ahead. A widget built but not wired into a real screen cannot claim Desktop E2E evidence —
nothing a real user runs reaches it yet.

## 7. Benchmark evidence tier, and the two CI gates

`scripts/benchmarking/` is a diagnostic, not a gate tier: local evidence for sizing, regression
detection and release judgment, never shared-CI thresholds.

`ci-local.ps1 -Full` is the only local handoff evidence, but **not** the only CI:
`.github/workflows/ci.yml` also exists and runs on every push/PR to `master-warrior` (deleted from
this branch once, then restored; see the comment at the top of that file) — confirm with
`ls .github/workflows/`. The two gates are **not** copies of each other — know the differences
before treating either one as sufficient:

| | `ci-local.ps1 -Full` | `.github/workflows/ci.yml` |
| :--- | :--- | :--- |
| Primary tests | parallel (`-n min(logical cores, 6)` by default — see §1's `-Workers`) | sequential, single process |
| Sanity | separate job, always sequential | mixed into `pytest tests/` |
| 80% coverage gate | yes | yes (since 2026-08-27) |
| Ruff/`mypy`/`.agents/Skills` guard | all 3 | all 3 (since 2026-08-27) |

The parallelism/job-separation difference is **deliberately not reconciled yet**, not a defect to
patch immediately. Do not assume either side subsumes the other.

## 8. Static quality, read-only gate, and the mandatory log scan

- **Static quality:** Ruff lint/format plus architecture/import rules run on every commit and
  pull request; they support but do not replace the four test levels.
- **Read-only CI:** a CI verification command MUST not mutate the working tree (§5.3 holds the
  developer-side formatting action). A test runner that changes unrelated files is not an
  acceptable required quality gate.
- **Local CI/CD enforcement:** always run `.\scripts\ci-local.ps1 -Full` before finishing
  changes. For lifecycle/concurrency work add deterministic tests for stale-success,
  stale-failure, success-after-cancel, and cancellation during every relevant computation phase
  — never timing sleeps to test races.
- **CI/CD MUST capture a log file, then scan it for problem levels.** A green exit code is not
  evidence that a run was clean. `scripts/ci-local.ps1` automates this on every invocation
  (`-SanityOnly` and the Unit/Full path alike): it captures each test run to a log file, then
  `Invoke-RunLogScan` greps for the problem levels defined in
  [`logging-rule.md`](logging-rule.md) §"Log levels" (`WARNING`, `ERROR`, `CRITICAL`) using that
  file's own matcher (`Select-String "- (WARNING|ERROR|CRITICAL) -"` /
  `grep -E '\- (WARNING|ERROR|CRITICAL) \-'`) and fails the run on any hit. Do this in the
  script, not by hand.

  Every hit MUST be investigated and reported — never silently accepted because tests passed,
  never bypassed with `-AllowLogWarnings` to get a green build. Report each as either (a) a real
  defect, which then follows [`bug-fix-rule.md`](bug-fix-rule.md) in full, or (b) an understood,
  explicitly justified expected condition, naming the reason. "It was already there before my
  change" is a reason to check `Tasks/bug_report/incomplete/` for a known open bug, not a reason
  to skip it. `-AllowLogWarnings` exists only to triage hits already understood and recorded.

  Why: `BUG-022` — a realtime backtest logged a `tick_gap_forced_commit` WARNING on every bar of
  every run (the bar-close condition never matched real exchange `close_time` values, so each bar's
  closing tick was evaluated twice) and still exited 0; `BUG-021` — a chart query returned `rows=0`,
  producing a blank chart with no failure anywhere.
