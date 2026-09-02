---
name: Onboarding
description: Entry point for any AI agent working on this repository — document map, task/bug lifecycle, real verification commands, bookkeeping, permissions, and the traps that have actually produced broken code.
trigger: always_on
---

# ONBOARDING — read this BEFORE writing the first line of code

This `.agents/` set has several rule files — **don't load them all**. Each has
its own `trigger`; read the one the work in front of you needs.

A new agent's problem is not a shortage of rules. It is **not knowing those
files exist, in what order to read them, and how the process actually runs**.
This file is that map. It does not repeat rule content; it says *when* to read
*which* rule, and describes the parts of the process written down nowhere else.

---

## 1. Document map — read in this order

| Order | File | When |
| :--- | :--- | :--- |
| 1 | `.agents/ONBOARDING.md` (this file) | Always, first |
| 2 | `.agents/Handover.md` | **Immediately after this one** — where the last session stopped, which decisions not to re-derive |
| 3 | `.agents/AGENTS.md` | Navigation only — topic → rule file |

Then open **exactly one or two** files under `rules/`, matching the work — not
the whole set:

| Doing what | Read |
| :--- | :--- |
| Changing any code | `code-quality-rule.md` |
| Anything architectural: interfaces, layers, splitting files | `architecture-rule.md` |
| Unsure between an internal signal and the event bus | `event-rule.md` |
| Deferring work, or accepting a trade-off | `design-intent-rule.md` |
| About to say "done" | `ci-rule.md` |
| About to commit | `commit-rule.md` |
| A bug was reported (**mandatory**) | `bug-fix-rule.md` |
| Adding or changing logs | `logging-rule.md` |
| Writing tests | `testing-rule.md` |
| User-initiated background work | `async-action-rule.md` |
| Business logic | `domain-truth-rule.md` |
| Presentation layer | `ui-rule.md` |
| Missing tooling to verify | `environment-rule.md` |
| Where the system currently stands | `<TASKS_DIR>` |

**Don't trust any number written in documentation** (rule-file counts, test
counts, lint-error counts). They drift faster than anything else. In the
repository this rule set came from, the sentence "there are N rule files" was
**wrong three times in a row** (10 → 9 → 8, actually 7). Count with a command:
`ls .agents/rules/`.

---

## 2. Lifecycle of a TASK (new feature)

1. **Task file first, code second.** Every task has a file under `<TASKS_DIR>`
   named `<TASK_ID>-XXX_short_description.md` (next number after the highest
   existing one). If the user asks for a feature with no task → write the task
   file first. Large work splits into sub-tasks `<TASK_ID>-XXXA`, `-XXXB`… and
   must carry a sub-task table with an **execution order** (sorted by
   increasing risk, stating explicitly what blocks what).
2. **Task file contents**, at minimum: the **real** context and problem (not a
   generic description), the design plus the **reasoning** behind every
   non-obvious decision, per-file changes, and how it will be verified.
3. **Refactoring work: present the design before implementing.** Class and
   component diagrams, as-is and to-be, stating what is shared and what is
   local. Approved first, coded second.
4. **Code + tests.** Which test level is the right one: `rules/ci-rule.md` §4.
5. **Completion:** move the task file into `completed/` (`git mv`, never
   copy-then-delete — that loses history), change its status to
   `✅ Done (YYYY-MM-DD)`, and add an **"Implementation notes"** section: real
   bugs found while doing it, design decisions, test counts. That section is
   the task file's greatest value to whoever reads it later — don't write it
   for the sake of writing it.
6. **Bookkeeping:** §4.

A large task does **not** move to `completed/` until *every* sub-task is done;
until then update its status in place (`1/3 done`).

**The status written in a task file can be older than the code.** Before
believing "this task hasn't been done", check the code itself (`grep`, run the
tests). A task already completed by other work — or one that has **run out of
subject matter** — happens more often than you'd think.

---

## 3. Lifecycle of a BUG

`rules/bug-fix-rule.md` is the source of truth — read it verbatim. The three
most-violated points:

- **Write the regression test BEFORE the fix, and run it to confirm it FAILS
  for the right reason.** A test written after the fix proves nothing. A test
  failing for an unrelated reason (bad import, missing fixture) proves nothing
  either.
- **Pick the right test level.** If the crash lives inside a method your test
  double replaces, that test *cannot* reproduce the bug — a mock never runs the
  real body. A real bug was once "reproduced" with `Mock(spec=...)` and passed
  twice in a row with no fix applied at all.
