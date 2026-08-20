---
name: Bug Fix Rule
description: Mandatory workflow for diagnosing and fixing a reported bug — root cause first, log evidence for both reproduction and fix, regression test before the fix, correct test tier, permanent test, documented report.
trigger: always_on
---

# BUG FIX WORKFLOW

This file owns the whole bug-fix workflow. `code-rule.md` and
`commit-rule.md` used to each carry one fragment of it — moved here so
there is a single source of truth instead of two partial copies drifting
apart.

## 1. Diagnose the root cause first — never guess

- Read the actual failure evidence (traceback, log, screenshot) and the
  real source it points at before writing a single line of fix code.
  "Plausible hypothesis" is not "root cause" — trace the exact call chain
  the error came from.
- State the root cause explicitly before touching the fix: what causes the
  bug, and why the planned fix resolves it cleanly without crossing
  architectural layer boundaries.

## 2. Prove the reproduction and the fix with log evidence

- When static reading isn't conclusive, add **temporary** debug logging at
  each layer the failure could plausibly cross — input, business logic,
  render/adapter boundary — not just at the one layer you already suspect.
  Multiple layers let the log itself show exactly where the actual
  behavior diverges from the expected one, instead of you guessing which
  layer is at fault. `BUG-009`'s three concurrent layers
  (`[chart-env]`/`[chart-data]`/`[cached-frame]`) is the worked example.
- Reproduce with that logging in place and capture the output as the real
  evidence for the root cause in step 1 — not a paraphrase of what you
  expect it to say.
- After applying the fix, reproduce again and check the *same* log for
  **positive proof the new mechanism actually ran** — e.g. "dropped 2
  stale indicator lines after rebuild" — not merely the absence of the old
  crash/symptom. Absence-of-symptom is weak evidence: the bug could be
  gone for an unrelated reason (a different code path, a timing accident)
  while the actual fix mechanism never fired.
- **Decide explicitly whether to keep or discard each piece of temporary
  logging — do not reflexively delete all of it, and do not reflexively
  keep all of it either:**
  - **Keep and promote to permanent** logging that describes general
    system behavior useful for diagnosing *future*, not-yet-known bugs in
    the same area (`[chart-env]`'s render-backend/DPR dump is exactly this
    — it outlived the bug it was written for). A kept log MUST be moved to
    a proper, permanent home per `.agents/rules/logging-rule.md` — correct
    `"App.*"` logger namespace, correct level (`INFO` for a one-shot
    meaningful event, `DEBUG` for high-frequency per-event detail) — never
    left as a raw `print()` or an ad hoc logger that emits nothing (this
    was itself `BUG-009`'s second root cause: a logger outside the `"App"`
    tree has no handler and silently drops everything at `INFO`).
  - **Discard** logging that only proves one specific hypothesis about
    this one specific bug (a printed `x`, `y` pair to confirm a guess) and
    has no diagnostic value once the bug is closed.
  - **Weigh placement before keeping anything in a hot path** (a per-frame
    render loop, a tight pixel/geometry computation). A log line that's
    fine once per gesture can be real noise or overhead at 60 times a
    second — prefer a coarser granularity (per-gesture, per-action) at
    `DEBUG`. If per-frame/per-call detail is genuinely needed, log it at
    `TRACE` instead (`.agents/rules/logging-rule.md` §6-7) — it only emits
    under `--debug`, not a normal `--dev` session, so it never has to be
    discarded just because it's expensive.

## 3. Write a regression test first, and confirm it actually fails

- Before fixing the code, write a test that reproduces the reported
  failure condition, then **run it and confirm it fails for the right
  reason** — not just that it exists. A test that passes before the fix
  proves nothing and must not be trusted as a reproduction.
- **Pick the correct test tier for where the crash actually lives.** If the
  failure is inside a method that a mock/test-double stands in for in your
  first attempt, that attempt cannot reproduce it — a `Mock` never executes
  the real method body. This is not hypothetical: `BUG-013` (2026-08-19)
  was first "reproduced" with `Mock(spec=NativeBacktestChartHost)`, which
  silently passed with no fix applied at all, twice, before the mistake was
  caught and the test was rewritten at the Sanity tier against a real
  native host. See `.agents/rules/ci-rule.md` §6 for the four-level test
  contract this decision maps onto.
- Only after the test is confirmed red, apply the fix, then confirm the
  same test goes green — and confirm the log evidence from step 2 alongside
  it, not the test in isolation.

## 4. Keep the regression test permanently

- The regression test is the executable record of the reported failure.
  It MUST NOT be deleted, skipped, weakened, or rewritten into something
  that no longer reaches the original failure path, unless explicitly
  replaced by stronger coverage of that exact same path.

## 5. Commit content

- The commit that fixes a bug MUST include the regression test from step 3
  — never fix without it, never commit the test as a separate later commit.
- State the root cause clearly in the commit body: what caused the bug, and
  why the fix resolves it cleanly.
- `fix:` commit type per `.agents/rules/commit-rule.md` — reference the
  root cause or issue ID (`BOT-xxx`/`BUG-xxx`).

## 6. Document it as a bug report

Every bug worth this workflow gets a file in
`Tasks/bug_report/incomplete/BUG-XXX_description.md` (next number after the
highest existing one across *both* subdirectories), following the structure
established across `BUG-006` onward:

- **Header:** Reported date, Severity, Status (`Open`, or `✅ Fixed <date>`
  with how — root-caused / reproduced / regression-tested / verified).
- **Symptom:** what was observed, with real evidence (traceback, log,
  screenshot) — not a paraphrase.
- **Root cause:** the actual mechanism, from step 1, with file/line
  references.
- **Fix:** what changed and why it's sufficient.
- **Regression test:** which file, and confirmation it failed before / passes
  after.

If the report is filed before the fix (bug found but not yet worked), it's
fine to leave `Status: Open` with a `Suggested next steps` section instead
of a fix — do not guess at a root cause you have not verified just to fill
the section in.

Once the fix lands, `git mv` the report (and any screenshots it embeds) from
`incomplete/` to `Tasks/bug_report/completed/`, update its `Status` line, and
move its row in [`Tasks/bug_report/README.md`](../../Tasks/bug_report/README.md)
— the Bug Board — from the open table to the fixed one. The board is the only
place an *open* bug is visible; `ROADMAP.md` only ever lists fixed ones.
