---
name: process-drift
description: Audit whether the written process still matches what the repository does — rule contradictions, stale claims, quotations the cited file never contained, mechanisms the tree no longer has, board orphans, reference rot. Runs on a schedule (every 3 days) and leaves one dated file under Tasks/reports/process_drift/ whether or not it found anything.
---

You are the **process-drift audit** for Sagittarius Elite Warrior. `.claude/ONBOARDING.md` §13 holds the rules every unattended run obeys; read it first. Your run answers one question — **has the written process stopped matching what the repository does?** — and leaves one dated file whether or not it found anything.

## 1. What you check, and with what
Run the mechanical half first; every command's output is evidence, never a paraphrase.

```bash
python3 scripts/measure_process.py                      # rule lines, always-loaded lines, guard count, allowlist size, task counts
python3 scripts/check_skill_prompt_references.py        # cited paths that no longer exist
python3 scripts/render_task_counts.py                   # the count table ROADMAP.md must carry
python3 scripts/render_claude_manifest.py               # the inventory .claude/README.md must carry
PYTHONPATH=.. python3 -m pytest tests/unit/test_task_board_is_consistent.py tests/unit/test_rule_navigation_is_complete.py tests/unit/architecture/test_claude_tree_is_wired.py tests/unit/architecture/test_case_study_index_is_consistent.py tests/unit/architecture/test_spec_index_is_consistent.py -q
```

Then the half only a reader can do. Read `CLAUDE.md`, `.claude/ONBOARDING.md`, `.claude/README.md` and every file `ls -R .claude/rules/` prints, whole, and list:
- **a rule that contradicts another rule or a guard** (a cadence, a number, an authority stated twice differently — compare each stated threshold with the guard that holds it);
- **a quotation attributed to a file that the file does not contain** (grep the quoted words);
- **a claim of current state that a command disproves** ("the repo always has…", "N tests", "X is scheduled") — run the command;
- **a document that describes a mechanism the tree no longer has** (a deleted directory, a retired flag, a renamed script);
- **a rule clause tagged `[eye]` that a guard in `tests/unit/` now enforces**, or a guard whose `Retire when:` condition has arrived;
- **a pitfall under `.claude/rules/pitfalls/` whose bug or case study no longer exists**, or a case study whose one-line form is in no pitfall file.

## 2. What you write
`Tasks/reports/process_drift/<YYYY-MM-DD>.md`, English, one screen:

```markdown
# Process drift — <date>
**Verdict:** <unchanged since <previous date> | N findings>
**Measured:** <the numbers `measure_process.py` printed, as a table with the previous run's values beside them>
## Findings          (omit when none)
- <file:line> — <what disagrees with what> — <what breaks if left>
## Environment       (only when a command above could not run; say which and why)
```

Commit it on `master-warrior` (documentation-only, `ONBOARDING.md` §7) and push. Do not fix findings; do not open a pull request for them. If the previous report already lists a finding, say "still open since <date>" rather than restating it.

## 3. Stop conditions
Stop and write the Environment section instead of guessing when: the checkout is not on `master-warrior`, a script above is missing, or the tests cannot be collected. An empty run is a correct outcome.
