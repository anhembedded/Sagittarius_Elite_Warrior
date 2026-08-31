---
name: Local CI Execution Rule
description: The mandatory verification command, the test levels, and how to handle a red gate.
trigger: always_on
---

# CI Rule & Run Guide

**There must be exactly ONE command that is the source of truth for local
verification.** If the repository has none, create it before doing anything
else — a script that locates the virtual environment, sets up the required
environment, and runs every step below.

```bash
<CI_CMD>
```

**Never substitute a bare test command for a required gate run.** A bare
command may not boot the project in the same import/runtime environment the
script sets up, and usually skips the log-scanning step at the end.

---

## 1. The mandatory gate — before handoff, commit, merge, or claiming "done"

`<CI_CMD>` must run **all** of:

- **lint + format in read-only mode** (`<LINT_CMD>`);
- **static type checking** (`<TYPECHECK_CMD>`) over `<SRC_DIR>` **and**
  `scripts/` **in a single invocation** — checking them separately can let an
  "incomplete implementer" error through, because the type checker then never
  resolves the interface's defining module in the same pass;
- **all primary tests** (`<TEST_DIR>`);
- **the boot/sanity tier, sequentially**, in a separate job;
- **coverage**, at the agreed threshold;
- **a guard test for the agent documentation itself**, if the repository runs
  automated agents — every repository path their prompts name must still
  resolve. For an unattended agent a broken link **fails silently**: the run
  completes and reports success.

The gate must exit `0`. **Tests passing while lint, format, coverage or sanity
is red is a FAILED verification**, not a successful handoff.

If the type checker is gated at a **baseline** rather than at zero (a list of
legacy dirty files), then: any file **not** on that list must be clean, and the
list may only ever get **shorter**.

### Exception — commits that touch no code file

A commit whose diff touches **no** file under `<SRC_DIR>`, `<TEST_DIR>`,
`scripts/`, and no file affecting build/dependency/runtime behaviour
(manifests, lockfiles, build configuration) does **not** require the gate —
there is no code change for a test to verify. This covers, for example, a
commit limited to documentation, task files, or `.agents/`.

Touching **one** file able to affect build, runtime, lint, type checking or
tests still requires the full gate. This exception does **not** apply because
"most of the diff is docs"; it applies only when **none** of the diff is code.

---

## 2. Diagnostic modes — never sufficient on their own

| Purpose | Example | Replaces the gate? |
| :--- | :--- | :---: |
| Fast feedback | unit tests only | **No** |
| Diagnosing boot/DI | sanity only | **No** |
| Reproducing a parallelism issue | gate with 1 worker | **No** |
| Diagnosing tests alone | gate, skipping lint | **No** |
| Diagnosing static checks alone | gate, skipping tests | **No** |

Every "skip" flag is a **diagnostic tool**. They MUST NOT be used to bypass a
failing required gate, to justify a commit, or to mark a task complete.

**Don't raise the worker count for speed without measuring.** Measured on a
real 4-core machine: 6 workers → ~147s; 12 workers → ~150s. Doubling the
workers **changed nothing** — workers beyond core count only add contention.
Check `nproc` first, and treat every timing number as specific to one machine.

---

## 3. Handling a red gate

1. **Read the FIRST failing step and preserve its output.**
2. **Fix the root cause.** Don't weaken assertions, skip tests, lower the
   coverage threshold, or add a broad ignore just to make the gate green.
3. **Formatting is an explicit developer action, not a CI action.** CI must be
   **read-only**: use `--check` modes, never let CI rewrite files. A test runner
   that changes unrelated files is not an acceptable quality gate. Run the fix
   command by hand, **review every diff** (especially in unrelated files), then
   re-run the gate.
4. **Don't commit while the gate is red.** If it is an established external
   blocker, report the evidence and **keep** the required coverage, rather than
   declaring an unverified success.
5. **Periodically re-verify every "known flaky/crashy" exclusion.** In the
   original repository a test directory sat excluded from CI for over a year as
   "known flaky"; when someone finally measured it again (7 runs, sequential and
   parallel) it **did not reproduce once** — the underlying cause had been
   deleted from the codebase long before. A standing exclusion is where a real
   regression hides.

---

## 4. The four test levels

Every feature is verified across exactly four levels. **Each level proves only
its own contract**; a higher level never replaces a lower level's deterministic
coverage.

