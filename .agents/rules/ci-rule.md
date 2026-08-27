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

- `ruff check src tests` (read-only lint check);
- `ruff format --check src tests` (read-only format check);
- `mypy` static type check over `src` **and** `scripts` in one invocation
  (`EPIC-002`, sourced from `BUG-026` — a class implementing a Port silently
  fell behind an interface change; `ruff` cannot catch this, only a type
  checker can). Gated at the exact baseline `EPIC-002A` measured, not at
  zero — `[tool.mypy]` in `pyproject.toml` excludes `src/presentation/`
  wholesale (dominated by one systemic PySide6 `@Property`-typing false
  positive, not real defects) plus a named list of pre-existing dirty files
  frozen as debt (`EPIC-002D` tracks shrinking that list). A file not on
  that list must pass clean; `src` and `scripts` MUST be checked together —
  checking either alone lets an ABC-completeness error like `BUG-026`'s go
  undetected, because mypy then never resolves the Port's own defining
  module in the same analysis pass (verified empirically, see
  `Tasks/reports/EPIC-002A_mypy_baseline_audit.md` §3);
- `scripts/check_skill_prompt_references.py` — every repository path the
  scheduled-agent prompts under `.agents/Skills/` name must still resolve
  (`EPIC-011`, moved from `.jules/` and renamed in `EPIC-012`). Those prompts
  drive agents that run unattended, so a reference to a deleted file fails
  silently: the run completes and reports success. `sentinel.prompt.md` spent
  months pointing at a rule file with no commit in any branch's history. Needs
  neither Qt nor the engine, runs in milliseconds, and is verified in both
  directions (passes clean, fails on an injected broken reference);
- all primary tests under `tests/`, excluding `tests/sanity/` and the known
  unstable `tests/integration/presentation/ui/` group by default;
- `tests/sanity/` sequentially in a separate job;
- coverage for `src/`, with the required 80% threshold.

Full CI MUST exit `0`. A passing test count while lint, formatting, coverage, or
Sanity fails is a failed verification, not a successful handoff.

### Exception — commits that touch no code file

**Added 2026-08-21 (user request).** A commit whose diff touches **no** file
under `src/`, `tests/`, `scripts/`, and no file that affects build,
dependency or runtime behavior (`pyproject.toml`, `requirements.txt`,
`.qml`) does not require running `ci-local.ps1 -Full` or any test tier
before commit — there is no code change for a test to verify. This covers, for
example, a commit limited to `Tasks/`, `.agents/`, `README.md`, `Docs/`, or
other Markdown/doc-only files.

A commit that touches even one file able to affect build, runtime, lint, type
check, or test behavior still requires the full gate per §1 above — this
exception does not apply just because most of the diff is docs; it applies
only when *none* of the diff is code.

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

## 3. Qt integration directory — re-verified 2026-08-25, runs by default again

`tests/integration/presentation/ui/` used to be excluded from ordinary Full CI
for a known intermittent native Qt/PySide crash (`BOT-038`). Re-verified
2026-08-25 (triggered by `EPIC-009`): 7 runs — 4 single-process sequential, 3
under `-n 6` with `tests/sanity` running concurrently, matching this script's
real `-Full` load — produced zero crash markers. Leading hypothesis: `EPIC-006`
(2026-08-24) deleted `QQuickWidget`/QML from the application entirely, and
BOT-038's own top suspect was an object-lifetime bug tied to exactly that
class. Not proven by elimination alone; see BOT-038's closing note in
`Tasks/completed/`.

`-IncludeFlakyUi` is now a no-op kept only for command-line compatibility — the
directory runs in every mode. If a native crash resurfaces here, it is a *new*
finding: file a fresh bug rather than reopening `BOT-038`, since the mechanism
that bug named may no longer be present to cause it, and treating a new crash
as a known-flaky recurrence is how a real regression hides again.

