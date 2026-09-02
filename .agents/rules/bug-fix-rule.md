---
name: Bug Fix Rule
description: Mandatory workflow for diagnosing and fixing a reported bug — root cause first, log evidence for both reproduction and fix, regression test before the fix, correct test tier, permanent test, documented report.
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

## 2. Prove the reproduction and the fix with log evidence

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

## 3. Write a regression test first, and confirm it actually fails

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
  green — alongside step 2's log evidence, not the test in isolation.

## 4. Keep the regression test permanently

The regression test is the executable record of the reported failure. It MUST NOT be
deleted, skipped, weakened, or rewritten into something that no longer reaches the original
failure path, unless explicitly replaced by stronger coverage of that exact same path.

## 5. Commit content

- The fixing commit MUST include step 3's regression test — never fix without it, never
  commit the test as a separate later commit.
- State the root cause clearly in the commit body: what caused the bug, and why the fix
  resolves it cleanly.
- `fix:` commit type per [`commit-rule.md`](./commit-rule.md), referencing the root cause
  or issue ID (`BOT-xxx`/`BUG-xxx`).

## 6. Document it as a bug report

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