- **A bug report is mandatory**, containing: Symptom (real evidence —
  traceback/log/screenshot, not a paraphrase), Root cause (the actual mechanism
  with `file:line`), Fix, Regression test. Once filed, add a row to the open-bug
  table — that is the only place an unfixed bug is visible.

If the user pastes a log or a screenshot into chat, **open it with a real
tool** before forming a hypothesis. One detail in an image often points
straight at the cause: a correct figure sitting next to a wrong one immediately
localised a defect to the aggregation function rather than the data-loading
layer.

---

## 4. Bookkeeping — the part most often done sloppily

Every completed task/bug must update **all three** places:

1. **Add a line at the top of the "done" section** (newest first). That line
   must summarise the root cause / design decision, not merely restate the
   task's name.
2. **Recompute the count table with a command, never by hand:**
   ```bash
   for d in completed in_progress backlog cancelled; do
     printf "%s %s\n" "$d" "$(ls <TASKS_DIR>/$d/*.md 2>/dev/null | wc -l)"
   done
   ```
3. **Update the status line in place** in the overview table, with the date.

After adding a file with cross-links, **check for broken links**:

```bash
grep -oh "](\.\{1,2\}/[^)]*\.md)" <file>.md | tr -d '](' | sed 's/)$//' \
  | sort -u | while read -r l; do [ -f "$l" ] || echo "BROKEN: $l"; done
```

---

## 5. Running the REAL verification

The full gate command and how to handle red: `rules/ci-rule.md`. Here are only
the two things agents get wrong **before they get around to reading it**:

### 5.1 Don't trust the console — write to a file, then grep

```bash
<CI_CMD> > /tmp/ci.log 2>&1
grep -nE "FAILED|ERROR|Traceback|WARNING" /tmp/ci.log
```

**Always `> logfile 2>&1`, never `| tail`.** Two reasons; the second is the
heavier one:

- Many frameworks (GUI stacks in headless mode especially) dump **harmless**
  errors to stderr *after* the test runner's summary line, so `tail` shows you
  that noise and you conclude the tests broke.
- Worse: `| tail -N`, or a truncating terminal, can **lose the actual failing
  line entirely**. Real evidence: an agent ran bare tests for several sessions
  and never ran the full gate; the first time it did **and redirected
  everything to a file**, two real bugs surfaced at once — a script error that
  only occurred on an older shell version, and a worker dying mid-run after
  `ResourceWarning: unclosed database`, reproducing 2 out of 2 times rather
  than being flaky. Both surfaced only because there was a complete log file to
  read back.

This applies to **every** verification command, the gate itself included. This
section is about **you** typing a command by hand; the requirement that the
**gate script itself** capture and scan its log is a separate rule —
`rules/ci-rule.md` §5.

### 5.2 Only fix lint in the files you are already changing

A repository always carries a few lint errors from other sessions that you did
not cause. Cleaning up unrelated files makes a bug-fix diff carry unrelated
changes and nobody can review it. To clean the whole repo, make a separate
`style:` commit — after asking the user.

---

## 6. Permissions — what to do freely, what to ask about

| Action | Rule |
| :--- | :--- |
| Read, analyse, run tests | Free |
| Change code within the scope the user asked for | Free |
| Design decisions inside that scope | Free — see `architecture-rule.md`, decision doctrine |
| Install an **already-declared** tool/library into this environment | Free — `environment-rule.md` |
| Add a **new** dependency to a manifest | **Ask first** |
| `git commit` | **Ask first.** Never commit spontaneously |
| `git push` | **Only when the user explicitly asks**; each repository is its own confirmation |
| Change files outside the task's scope | No, unless the user asks |
| Delete or overwrite the user's files | Read the contents first, then ask |

### Pushback is mandatory, not optional

- The agent **must** challenge a user request that introduces a contradiction,
  violates a layer boundary, or breaks an established principle. State the
  underlying problem and propose a clean alternative — do not silently comply.
- But if the user has heard it and still wants the request as stated, **do it
  fully as asked** — don't do it half-heartedly to prove a point.

---

## 7. Nine traps that have actually produced broken code

All of these really happened; none is hypothetical. **Each has exactly one
owner** under `rules/` — the full description and its evidence live there and
are not copied here. This table exists so you recognise which trap you are
standing in front of.

