---
name: Bug Fix Rule
description: Mandatory workflow for diagnosing and fixing a reported bug — root cause first, never a hotfix (redesign the mechanism when it can recur elsewhere), log evidence for both reproduction and fix, regression test before the fix, correct test tier, permanent test, documented report.
trigger: always_on
---

# BUG FIX WORKFLOW

This file owns the whole bug-fix workflow — the single source of truth.

## 1. Diagnose the root cause first — never guess

- Read the actual failure evidence (traceback, log, screenshot) and the real source it
  points at before writing a line of fix code. "Plausible hypothesis" is not "root cause":
  trace the exact call chain the error came from.
- State the root cause explicitly before touching the fix — what causes the bug, and why
  the planned fix resolves it cleanly without crossing architectural layer boundaries.
- **Read [`Docs/CASE_STUDIES/README.md`](../../Docs/CASE_STUDIES/README.md) first when the gate
  was green while the defect was live.** It is the catalogue of blind spots this repository has
  already paid for, one screen each, and every entry carries a *"where else this is still open"*
  list written by someone who had just finished understanding it. If the symptom rhymes with one,
  start there — `CS-001` exists because a hand-written double and an `Any` at a seam hid a crash
  on the app's only way off its first screen, and both conditions are still true elsewhere.

## 2. Never hotfix — investigate the mechanism, prioritize redesigning it to scale

Root-causing a bug means investigating the *mechanism* behind it, not stopping at the one
call site the report happened to surface. Every fix must weigh scalability before a line of
code is written: **prioritize fixing the mechanism, redesign it if that's what it takes** —
a hotfix is the fallback only once a redesign is genuinely not warranted, never the default.

- A fix that patches only the one call site the report surfaced, while the same defect
  stays free to recur at every other call site of the same shape, is a hotfix — forbidden
  even when it makes the reported symptom disappear.
- Before writing the fix, ask: does this class of problem already exist at more than one
  place, or will it recur as the app grows (a second screen, a third caller, a new symbol)?
  If yes, the fix must redesign the shared mechanism, not duplicate a patch per call site.
- Concrete tell: if the natural fix is "add the same timer/toggle/wiring to every Presenter
  that has this problem," stop — that is N copies of one concern, the exact duplication
  class this repo has already paid for and extracted away more than once (`OrderFeed`,
  `EquityFeed`, `HealthCheckCoordinator`, `LiveOrderBookCoordinator` all exist because two
  Presenters once carried byte-identical logic). Move the mechanism to the one layer that
  serves every current and future consumer for free — typically one application-layer
  service publishing through the existing event pipeline, not a UI-layer object constructed
  once per screen.
- Worked example (`BUG-117`): the Positions table's mark price/PnL only ever refreshed on an
  `ACCOUNT_UPDATE` event, so it went stale between fills while the live chart kept ticking.
  The first pass added a `QTimer`-based controller to *each* Presenter (Trading, Dev Board)
  — it did fix the reported symptom, but as two independent timers polling the same
  endpoint, with a third future screen needing a third copy. Corrected to one
  `PositionRefreshService`, started once at boot, gated on `TradingSessionState.enabled`,
  republishing through the same `PositionChangedEvent`/`PositionClosedEvent` every screen
  already listens to — one poll, zero added Presenter wiring, any number of screens.
- This rule does not license scope creep the report never asked for. A redesign stays
  bounded to the mechanism the bug actually lives in — replace the duplicated/patched piece
  with the shared one, do not also refactor unrelated code nearby.

## 3. Prove the reproduction and the fix with log evidence

- When static reading isn't conclusive, add **temporary** debug logging at *each* layer the
  failure could plausibly cross — input, business logic, render/adapter boundary — not just
  the one you suspect. Multiple layers let the log show where behaviour actually diverges
  instead of you guessing. `BUG-009`'s three concurrent layers
  (`[chart-env]`/`[chart-data]`/`[cached-frame]`) is the worked example.
- Reproduce with that logging in place and capture the output as the real evidence for
  step 1's root cause — not a paraphrase of what you expect it to say.
- After the fix, reproduce again and check the *same* log for **positive proof the new
  mechanism actually ran** (e.g. "dropped 2 stale indicator lines after rebuild"), not
  merely the absence of the old symptom — absence is weak evidence: the bug could be gone
  for an unrelated reason (another code path, a timing accident) while the fix never fired.
