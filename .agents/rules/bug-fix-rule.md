---
name: Bug Fix Rule
description: Mandatory workflow for diagnosing and fixing a reported bug — root cause first, log evidence for both the reproduction and the fix, regression test before the fix, correct test level, permanent test, documented report.
trigger: always_on
---

# BUG FIX WORKFLOW

This file owns the **whole** bug-fix workflow. Don't let fragments of it live
in other rule files — two partial copies will drift apart.

---

## 1. Diagnose the root cause first — never guess

- **Read the real failure evidence** (traceback, log, screenshot) and the
  **real source it points at** before writing a line of fix code. A "plausible
  hypothesis" is **not** a root cause — trace the exact call chain the error
  came from.
- **State the root cause explicitly before fixing:** what causes the bug, and
  why the planned fix resolves it cleanly without crossing architectural layer
  boundaries.
- **Fix the mechanism, not the symptom.** When the same error recurs in several
  places, fixing only the reported one is **unacceptable**. And **a fix you
  cannot explain — why the symptom disappeared — is not a fix.**

---

## 2. Prove the reproduction AND the fix with log evidence

- When static reading isn't conclusive, add **temporary** logging at **every
  layer the failure could plausibly cross** — input, business logic, the
  adapter/render boundary — not just the one you already suspect. Instrumenting
  several layers lets **the log itself show where actual behaviour diverges from
  expected**, instead of you guessing which layer is at fault.
- **Reproduce with that logging in place** and keep the output as the real
  evidence for the root cause in step 1 — not a paraphrase of what you *expect*
  it to say.
- **After the fix, reproduce again and read the SAME log for POSITIVE proof that
  the new mechanism actually ran** — e.g. "dropped 2 stale indicator lines after
  rebuild" — not merely the **absence** of the old symptom. Absence is weak
  evidence: the bug may be gone for an unrelated reason (a different code path,
  a timing accident) while the fix mechanism **never fired**.

### Decide explicitly whether to keep or discard each temporary log

Don't reflexively delete all of it, and don't reflexively keep all of it.

- **KEEP and promote to permanent** the lines describing **general system
  behaviour**, useful for diagnosing **future, not-yet-known** bugs in the same
  area. A kept log MUST be moved to a proper home per
  [`logging-rule.md`](logging-rule.md) — correct logger namespace, correct level
  — **never** left as a raw `print()` or an ad-hoc logger that emits nothing.
  *(That was itself the **second root cause** of a real bug: a logger outside
  the app's namespace tree has no handler and silently drops everything below
  WARNING.)*
- **DISCARD** logging that only proves **one** hypothesis about **one** specific
  bug (a printed `x, y` pair confirming a guess) and has no diagnostic value
  once the bug is closed.
- **Weigh placement before keeping anything in a hot path** (a per-frame render
  loop, a tight computation). A line that's fine once per gesture can be real
  noise or real overhead at 60 times a second — coarsen the granularity (per
  gesture, per action) and lower the level. If per-frame detail is genuinely
  needed, log it at the most verbose level (emitted only under a debug flag) so
  it never has to be discarded merely for being expensive.

---

## 3. Write the regression test FIRST, and confirm it actually fails

- **Before fixing the code**, write a test reproducing the reported failure
  condition, then **run it and confirm it fails FOR THE RIGHT REASON** — not
  merely that it exists. A test that passes **before** the fix proves nothing
  and must not be trusted as a reproduction.
- **Pick the correct test level for where the failure actually lives.** If the
  crash is inside a method your mock/test double stands in for, that attempt
  **cannot** reproduce it — a mock **never runs the real body**.

  > **Real evidence:** a bug was "reproduced" with `Mock(spec=<real host>)` and
  > **passed twice in a row with no fix applied at all**, before the mistake was
  > caught and the test rewritten at a higher level against the real object.

- Only **after** the test is red for the right reason, apply the fix, then
  confirm that same test goes green — **and** confirm the log evidence from
  step 2 alongside it, not the test in isolation.

---

## 4. Keep the regression test permanently

The regression test is the **executable record** of the reported failure. It
MUST NOT be deleted, skipped, weakened, or rewritten into something that no
longer reaches the original failure path — unless replaced by **stronger**
coverage of **that exact path**.

---

## 5. Commit contents

- The bug-fix commit **MUST contain** the regression test from step 3 — never
  fix without it, never commit the test separately afterwards.
- **State the root cause clearly in the commit body.**
- Use the `fix:` type per [`commit-rule.md`](commit-rule.md), referencing the
  root cause or bug ID.

---

## 6. File a bug report

Every bug worth this workflow gets a report file (next ID after the highest
existing one, counting **both** the open and the closed directories):

- **Header:** reported date, severity, status (`Open`, or `✅ Fixed <date>` with
  how: root-caused / reproduced / regression-tested / verified).
- **Symptom:** what was observed, **with real evidence** (traceback, log,
  screenshot) — not a paraphrase.
- **Root cause:** the actual mechanism, with `file:line` references.
- **Fix:** what changed and why it is sufficient.
- **Regression test:** which file, and confirmation it failed before / passes
  after.

If the report is filed **before** the fix (bug found but not yet worked), leave
`Status: Open` with a **"Suggested next steps"** section — **do not guess at a
root cause you have not verified just to fill the section in.**

Once the fix lands: `git mv` the report (and any screenshots it embeds) into the
closed directory, update its `Status` line, and **move its row in the bug board**
from the open table to the fixed one. The bug board is the **only** place an
**open** bug is visible.