Desktop E2E is a separate opt-in tier: it requires a real windowing session
(never `QT_QPA_PLATFORM=offscreen`), real Qt mouse/keyboard interaction,
deterministic local data, and an assertion that Qt stderr/message capture is
clean. Windows and macOS always have a real compositor; Linux only has one
when an X11/Wayland session is actually running (`DISPLAY`/`WAYLAND_DISPLAY`),
which typical headless CI runners do not — detect this generically rather
than gating on `sys.platform == "win32"`. A specific task's proof
requirements may still mandate the production target OS explicitly (e.g. real
pixel color under Windows' RHI backend) when platform-specific rendering
behavior is what is being verified; a same-machine real-display run is
supplementary local evidence, not a substitute for that. This tier does not
replace Full CI.

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
   blocker, report the evidence and keep the required deterministic coverage
   rather than declaring an unverified success. `BOT-038`'s exclusion was this
   kind of blocker for over a year — re-verify a standing "known flaky/crashy"
   exclusion periodically rather than trusting it indefinitely; it may have
   silently stopped being true.

## 6. Four-level test contract

Every feature is verified through exactly four test levels. Each level proves
only its own contract; higher levels never replace lower-level deterministic
coverage.

1. **Unit:** pure functions, data contracts, invariants and deterministic
   component behavior. No real app/container, network or timing gate.
   Constructing a bare widget/component directly (e.g. `ChartCard(...)`,
   `BackTestView()`) still counts as Unit as long as it does not boot the
   real app/DI container — the existing `qapp`-fixture convention across
   this codebase's component and screen tests.
2. **Integration:** deterministic application or visible UI journeys across
   real collaborators, with local seeded/fake boundaries. It proves the user
   flow, not just a private call or a mock expectation.
3. **Sanity:** real app boot, DI wiring and View/Presenter construction only;
   no user action, no background dispatch. It proves composition health —
   the app assembles, resolves and shuts down in silence — via a real
   composition-root boot plus a real subprocess launch, not QML checks
   (retired with `EPIC-006`, zero QML left in this app). "No network" means
   no code-path substitution for a port (that produced `BUG-026`/`BUG-027`);
   the network boundary is drawn at configuration instead — see
   `testing-rule.md`'s Sanity bullet and
   `Tasks/epics/EPIC-009_sanity_tier_redesign/` for the full model.
4. **Desktop E2E:** a critical visible journey through the **real running
   app** — started from its real entry point (e.g. `main.py` / `create_app()`
   booted for real) into the real production window/screen a user would
   actually see — on a real windowing session (not offscreen), using real Qt
   mouse/keyboard input, real render backend and clean Qt stderr/message
   capture. It is opt-in/local or nightly but mandatory evidence for changed
   rendering-critical UI code or reported GUI runtime defects. When a task's proof
   requirements name a specific production target OS (e.g. Windows RHI pixel
   evidence), that OS is still required; this tier's own definition does not
   restrict "real display" to Windows.

**Component probe (not a test level, not Desktop E2E):** a script that
constructs one isolated widget/host/QML piece directly (real rendering, real
Qt input) without going through the real app's entry point or production
wiring — e.g. proving a not-yet-integrated widget works before any screen
actually uses it. This is legitimate opt-in local evidence for a piece
that is not yet reachable from the real app. It is **not** interchangeable with
Desktop E2E and must never be reported as satisfying it: the instant a
feature becomes reachable from the real running app (wired into production
selection, not merely built and tested standalone), Desktop E2E — the real
entry point, the real screen — becomes required evidence before that feature
counts as done. A passing component probe proves the piece works in
isolation; it does not prove the app works.

An external-service smoke check is an opt-in operational check, not a fifth
test level and never a normal CI requirement. Passing a lower tier proves only
that tier's contract. In particular, a green Sanity or UnitOnly run never
proves a user journey or business acceptance contract.

**Why these levels, in this order — a V-model reading:** each tier verifies
exactly the artifact its matching development stage produces, same idea as
the classic V-model's level-to-level test mapping, without adopting its
waterfall sequencing (write-every-test-before-any-code, finish one whole side
of the V before starting the other). This codebase ships incrementally
(BOT-098F6A→F6B→F6C→F6D→F6E), so the mapping is read per-feature, live,
against however far that feature has actually been built — not planned
upfront for the whole system:

| Development stage | Test level |
| --- | --- |
| Module/function implementation | **Unit** |
| Cross-collaborator wiring within a feature | **Integration** |
| Whole-app boot/composition | **Sanity** |
| A piece built but not yet reachable from the real app | **Component probe** |
| Feature actually wired into the real running app | **Desktop E2E** |

The practical rule this gives: test only as far as a feature has actually
been integrated, never further ahead of it. A widget or host that is built
but not yet wired into a real screen has no business claiming Desktop E2E
evidence — nothing a real user runs reaches it yet, so a component probe is
the correct and honest tier, right up until the phase that wires it in
exists.

## 7. Benchmark evidence tier

`scripts/benchmarking/` is a diagnostic, not a gate tier. Its reports are local
evidence for sizing, regression detection and release judgment — not shared-CI
thresholds.

- `ci-local.ps1 -Full` still includes lint, format, primary and sequential
  sanity. It is the only local handoff evidence.

> **Sửa 2026-08-27:** dòng trên từng khẳng định *"CI for this project is
> local-only; there is no GitHub Actions workflow"*. **Sai tại thời điểm sửa** —
> `.github/workflows/ci.yml` tồn tại và đang chạy trên mọi push/PR tới
> `master-warrior` (đã bị xoá khỏi nhánh này một lần rồi được khôi phục; xem
> comment đầu chính file đó). Không tin dòng này nữa; xác nhận bằng
> `ls .github/workflows/`.
>
> Hai gate **không** phải bản sao của nhau — biết trước sự khác biệt trước khi
> coi một trong hai là đủ:
>
> | | `ci-local.ps1 -Full` | `.github/workflows/ci.yml` |
> | :--- | :--- | :--- |
> | Test primary | song song (`-n 6` mặc định) | tuần tự, một tiến trình |
> | Sanity | tách job riêng, luôn tuần tự | trộn chung trong `pytest tests/` |
> | Coverage gate 80% | có | có (từ 2026-08-27) |
> | Ruff/`mypy`/guard `.agents/Skills` | có cả 3 | có cả 3 (từ 2026-08-27) |
>
> Sự khác biệt về song song/tách job là **cố ý chưa đối chiếu lại** — không
> phải lỗi cần vá ngay, chỉ là chưa ai xác nhận CI có cần chạy y hệt cấu trúc
> local hay không. Đừng giả định một bên bao trùm bên kia.

---

## 8. Static quality, read-only gate, and the mandatory log scan

> **Nguồn (2026-08-25):** bốn mục dưới đây được **chuyển nguyên văn** từ
> `code-rule.md` §4 khi file đó được tách. Chúng nói về *chạy* gate CI nên
> thuộc file này, không thuộc [`testing-rule.md`](testing-rule.md) (vốn chỉ
> giữ cách *viết* test). Không có quy tắc nào bị đổi nghĩa.

- **Static quality:** Ruff lint/format plus architecture/import rules run on
  every commit and pull request; they support but do not replace the four test
  levels.
- **Read-only CI:** A CI verification command MUST not mutate the working tree. Use `ruff check` and `ruff format --check` in CI; reserve `--fix` and formatter writes for an explicit developer formatting action. A test runner that changes unrelated files is not an acceptable required quality gate.
- **Local CI/CD Enforcement:**
  - Always run `.\scripts\ci-local.ps1 -Full` to validate your code before finishing changes. This includes lint, format, coverage, Unit and Sanity checks; `-UnitOnly` is diagnostic-only and never sufficient for handoff or commit.
  - For lifecycle/concurrency work, add deterministic tests for stale-success, stale-failure, success-after-cancel, and cancellation during every relevant computation phase. Do not rely on timing sleeps to test races.
- **CI/CD MUST capture a log file, then scan it for problem levels:** A green
  exit code is not sufficient evidence that a run was clean. `scripts/ci-local.ps1`
  automates this — it captures every test run to a log file and runs
  `Invoke-RunLogScan` afterward, which greps for the problem levels
  `.agents/rules/logging-rule.md` §"Log levels" defines (`WARNING`, `ERROR`,
  `CRITICAL`) using that file's own documented matcher
  (`Select-String "- (WARNING|ERROR|CRITICAL) -"` / `grep -E '\- (WARNING|ERROR|CRITICAL) \-'`)
  and fails the run if any are found. This runs automatically on every
  `ci-local.ps1` invocation (both `-SanityOnly` and the Unit/Full path) — do
  this in the script, not by hand each time.
  Every hit the scan reports MUST be investigated and reported — never
  silently accepted because the tests still passed, and never bypassed with
  `-AllowLogWarnings` as a way to get a green build. Report each one as
  either (a) a real defect, which then follows `.agents/rules/bug-fix-rule.md`
  in full, or (b) an understood, explicitly justified expected condition,
  naming the reason. "It was already there before my change" is a reason to
  check whether it is a known open bug in `Tasks/bug_report/incomplete/`, not
  a reason to skip it. `-AllowLogWarnings` exists only to triage a run whose
  hits are already understood and recorded.
  This rule exists because a run can exit 0 while logging a real, silently
  degraded path — e.g. a realtime backtest that logged repeated
  `tick_gap_forced_commit` WARNINGs on every bar of every run (`BUG-022`: the
  bar-close condition never matched real exchange `close_time` values, so the
  closing tick of every bar was evaluated twice) and still reported success,
  or a chart query returning `rows=0` that produced a blank chart with no
  failure anywhere (`BUG-021`).