- **Decide explicitly whether to keep or discard each piece of temporary logging — neither
  reflexively delete nor reflexively keep all of it:**
  - **Keep and promote to permanent** logging that describes general system behavior useful
    for diagnosing *future*, not-yet-known bugs in the same area (`[chart-env]`'s
    render-backend/DPR dump outlived the bug it was written for). A kept log MUST get a
    proper permanent home per [`logging-rule.md`](./logging-rule.md) — correct `"App.*"`
    namespace, correct level (`INFO` one-shot, `DEBUG` high-frequency) — never a raw
    `print()` or an ad hoc logger that emits nothing (that was `BUG-009`'s second root
    cause: a logger outside the `"App"` tree has no handler and drops everything at `INFO`).
  - **Discard** logging that only proves one hypothesis about this one bug (a printed
    `x`, `y` pair) and has no diagnostic value once it is closed.
  - **Weigh placement before keeping anything in a hot path** (per-frame render loop, tight
    pixel/geometry computation). A line that's fine once per gesture is noise or overhead at
    60 Hz — prefer coarser granularity (per-gesture, per-action) at `DEBUG`; if per-frame
    detail is genuinely needed use `TRACE` ([`logging-rule.md`](./logging-rule.md) §6-7),
    which only emits under `--debug`, so it never has to be discarded for being expensive.

## 4. Write a regression test first, and confirm it actually fails

- Before fixing the code, write a test reproducing the reported failure, then **run it and
  confirm it fails for the right reason** — not just that it exists. A test that passes
  before the fix proves nothing and must not be trusted as a reproduction.
- **Pick the correct test tier for where the crash actually lives.** If the failure is
  inside a method a mock/test-double stands in for, that attempt cannot reproduce it — a
  `Mock` never executes the real method body. `BUG-013` (2026-08-19) was first "reproduced"
  with `Mock(spec=NativeBacktestChartHost)`, which passed twice with **no fix applied at
  all** before the mistake was caught and the test rewritten at the Sanity tier against a
  real native host. See [`ci-rule.md`](./ci-rule.md) §6 for the four-level test contract
  this maps onto.
- Only after the test is confirmed red, apply the fix, then confirm the same test goes
  green — alongside step 3's log evidence, not the test in isolation.

## 5. Keep the regression test permanently

The regression test is the executable record of the reported failure. It MUST NOT be
deleted, skipped, weakened, or rewritten into something that no longer reaches the original
failure path, unless explicitly replaced by stronger coverage of that exact same path.

## 6. Commit content

- The fixing commit MUST include step 4's regression test — never fix without it, never
  commit the test as a separate later commit.
- State the root cause clearly in the commit body: what caused the bug, and why the fix
  resolves it cleanly.
- `fix:` commit type per [`commit-rule.md`](./commit-rule.md), referencing the root cause
  or issue ID (`BOT-xxx`/`BUG-xxx`).

## 6.5 Write a case study when the gate was green

A bug report says what broke. When the defect reached the user **through a passing gate**, and
some existing check — a type checker, a test, a guard, a review row — covered that area and
missed it, the reason it missed is worth more than the fix: it is a blind spot, and blind spots
are never local. Add `Docs/CASE_STUDIES/CS-NNN_slug.md` in the fixing commit, one screen, with
the three sections its [index](../../Docs/CASE_STUDIES/README.md) requires — *why nothing caught
it* (net · why silent · still open?), *the fix*, *where else this is still open* — and list it in
that index. `tests/unit/architecture/test_case_study_index_is_consistent.py` fails on an unlisted
file, a dead citation, a missing section or a file over 60 lines.

Not every bug earns one: if nothing was watching that line and nothing pretended to be, the bug
report is the whole record. The test is whether the same blind spot is open somewhere else right
now — and the case study must install the check that closes it, in the same commit.

## 7. Document it as a bug report

Every bug worth this workflow gets `Tasks/bug_report/incomplete/BUG-XXX_description.md`
(next number after the highest across *both* subdirectories), structured as from `BUG-006`
onward:

- **Header:** Reported date, Severity, Status (`Open`, or `✅ Fixed <date>` with how —
  root-caused / reproduced / regression-tested / verified).
- **Symptom:** what was observed, with real evidence (traceback, log, screenshot).
- **Root cause:** the actual mechanism from step 1, with file/line references.
- **Fix:** what changed and why it's sufficient.
- **Regression test:** which file, and confirmation it failed before / passes after.

Filing before the fix is fine: leave `Status: Open` with a `Suggested next steps` section
instead of a fix — do not guess at an unverified root cause just to fill the section in.

Once the fix lands, `git mv` the report (and any screenshots it embeds) from `incomplete/`
to `Tasks/bug_report/completed/`, update its `Status` line, and move its row in
[`Tasks/bug_report/README.md`](../../Tasks/bug_report/README.md) — the Bug Board — from the
open table to the fixed one. The board is the only place an *open* bug is visible;
`ROADMAP.md` only ever lists fixed ones.