1. **Unit** — pure functions, data contracts, invariants, deterministic
   component behaviour. No real app/DI boot, no network, no timing waits.
   *(Constructing a widget/component directly still counts as Unit, as long as
   it doesn't boot the real app.)*
2. **Integration** — a **deterministic** user/application journey across
   **real** collaborators, with outer boundaries seeded or faked **locally**. It
   proves the **flow**, not a private call or a mock expectation. Never depends
   on a real external service.
3. **Sanity** — a **real** boot, real DI wiring, real view/controller
   construction. No user actions, no background dispatch. It proves
   **composition health**: the app assembles, resolves, and shuts down **in
   silence**.
4. **E2E** — a visible journey through the **real running application**,
   started from its real entry point, with real user input and real output.
   Opt-in / nightly, but **mandatory evidence** for changes to
   rendering/interaction code and for any reported GUI or runtime defect.

**A component probe is not a test level, and is not E2E.** A script that
constructs one isolated piece directly (real rendering, real input) **without**
going through the entry point or production wiring — proving, say, that a
not-yet-integrated widget works. It is legitimate local evidence for **a piece
nothing in the real app can reach yet**. It does **not** substitute for E2E:
**the moment** that feature becomes reachable from the real app, E2E becomes
required evidence. A green probe proves the piece works in isolation; it does
**not** prove the app works.

An external-service smoke check is an opt-in operational check, **not** a fifth
test level and never a normal CI requirement.

### 4.1 Why these four, in this order — a V-model reading

Each tier verifies exactly the artifact its matching development stage
produces — the same level-to-level mapping idea as the classic V-model,
**without** its waterfall sequencing. The project ships incrementally, so the
mapping is read **per feature, live**, against how far that feature has
actually been built — not planned up front for the whole system:

| Development stage | Test level |
| :--- | :--- |
| Implementing a module/function | **Unit** |
| Wiring collaborators within a feature | **Integration** |
| Whole-app boot/composition | **Sanity** |
| A piece built but not yet reachable from the real app | **Component probe** |
| A feature actually wired into the real running app | **E2E** |

The practical rule this yields: **test exactly as far as a feature has actually
been integrated, never ahead of it.**

### 4.2 Sanity must scale at zero

- **Adding a feature/screen adds ZERO new tests to the sanity tier.** Every
  assertion here must **scan a real source of truth** (every registered use
  case, every navigable route, every screen package on disk) — never a
  hand-written per-feature test. If a new screen needs a new sanity test, the
  existing sanity tests were written wrong.
- **One real boot for the whole session**, not one per test.
- **Silence is the assertion:** an autouse guard must fail on any framework
  message, any log record at WARNING or above, or any warning raised during
  boot/construct/shutdown. A green exit code is **not** enough.
- **The only permitted substitution is the network boundary, drawn at
  CONFIGURATION, never at a code path** — point the real client at a local fake
  server; **never** hand-write a stand-in for a port. That exact shape produced
  two real bugs (a fake implementer left behind after an interface change).
- **No assertion at this tier may name a business fact** — that belongs to
  Integration.
- There is an **out-of-process** layer (launching the real entry point as a real
  subprocess) — the only tier that can prove the process **actually exits**,
  rather than proving a teardown function returned.

---

## 5. Mandatory: capture the log to a file, then SCAN it

**A green exit code is not sufficient evidence that a run was clean.**

The gate script must **capture every run to a log file**, then scan that file
itself for the problem levels (`WARNING`, `ERROR`, `CRITICAL` — see
[`logging-rule.md`](logging-rule.md)) using that file's own documented matcher,
and **fail the run if any are found**. Do this **in the script**, not by hand
each time.

```bash
<CI_CMD> > /tmp/ci.log 2>&1
grep -nE '\- (WARNING|ERROR|CRITICAL) \-' /tmp/ci.log
```

**Every hit MUST be investigated and reported** — never silently accepted
because "the tests still passed", and never bypassed with an
allow-warnings flag just to get a green build. Report each one as either:

- **(a) a real defect** — which then follows
  [`bug-fix-rule.md`](bug-fix-rule.md) in full; or
- **(b) an understood, explicitly justified expected condition**, naming the
  reason.

*"It was already there before my change"* is a reason to **check whether it is a
known open bug**, not a reason to skip it.

> **Why this rule exists:** a run can exit `0` while logging a **silently
> degraded** path — real examples: a loop logging a WARNING on **every step of
> every run** because a comparison never matched real values (so every step was
> evaluated twice), and a query returning `rows=0` that produced a blank chart —
> with **nothing failing anywhere**.

---

## 6. The benchmark tier

Benchmarks are **diagnostics, not a gate**. Their reports are local evidence
for sizing, regression detection and release judgement — **not** shared CI
thresholds.

---

## 7. The local gate and server CI are not copies of each other

If the repository has **both**, know the differences before treating either as
sufficient:

| | Local gate | Server CI |
| :--- | :--- | :--- |
| Primary tests | usually parallel | usually sequential |
| Sanity | separate job, sequential | may be mixed in |
| Coverage / lint / type check | ? | ? |

**Fill this table by reading both configuration files, not from memory.** In
the original repository, a line in this very rule file once asserted "this
project has no server CI" — false; the workflow existed and was running.
Confirm with `ls .github/workflows/` (or the equivalent), don't trust the
documentation. And **never assume one gate subsumes the other.**