| # | Trap | Rule that owns it |
| :-: | :--- | :--- |
| 1 | Computing a test's expected value in your head instead of running the real code | `testing-rule.md` §4 |
| 2 | Comparing floats with `==` / `if value:` | `testing-rule.md` §6 |
| 3 | Asserting counts against a hard-coded constant (`len(x) == 9`) | `testing-rule.md` §6 |
| 4 | Asserting full-object equality on serialised output | `testing-rule.md` §6 |
| 5 | Adding a field to a shared type without a default value | `code-quality-rule.md` §7 |
| 6 | Changing a shared formula without branching to preserve old behaviour | `code-quality-rule.md` §7 |
| 7 | Transitioning an FSM into the state it is already in; and putting important work after a call that can throw inside an exception-swallowing handler | `async-action-rule.md` §3 |
| 8 | Adding logging inside a hot loop | `logging-rule.md` §4 |
| 9 | Adding a method to an interface and updating only the "main" implementer | `architecture-rule.md` §2 |

Two have no owner under `rules/` because they are **working habits**, not rules
about code — so they live here:

- **Read evidence with a real tool.** When the user pastes a log or an image,
  open and read it before forming a hypothesis (§3).
- **A/B before blaming yourself** when the gate goes red somewhere you never
  touched (§10.4).

---

## 8. Language

- **Conversation with the user, task files, bug reports, documentation:**
  `<DOC_LANG>`.
- **Code, identifiers, docstrings, comments, commit subjects:** English.
- **User-visible UI strings:** `<UI_LANG>` — using the domain terminology
  already agreed on.

---

## 9. Reporting to the user — project-lead level, not implementation level

- When reporting progress, status, an investigation summary, or test results
  **in conversation**, write as if reporting to a **project lead**:
  conclusion, current status, decisions the user needs to make, risks and
  blockers. **Do not** descend into implementation detail (function names, line
  numbers, variable names) unless the user asks directly, or that detail
  **directly determines** the next action.
- **This does not apply to durable documents.** Task files, bug reports and
  written reports still need the full root cause / `file:line` / evidence. This
  rule governs conversational answers only.

---

## 10. Picking up work in progress

### 10.1 The first three commands, every time

```bash
git status
git log --oneline -10
cat .agents/Handover.md
```

**Work is routinely left uncommitted between sessions** — per §6, the agent
does not commit on its own. So `git status` is not a formality: a task board
that looks untouched **plus** a dirty working tree means the work **is already
done**, just unrecorded. Read the diff before concluding a task is untouched.

### 10.2 State lives in `Handover.md`, not here

This file deliberately does **not** list what is currently in flight. Its
previous version (in the original repository) had that table and the table was
wrong within hours. State lives in exactly one place:
[`Handover.md`](Handover.md), which is **replaced** every session.

### 10.3 Read the decisions before you start

**Mandatory: read the decision record (ADR / `DECISION_*.md`) for the work in
hand before touching any sub-task.** It captures decisions already argued
through with the user — including ones that **reverse** an earlier approach.
Re-deriving them costs a session and usually lands somewhere different.

### 10.4 Before concluding a failure is yours, A/B it

The CI gate can go red on tests **unrelated** to your change (collection-order
dependence, a tool missing from `PATH`, the environment).

```bash
git stash push -u   # run the gate → record the result
git stash pop       # run it again → compare
```

Two minutes, and it is the difference between a real regression and an hour
chasing the environment.

---

## 11. Checklist before saying "done"

Not a summary of the rules — a **verification order**. Each line points at
where it is defined; if a line looks doubtful, open that file rather than
guessing.

- [ ] Full gate `<CI_CMD>` exits `0` — **lint + format + type check + tests +
      coverage**, not tests alone (`ci-rule.md` §1)
- [ ] The run was **captured to a log file and scanned**; every
      WARNING/ERROR/CRITICAL hit is classified as a real defect or a justified
      expected condition (`ci-rule.md` §5)
- [ ] Test evidence sits at the **right level** — and a piece not yet wired
      into the real app is not claimed as E2E (`ci-rule.md` §4)
- [ ] If it's a bug: the regression test went **red before, green after**, and
      stays permanently (`bug-fix-rule.md` §3-4)
- [ ] If an interface changed: implementers were `grep`ed across **all of**
      `<SRC_DIR>`, `scripts/`, `<TEST_DIR>` (`architecture-rule.md` §2)
- [ ] If something was deferred or traded away: a **type or a test** stands for
      it, not just a paragraph (`design-intent-rule.md`)
- [ ] Bookkeeping updated in **all three** places, counts computed by command
      (§4)
- [ ] No commit/push unless the user asked (§6)
