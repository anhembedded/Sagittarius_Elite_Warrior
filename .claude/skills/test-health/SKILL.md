---
name: test-health
description: Audit whether this repository's tests are still trustworthy — empty and vacuous tests, silent skips, tiers excluded from CI, allowlists with no completeness guard, duplicated fixtures, tests guarding deleted code, and rule clauses nobody enforces. Use on a schedule (every 3 days), before a release, after a large refactor, or whenever CI is green but bugs still reach users.
---

# Test Health Audit

## What this answers

**Are the tests themselves still worth believing?**

Not "do they pass". Passing is `scripts/ci-local.ps1 -Full`'s job, and it needs
Windows, PySide6 and the engine installed. This audit runs anywhere, needs no
dependencies, and asks the question a green CI run cannot answer about itself:
*is anything here still capable of failing?*

The distinction matters because this repository has already been burned by it.
`BUG-039` closed with the note: *"1800 passed / 54 sanity — nothing broke, i.e.
**no test had ever asserted** that the default was correct."* `BUG-038` was
found by a human looking at the screen while *"1789 unit + 54 sanity"* ran
clean. Test count and coverage percentage stopped carrying signal here a while
ago; this audit is the replacement instrument.

## Run it

```bash
python3 .claude/skills/test-health/scan.py            # human summary
python3 .claude/skills/test-health/scan.py --json     # machine-readable
```

Stdlib only, no install step. Run from anywhere — it resolves the repo root
from its own location.

## The one rule that keeps this useful: report the delta, not the state

An audit that prints the same 45 findings every three days is ignored by the
third cycle. So:

1. Run `--json` and diff it against `Tasks/reports/test_health/baseline.json`.
2. **Report only what changed for the worse** since the baseline: a new
   finding, a tier that shrank, a clause that stopped being enforced, a
   directory newly excluded from CI, a bug that landed in a class the suite
   was supposed to cover.
3. **If nothing got worse, say exactly that in one line and stop.** Do not
   restage the known backlog. Do not re-explain findings the last report
   already explained.
4. Update the baseline **only** for items that were deliberately accepted or
   fixed — never to silence something merely because it is still there. A
   finding that stays open stays in the delta.

Known-open items live in
[`Tasks/reports/sanity_tier_audit_and_remediation.md`](../../../Tasks/reports/sanity_tier_audit_and_remediation.md).
Read it before writing a report so the audit does not re-file work already
filed.

## Reading each check

The scanner reports facts. Deciding what a fact means is your job — these are
the calls that need judgement rather than a threshold.

| Check | What it means | Legitimate exception |
| :--- | :--- | :--- |
| **C0** | A test file does not parse. | None. Always a defect. |
| **C1** | Test contains no assertion at all. | A deliberate *"does not raise"* test — the name usually says `no_op`, `without_raising`, `does_not_crash`. Weak but honest. Judge by whether the name claims more than exception-freedom. |
| **C2** | Every assertion in the test is unfalsifiable. | Rare. `assert x is not None` right after `x = SomeClass(...)` cannot fail; the scanner already excludes lookups like `container.resolve()`, which genuinely can return `None`. |
| **C3** | Docstring promises silence ("cleanly", "zero errors") the body never checks. | The promise may be delivered by a fixture (e.g. an autouse diagnostic guard). Verify before reporting. |
| **C4** | A fixture calls `pytest.skip`. | Almost never legitimate in `tests/sanity`: a tier that proves composition health must go **red** on a broken environment, not vanish. Defensible in an optional tier gated on a real external dependency. |
| **C6** | A hand-written constant drives `parametrize` with no completeness guard in the same file. | None that survives scrutiny. An allowlist catches deletions and is blind to an addition nobody registered — which is the failure that actually happens. The correct pattern already exists in `tests/sanity/test_view_model_thread_affinity_sanity.py`: pin the list, then prove the list complete against a live scan. |
| **C7** | The same fixture name is defined in several files of one tier. | Two genuinely different fixtures that happen to share a name. Check the bodies — if they are near-copies, they have already drifted or will. |
| **Excluded from CI** | A directory the project's own CI entry point refuses to run. | Never leave unreported. Report the test count being skipped as a number: that is the size of the blind spot. |
| **Rule contract** | A mandatory clause of `ci-rule.md` / `code-rule.md` with zero enforcement in the tier it governs. | A clause that has just been retired — in which case fix the rule and `contract.json` in the same change, so the audit stops checking a rule nobody has. |
| **Orphaned assets** | Files under `src/` that no `src/*.py` loads any more. | Assets loaded by path built at runtime. Verify. Ones still referenced *by tests* are the real signal: a guard outliving what it guards is worse than no guard — it reports green about something production stopped using, and costs CI time to say nothing. |

## Keeping `contract.json` honest

`contract.json` is the machine-readable half of `.agents/rules/ci-rule.md` §6
and `code-rule.md` §4. When either rule changes, change this file in the same
commit. If they drift, the audit starts grading the suite against a rule the
project no longer holds — which is precisely the failure the first audit found
(`code-rule.md` mandated `quick_widget.errors() == []` for a year after the UI
stopped using QML at all).

## Output

Write `Tasks/reports/test_health/YYYY-MM-DD.md`, kept short:

```markdown
# Test Health — YYYY-MM-DD

**Verdict:** <one sentence — better / unchanged / worse, and why>

## Changed since <previous date>
- ...            # only regressions and fixes; omit the section if empty

## Action
- ...            # only what someone should do now; "none" is a valid answer
```

If nothing got worse, the whole file is the verdict line. That is a successful
audit, not a lazy one.

## When to escalate beyond the report

Raise these to the user directly rather than burying them in a file:

- A **tier newly excluded** from default CI, or an excluded tier that grew.
- A **rule clause that stopped being enforced** — the suite silently stopped
  keeping a promise the project still makes in writing.
- A **new bug in `Tasks/bug_report/incomplete/`** whose defect class the suite
  is supposed to cover. That is an escape, and escapes are the only metric
  here that measures the real thing.
- Sanity **growing with feature count**. `tests/sanity` is designed to be a
  fixed set of scans; if it grows every time a screen is added, the tier has
  reverted to per-feature allowlists and will rot again.

## What this audit must not do

- **Do not run the app's test suite** and report the result as test health.
  It cannot run here, and a pass would not answer this question anyway.
- **Do not fix findings on your own initiative.** Report; let the user decide
  scope. The exception is a finding you created in this same session.
- **Do not propose raising the coverage threshold.** 93% coverage coexisted
  with 43 filed bugs in this repository. Coverage is not the instrument.
