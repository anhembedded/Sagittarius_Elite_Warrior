---
name: Onboarding
description: Entry point for any AI agent working on Sagittarius Elite Warrior — repo layout, task/bug workflow, real verification commands, bookkeeping, and the traps that repeatedly produce broken code.
trigger: always_on
---

# ONBOARDING — Read this BEFORE writing your first line of code

A map of the process, not a copy of the rules: it tells you *when* to read *which* rule, and describes the parts that are written down nowhere else (working across 2 repos, the real verification commands on Linux, `ROADMAP.md` bookkeeping).

**Every number in the documentation (rule file counts, test counts, lint error counts, task status) DRIFTS.** Always recount with a real command instead of trusting a number someone wrote down.

---

## 1. Documentation map — read in this order

| Order | File | When |
| :--- | :--- | :--- |
| 1 | `.agents/ONBOARDING.md` (this file) | Always, first |
| 2 | `.agents/AGENTS.md` | Navigation only — points to the right rule file per topic |
| 3 | `.agents/rules/code-quality-rule.md` | Any Python change in `src/`, `scripts/` |
| 4 | `.agents/rules/architecture-rule.md` | Port/ABC, layers, CQRS, splitting files by abstraction level |
| 5 | `.agents/rules/ci-rule.md` | Before declaring anything "done" — 4 test tiers + the gate command |
| 6 | `.agents/rules/commit-rule.md` | Before every commit |
| 7 | `.agents/rules/bug-fix-rule.md` | **Mandatory** when the user reports a bug |
| 8 | `.agents/rules/logging-rule.md` | When adding/changing logs, and in every bug fix |
| 9 | `.agents/rules/testing-rule.md` | When writing tests (the commands to run them are in `ci-rule.md`) |
| 10 | `.agents/rules/async-ui-action-rule.md` | Presenters, background tasks, cancellation, Coordinator |
| 11 | `.agents/rules/domain-truth-rule.md` | When touching `src/domain/`, `src/application/` |
| 12 | `.agents/rules/ui-presentation-rule.md` | When touching `src/presentation/` (Python) |
| 13 | `.agents/rules/qml-rule.md` | When touching `.qml` files |
| — | `Docs/VOCABULARY/README.md` | **Look up any term** (architecture, UI places, per-context domain words); the only place a term is defined — add a new term there in the same commit that coins it |
| — | `Tasks/ROADMAP.md` | Where the system stands, which tasks exist |
| — | `Tasks/bug_report/README.md` | Bug Board — which bugs are open |
| — | `Tasks/epics/README.md` | Epic list (each Epic has its own directory + README, §3) |
| — | **§12 of this file** | **Picking up work in progress** — and §12.2 for where live state actually lives |

Count the real number of rule files with `ls .agents/rules/` — **do not load them all**, each file has its own `trigger`. `install-rule.md` covers installation specifically; read it when a task actually touches that scope. `code-rule.md` is **only a navigation stub** (the real content was split into the files above); the stub is kept because `.agents/Skills/` still points at it (`grep -rl code-rule .agents/Skills/`). Security rules live in `.agents/Skills/sentinel.prompt.md` + `Tasks/epics/EPIC-004_static_security_and_quality_analysis/`, **not** in `rules/`.

---

## 2. TWO independent repos, not a submodule

```
Sagittarius_Engine/                  ← framework repo (sagittarius_engine/), its own remote
└── Sagittarius_Elite_Warrior/       ← Binance bot app repo, branch `master-warrior`, its own remote
```

As of commit `a1efcd6` (2026-08-21) the submodule declaration was removed entirely. The two directories are just 2 **completely independent Git repos** that happen to be nested on disk — **there is no pointer to keep in sync**.

- Work in `Sagittarius_Elite_Warrior/` (nearly every business task): go into that directory, `git commit`/`git push` — a single repo.
- Work in `sagittarius_engine/` (rare — only when a foundational mechanism is genuinely missing): commit/push separately in `Sagittarius_Engine`, unrelated to the app.

Older docs/habits mentioning "bump the submodule pointer" describe a process that is **no longer in effect**; confirm with `git ls-files -s Sagittarius_Elite_Warrior` from the superproject (empty = already detached, bump nothing).

**Never `git push` unless the user explicitly asks.** Commit is ask-by-default (§7); push is forbidden-by-default.

---

## 3. The lifecycle of a TASK (new feature)

1. **Task file** in `Tasks/backlog/` following the `BOT-XXX_short_description.md` template (the next number after the largest existing one). **Take that number from the files on disk, not from `ROADMAP.md`** — a board lags, and two sessions reading the same lagging board pick the same number. This has happened four times (`BUG-051`/`BUG-052`, `BUG-058` twice, `BOT-120`, `BOT-126`); `tests/unit/test_task_board_is_consistent.py` now fails the gate on a collision or a dangling board link, so a clash surfaces at merge instead of months later. If the user asks for a feature with no task → create the task file first, then code. Large epics get sub-tasks `BOT-XXXA`, `BOT-XXXB`… and the epic must have a table listing its sub-tasks.
2. **Task file content** is written in English (§10), and must at minimum contain: real context & problem (not generic), design + the **reason** for any non-obvious decision, per-file changes, testing.
3. **Code + tests.** See §5 for which test tier is the right one.
4. **On completion:** `git mv Tasks/backlog/BOT-XXX_*.md Tasks/completed/`, change the status to `✅ Hoàn thành (YYYY-MM-DD)`, and add an "Implementation Notes" section recording the **real bugs found while doing the work**, design decisions, and test counts. This is the task file's greatest value to a later reader — don't write it just to tick a box.
5. **`ROADMAP.md` bookkeeping:** see §6.

An epic does **not** move to `completed/` until *all* of its sub-tasks are done; until then update its status in place (`1/3 done`).

---

## 4. The lifecycle of a BUG

`.agents/rules/bug-fix-rule.md` is the source of truth — read it verbatim. The three most frequently violated points:

- **Write the regression test BEFORE the fix, and run it to confirm it FAILS for the right reason.** A test written after the fix, or failing for another reason (wrong import, missing fixture), proves nothing.
- **Pick the right test tier.** If the crash site lives inside a method that a test double replaces, that test *cannot* reproduce the bug — a `Mock` does not run the real function body. `BUG-013` was "reproduced" wrongly this way twice in a row with `Mock(spec=...)`, passing even before anything was fixed.
- **A bug report is mandatory:** `Tasks/bug_report/incomplete/BUG-XXX_mô_tả.md` (once fixed, `git mv` it to `completed/`), containing Symptom (real evidence: traceback/log/screenshot, not a paraphrase), Root cause (the real mechanism with file:line), Fix, Regression test. When done, **add a row to the [Bug Board](../Tasks/bug_report/README.md)** — the only place open bugs are visible; `ROADMAP.md` only shows fixed bugs.

When the user pastes logs/screenshots into the chat, **read them with real tools** (Read the image, open the log file) before proposing a hypothesis. In `BUG-018`, the "Database Size" tile being correct while the "Stored Records" tile was wrong immediately localised the fault to the function summing table rows, not to the disk-reading layer.

---

## 5. Running REAL verification

`ci-rule.md` mandates `scripts/ci-local.ps1 -Full` as the required gate. `pwsh` **is available** on this Linux machine (`which pwsh`), and the script really runs:

```bash
pwsh -NoProfile -Command "./scripts/ci-local.ps1 -Full"
# run from the Sagittarius_Elite_Warrior/ directory (this is $botRoot, unlike every
# bash command below, which runs from the superproject)
```

Prefer `pwsh` when you need the real CI gate (it wires up `mypy`, coverage, and sequential sanity correctly). The bash commands below are for deliberate quick checks — run them **from the superproject directory**:

```bash
# Unit (~3 minutes; count the real number of tests with this very command, don't trust a written number)
PYTHONPATH=. QT_QPA_PLATFORM=offscreen \
  Sagittarius_Elite_Warrior/.venv/bin/python -m pytest Sagittarius_Elite_Warrior/tests/unit/ -q

# Sanity (~35 seconds)
PYTHONPATH=. QT_QPA_PLATFORM=offscreen \
  Sagittarius_Elite_Warrior/.venv/bin/python -m pytest Sagittarius_Elite_Warrior/tests/sanity/ -q

# Lint (read-only, never let CI --fix on its own). This one command already covers EPIC-004's
# security/quality rules (S/PLR2004/B/SIM/ERA/N, ci-rule.md §1) too — they're enabled repo-wide via
# pyproject.toml's [tool.ruff.lint] extend-select, not a second tool/invocation.
Sagittarius_Elite_Warrior/.venv/bin/python -m ruff check  <file...>
Sagittarius_Elite_Warrior/.venv/bin/python -m ruff format --check <file...>

# Mypy (EPIC-002, the real gate — src AND scripts MUST be in the same command, see why
# in ci-rule.md §1 and Tasks/reports/EPIC-002A_mypy_baseline_audit.md §3)
PYTHONPATH=. \
  Sagittarius_Elite_Warrior/.venv/bin/mypy --config-file Sagittarius_Elite_Warrior/pyproject.toml \
  --namespace-packages --explicit-package-bases \
  Sagittarius_Elite_Warrior/src Sagittarius_Elite_Warrior/scripts
```

**Reading the output is a trap — this matters.** In `offscreen` mode QML dumps a flood of `TypeError: Cannot read property '...' of null` to stderr; they are harmless and appear *after* pytest's summary line, so `tail` shows you that noise instead. Always write to a file and grep it:

```bash
... -q > /tmp/run.log 2>&1; grep -E "^[0-9]+ (passed|failed)|failed," /tmp/run.log | tail -3
```

**This applies to EVERY verification command, including `ci-local.ps1 -Full`** — and the reason is worse than "noise": `| tail -N` can **completely lose** the real error line. Evidence (`BUG-029`/`BUG-030`): a previous agent only ran raw `pytest`; when it finally ran `ci-local.ps1 -Full` and redirected everything to a file (`> file 2>&1`, not pipe/tail), two real bugs surfaced at once — (1) `Join-Path` only works on PowerShell 7+, breaking the CI gate on PowerShell 5.1 which the script itself claims to support; (2) `-n 6` (parallel) killed one worker after a `ResourceWarning: unclosed database`, reproducing 2/2 times, not flaky. Both only surfaced because there was a complete log file to re-read. Always `> logfile 2>&1`, never `| tail`.

**On lint:** the repo always carries a few `I001` errors (unsorted imports) from other sessions that you did not cause — check for real with `ruff check src tests`. Only fix lint in the **files you are already changing for the current task**; don't go tidying unrelated files (nobody can review a bug-fix diff mixed with unrelated changes). If you want to clean the whole repo, do it in a separate `style:` commit, after asking the user.

---

## 6. `Tasks/ROADMAP.md` bookkeeping — the most commonly botched part

Every completed task/bug must update **all three** places:

1. **Add one line at the TOP of the `🟢 Completed` section** (newest-first). That line must summarise the root cause / design decision, not just restate the task name.
2. **Recompute the count table with a real command, don't count by hand:**
   ```bash
   for d in completed in_progress backlog cancelled; do
     printf "%s %s\n" "$d" "$(ls Tasks/$d/*.md 2>/dev/null | wc -l)"
   done
   ```
   Then update all 4 lines + the total + the percentage. (Bug reports in `Tasks/bug_report/` do **not** count toward these numbers.)
3. **Update the epic's line in place** in its group table, and note "Cập nhật <date>" at the top of the file.

After adding a new task file with cross-links, **check that no link is broken**:

```bash
cd Tasks/backlog && grep -oh "](\.\./\?[^)]*\.md)" BOT-XXX*.md | tr -d '](' | sed 's/)$//' \
  | sort -u | while read -r l; do [ -f "$l" ] || echo "BROKEN: $l"; done
```

**A large epic (many sub-tasks, many status updates) gets its own `Tasks/epics/EPIC-XXX_slug/`, not one line in `ROADMAP.md`** (details in `Tasks/epics/README.md`). Structure: `README.md` (overview + sub-task table) + `incomplete/`/`completed/` (sub-task codes `EPIC-XXXA`, `EPIC-XXXB`…). `ROADMAP.md` then **keeps only a single link line** to the epic's `README.md` — no copied content. When a sub-task is finished, update all 3 places: the epic's `README.md`, `Tasks/epics/README.md` (recount X/N), and the one-link line in `ROADMAP.md`. (Old-style epics, flat in `Tasks/backlog/`/`completed/` — `BOT-109`, `BOT-112`, `BOT-115` — keep the old format.)

Architecture proposals that are not yet tasks (nobody has approved them) live in `Tasks/proposal/PRO-XXX.md` — distinct from `Tasks/backlog/` (already accepted) and from `Tasks/epics/` (already broken into concrete sub-tasks). Once approved, turn them into real `BOT-XXX`/`EPIC-XXX`; `PRO-XXX.md` is not executable on its own.

---

## 7. Authority — what you may do alone, what you must ask about

| Action | Rule |
| :--- | :--- |
| Read, analyse, run tests | Free |
| Change code within the scope the user asked for | Free |
| `git commit` | **Ask first.** Never commit spontaneously |
| `git push` | **Only when the user explicitly asks**, and each repo (app / engine) is its own separate confirmation — 2 independent repos per §2, no longer coupled |
| `git commit` / `push` / merge of a **documentation-only** change (`Docs/`, `Tasks/`, `.agents/`, `CLAUDE.md`) | **Free** — standing authorisation by the user, 2026-09-13 (*"update doc thì cứ merge as will"*). Any file outside those paths makes it a code change and the two rows above apply |
| `git commit` of **`EPIC-025` code**, locally, after the gate is green | **Free** for the duration of that epic (user, 2026-09-13); `push` and merge of code still wait for the user's OK per pull request |
| Change files outside the task's scope | No, unless the user asks |
| Delete/overwrite the user's files | Read the content first, ask first |

### Deciding for yourself is the default — don't ask the user about every small choice

> **Decision doctrine (settled by the user 2026-08-30; extended 2026-09-02
> beyond architecture).** This doctrine used to live only in
> `rules/architecture-rule.md`, and **no navigation file pointed to it** —
> it existed but might as well not have. It is a rule about **autonomy**, so it belongs in this section.

Applies to **every** technical decision, not just architecture:

- **When several directions are all reasonable and there is no "absolutely right" answer → decide by proven best
  practice / design pattern / architecture pattern.**
- **Apply before you invent — survey first, every time (user decision 2026-09-13, in these
  words: *"hãy refer xem các giải pháp có sẵn trên thế giới làm gì, tui ưu tiên áp dụng, ứng dụng
  hơn sáng tạo"* — "look at what the existing solutions in the world do; I prefer applying and
  adopting over inventing").** The moment you start considering a solution to a problem — an
  architecture, a mechanism, a guard, a widget, a workflow — the **first** step is a survey: which
  named pattern, which large community-vetted project, which library already solves this, and how.
  Prefer **applying** that solution over creating one. When a ready-made solution is *not* adopted
  (a dependency policy, a licence, a version constraint), still **apply its shape** — copy the
  vetted design, not just the idea. Inventing is the last resort, and the document that proposes
  the invention must say which existing options were surveyed and why each was rejected. Worked
  examples: `Docs/HLD/07_build_vs_buy.md` (the survey for `EPIC-025`, with two tools run on the real
  tree before deciding) and `Docs/HLD/04_surfaces_and_contribution_points.md` §4.6 (the UI
  placement rule taken from the VS Code / Spyder / napari workbench model rather than designed from
  scratch).
- **Don't be afraid to redesign** an existing part if the current design is a *hard design*
  (rigid, patched together, hard to extend). **"It currently works" is not a reason to leave it
  alone.**
- **The agent decides and carries on** — don't stop to ask the user about every small
  choice.

**Only ask when the situation falls into exactly one of these three groups:**

1. A **genuinely large or irreversible** trade-off (changing the foundational architecture, changing a
   public contract, migrating data).
2. The action is in the **"must ask" table above** — `commit`, `push`, delete,
   overwrite, changes outside the task's scope. This doctrine does **not** loosen that group.
3. Missing information **only the user has** (business intent, priority order).

The doctrine decides **which direction is right**, it does **not** change **how the work is done**: still
task + ADR before code (§3, §12.2), still through the same CI gate (`ci-rule.md`) and
commit gate (`commit-rule.md`) as before.

### Pushing back is mandatory, not optional

- The AI assistant MUST actively challenge/refute user requests if they introduce inconsistencies, anti-patterns, layer violations, or break established domain principles.
- Never blindly follow contradictory instructions; explain the root issue and propose a clean, consistent alternative.

That is: if the user's request creates an architectural contradiction, violates a layer boundary, or breaks a settled principle → say so and propose a clean alternative, don't silently comply. But if the user has heard you out and still stands by the request, carry it out in full.

---

## 8. Eleven traps that made other agents produce broken code

All of them really happened in this repo; none are hypothetical.

1. **Computing a test's expected value in your head instead of running the real code.** In `BOT-106A`, a return series that is mathematically constant still made `statistics.stdev()` yield ~1e-16 rather than `0.0`, blowing Sharpe up to ~3.2×10¹⁵. Run the real code, then fix the expected number.
2. **Comparing floats with `== 0` or `if value:`.** Use `math.isclose(x, 0.0, abs_tol=1e-9)`. See trap 1 for the consequences.
3. **Asserting counts against hard-coded constants** (`len(cards) == 9`). A later task adds one card and the test breaks even though nothing is wrong. Assert on *what is meaningful* (present/absent, relative order), not on a count.
4. **Asserting full-dict equality** on `to_dict()` output. Another session adds a legitimate field and the test breaks. Assert on the subset of fields the test actually cares about.
5. **Adding a field to a frozen dataclass without a default.** `Trade`, `BacktestMetrics`, `BacktestRunConfig` have hundreds of call sites constructing them directly in tests. A new field must **always** have a default value.
6. **Changing a shared formula without a branch that preserves the old behaviour.** `BOT-114` added leverage to `PaperExchange`: the "spot"-style LONG PnL formula is completely wrong when `margin != notional`. The right approach is to keep the old branch **byte-for-byte** for `leverage == 1.0` and only use the new formula when leverage is actually in play — the proof being that 47 old tests passed without a single line changed.
7. **Calling `fsm.transition_to(X)` while already in `X`.** The FSM matrix has no self-edges, so it raises; `@safe_ui_action` swallows the error so the app doesn't die, but the slot **dies mid-way** and every line after it never runs. That is exactly `BUG-018`. A background worker that never locked the UI must **not** emit an unlock signal.
8. **Forgetting that `@safe_ui_action` swallows exceptions.** A slot can die silently halfway through. Don't put important work (refreshing data) *after* a call that can throw.
9. **Adding `logger.info()` inside a hot loop.** Logging is **not** free: `SignalLogHandler` is attached to the **root** `"App"` logger at INFO level (`data_management_presenter.py`), so **every** `App.*` record from **every** subsystem is pushed through a queued cross-thread signal to the UI thread, and each line then runs a full `beginInsertRows`/`endInsertRows`/`countChanged` cycle in `LogListModel`. `BUG-042`: `PaperExchange` logged at INFO on every fill → 838 trades produced **5,028 lines in 2 seconds** → the UI froze solid, freezing linearly with trade count. Which screen the log belongs to does **not** matter — the handler catches at the root logger. Inside a loop that runs many times (per trade, per candle, per tick) use `logger.debug()`, or batch/throttle before logging — see `ProgressThrottle` (`BUG-033`) as the model for the correct signal path.
10. **Editing a `.qml` file while forgetting that the logic belongs in Python.** QML is declarations and bindings only; state machines, validation and computation all belong to the Presenter/ViewModel. And a `.qml` file over 300 lines should be split into components.
11. **Adding a new `@abstractmethod` to a Port and updating only the "main" implementer.** `ruff` cannot catch this — checking whether a class implements the full interface is the type checker's job. `BUG-026`: a probe script implementing `IExchangeClient` was forgotten when the interface gained a method, and crashed at construction (`TypeError: Can't instantiate abstract class`). When you change a Port, grep for implementers in **`src/`, `scripts/`, AND `tests/`** — missing `scripts/` is exactly what went wrong while fixing `BUG-025`, leaving an identical live defect behind. `mypy` (gating `src`+`scripts` in one command, §5) is the second safety net — but don't rely on tooling alone; still grep when changing an interface.

---

## 9. Two `.agents/` sets — don't read the wrong repo

`Sagittarius_Engine` (framework) and `Sagittarius_Elite_Warrior` (the bot app, this directory) each have their own `.agents/`, and are **2 independent Git repos** (§2) that merely happen to be nested on disk. This is the most dangerous confusion for a new agent.

| | `../.agents/` (`Sagittarius_Engine`) | `.agents/` (`Sagittarius_Elite_Warrior` — this directory) |
| :--- | :--- | :--- |
| Serves | the `sagittarius_engine/` framework | the bot app |
| Task board | `../Tasks/README.md` (Kanban, code `TASK-XXX`) | `Tasks/ROADMAP.md` (codes `BOT-XXX`/`BUG-XXX`/`EPIC-XXX`) |
| Entry point | `PLAYBOOK.md` + `manifest.yml` | `ONBOARDING.md` (this file) + `AGENTS.md` |
| Git remote | its own, repo `Sagittarius_Engine` | its own, repo `Sagittarius_Elite_Warrior` |

When working in the app, **always give this repo's rules priority**. `Sagittarius_Engine`'s rules apply only when you are genuinely changing framework code — and then it is a completely separate commit/push (§2). The two task boards have nothing to do with each other — don't record app tasks in the engine's `Tasks/README.md`, or vice versa.

Per-session narrative summaries are not kept anywhere any more (§12.2) — the current state is what §12.1's commands print.

Note: **every rule file in both repos only lists PowerShell commands**. On Linux, use the commands in §5.

---

## 10. Language

- **`.agents/` rule documentation and this onboarding:** English.
- **Code, identifiers, docstrings, comments, commit subjects:** English.
- **Conversation with the user:** Vietnamese, or whatever language the user writes in.
- **Every `.md` document — task files, bug reports, ROADMAP, epics, ADRs, proposals, `Docs/`:** English.
  **User decision 2026-09-12** (*"từ nay tài liệu .md không viết tiếng Việt nữa"*), replacing the
  earlier Vietnamese rule. Documents written before that date stay as they are; any new section
  added to one of them is English.
- **Register for documents — "like a self-study technical book"** (the user's words). Concretely:
  - Teach, don't just record. State *why* before *what*; a reader who was not in the conversation
    must be able to follow the reasoning and check it.
  - Define a term the first time it is used, then use it consistently (Bounded Context, Port,
    Surface, Contribution point). Never introduce a name without saying what it is — and the
    definition lives in **one** place, `Docs/VOCABULARY/README.md`; a document links there rather
    than redefining (user decision 2026-09-13: *"the vocabulary nên đưa vào 1 dir doc, để tra cứu
    khi dev"* — "put the vocabulary in one doc directory, to look up while developing").
  - Prefer one worked example with real file paths and numbers over three adjectives. Evidence
    is `file:line` and a measured count, not "many" or "a lot".
  - Full sentences and short paragraphs; tables for comparisons and inventories, prose for
    reasoning. A table cell is not the place for an argument.
  - No chat-style shorthand, no emoji in prose (status icons in board tables are fine), no
    untranslated Vietnamese except a quoted user decision, which is given verbatim and then
    translated.
- **User-visible UI strings and log messages:** English, using the agreed domain terminology (for example "Strategy Parameters" is distinct from the general Bot Settings).

---

## 11. Reporting to the user — project-lead level, not implementation level

- When reporting progress, task/epic status, an investigation summary, or test results to the user in conversation, write as if reporting to a **project lead**: conclusion, current state, decisions the user needs to make, risks/blockers. Do **not** go into implementation detail (function names, lines of code, internal data types, C++ symbol names…) unless the user asks directly, or that detail **directly determines** the next action. Example: "F4 is blocked by BUG-015 (Windows: geometry rebuilt on pointer move), root-cause hypothesis under investigation" is enough; there is no need to list `QSizeF` or `.cpp` file names.
- **This does not apply to long-lived documents** — task files, bug reports (`Tasks/bug_report/`), and reports (`Tasks/reports/`) must still carry full root cause/file:line/evidence per `bug-fix-rule.md` and §4/§5. The "project-lead level" rule applies only to answers in conversation.
- **A question to the user carries its own context (user decision 2026-09-13, in these words: *"hỏi gì thì hãy cho tôi context"* — "whatever you ask, give me the context").** The user has not read the documents you have; a question that names an ADR label, a file or a term they never met (*"decide O4; approve SDD-01b"*) cannot be answered. Every question states, in plain language and in this order: what happens in the code today; why it has become a decision now; each option by the **consequence the user will feel**, not by its mechanism; your recommendation and why; and what "yes" commits them to. One screen, no reading required. The worked example is the position-sizing decision (ADR D17): the first ask was three labels and was rejected; the second explained the size formula, who calls it, and what changes when the user later wants a different formula, and was answered in one line.

---

## 12. Picking up work in progress — read this section before typing the first line

### 12.1 The same first three commands, every time

```bash
git -C . status
git -C ../Sagittarius_Engine status
cat Tasks/epics/README.md
```

**Work on this project is often left uncommitted between sessions** — per §7, agents don't commit on their own. So `git status` is not a formality: a task board that looks untouched **plus** a dirty working tree means the work is **already done**, just not recorded. Read the diff before concluding a task is untouched. Trust the output of those 3 commands, not any paragraph describing the state.

### 12.2 Where things stand → the boards and git, never a hand-written summary

**This section deliberately does NOT list which epic is running or which task is next.** Two
attempts at holding that here, and a third in a separate `Handover.md`, all went stale — the
Handover was frozen at `2026-08-25` and still opened with *"Next up: `EPIC-007A`"* long after
`EPIC-007` closed 8/8, `EPIC-021` closed 13/13 and `EPIC-022` closed 6/6. It was deleted on
2026-09-07 rather than rewritten again (user's decision), because the problem was never the
writing: **a hand-maintained copy of state that already exists elsewhere drifts, always.**

State now has exactly four sources, none of which can drift because each one *is* the thing it
describes:

| Question | Source |
| :--- | :--- |
| Which epic is running, how far along | [`Tasks/epics/README.md`](../Tasks/epics/README.md) — status column |
| Which bugs are open | [`Tasks/bug_report/README.md`](../Tasks/bug_report/README.md) — the Bug Board |
| What just happened, and why | `git log` (commit bodies here carry the reasoning) |
| What is half-done right now | `git status` + the diff, in **both** repos (§12.1) |

Those are the same commands §12.1 already tells you to run. That is the point: §12.1 was always
the real handover, and the file merely repeated it less accurately.

Invariants that do belong here:

- **Mandatory: read the epic's `README.md` + its `DECISION_*.md` (ADR) files before doing any sub-task.** ADRs record decisions already argued out with the user — including several that **reverse** an earlier approach. Re-deriving them costs a session and usually reaches a different answer. If an epic has `design/*.puml`, look at the diagrams before touching code.
- **The sub-task table in each epic has a `Repo` column.** A task marked `Engine` must be committed in the Engine repo (§2, §9). The table is ordered by increasing risk and states which item blocks which — don't skip ahead.
- **The status written in a task file can be older than the code.** Before believing "this task hasn't been done", check against the code itself (`find`, `grep`, run the tests) — tasks have turned out to be already finished by another epic, and others have had **nothing left** to do. A count in a README drifts the same way: `EPIC-021`'s own README said 10/13 while its `completed/` directory held 13.

### 12.3 The next sub-task and its ordering

When you finish a sub-task: `git mv incomplete/EPIC-XXXY_*.md completed/`, write a "Xong <date>" section at the end of that file (root cause, decisions, verification evidence), update the corresponding row in the epic's `README.md` table and the "x/y sub-tasks done" count at the top of the file. Follow the `Tasks/epics/README.md` convention.

### 12.4 New mechanisms in the Engine — use them, don't rewrite them

`EPIC-008` already built the following mechanisms in the Engine repo. Writing something else instead recreates exactly the bugs they just closed. Full details in `Sagittarius_Engine/.agents/context/events.md`:

| What you need | What to use |
| :--- | :--- |
| Define an event | inherit `BaseEvent` — you get `event_id`/`occurred_on`/`event_name` + automatic catalog registration |
| Presenter subscribing to an event | `self.subscribe(...)`, **not** `self.event_bus.on(...)` — it hops back to the main thread and detaches on dispose |
| Cleanup when shutting a presenter down | override `shutdown()`, **never** override `dispose()` |
| Reporting a handler failure | `report_handler_failure` |
| A logger when none is injected | `resolve_bus_logger` — **not** `NullLogger` |

### 12.5 Six principles the user has settled, applying to every task

1. **Fix the mechanism, not a hot fix.** Fixing only the one place that was reported, when the same fault recurs in several places, is unacceptable. A fix you cannot explain — *why* the symptom disappeared — does not count as a fix (`bug-fix-rule.md`).

   **Extended 2026-09-08 (user's decision, in these words: *"luôn chọn general solution"*).**
   When a fix can be made either **locally** (this screen, this call site) or as a **general
   mechanism** (the shared component every caller goes through), **take the general one** —
   and do not present the local one as the recommended option. This settles a class of
   question that had been asked repeatedly and answered inconsistently.

   Worked example, the one that produced this rule (`BOT-128`): two tables on the Trading
   screen lost 4 of 7 columns because their declared widths needed ~840px and the layout gave
   each ~390px. Local fix: stack those two tables vertically — one line, zero risk, fixes what
   was reported. General fix: give the shared `DataTable.qml` a horizontal scroll, so **all six**
   tables in the app stop losing columns at any window width. The agent recommended the local
   one because it was cheaper; the user overruled it, and was right — the local fix leaves the
   same defect armed in five other places.

   The counterweight is **scope**, not cost: a general mechanism must still be the general form
   of *the reported problem*, not a speculative *implementation* of problems nobody has (§7's "the
   4 stub cards guessed the wrong shape"). That counterweight never forbids a **seam** — see
   principle 6 below and `architecture-rule.md` §7.2.1 for the distinction. Cost alone is never the reason to prefer local — say
   that a general fix is larger and then do it anyway.
2. **More files is better — one abstraction per file, and different abstractions don't even share a directory.** Splitting is the default; **merging is what needs a reason**. Two hard constraints: (a) two things at **different abstraction levels** must not share a file (Port vs implementation, base class vs subclass); (b) files at **different abstraction levels** must not share a `dir` — a directory is a layer, not a bucket (`interfaces/` holds no implementations, a shared `widgets/` holds no widget specific to one screen). The only counterweight is Single-Scope Cohesion in `code-quality-rule.md`, and it **only** wins when the definitions describe **the same lifecycle** (an FSM's enum + its matrix) — "same feature"/"same screen" does **not** count. Thresholds that force a split: **>400 lines/file** or **>15 public methods/class**. Quick arbitration: *does changing A force you to change B?* Yes → same file; no → split. Full text in [`rules/architecture-rule.md`](rules/architecture-rule.md) §5 "Abstraction-Level Separation".
3. **Present the design before implementing** for any restructuring work: PlantUML class + component, as-is and to-be, stating clearly what is shared and what is per-screen — get it approved before writing the task file and the code.
4. **No commit, no push unless the user asks** (§7).
5. **Apply before you invent** (user decision 2026-09-13; full text in §7). Before designing
   anything, survey what already exists — named patterns, large projects, libraries — and prefer
   applying it. Not adopting a library is a legitimate outcome (the user kept `EPIC-025`'s
   hand-written guards after seeing `tach` run), but the survey happens first and is written down,
   and a rejected library's *shape* is still the reference for what we build.
6. **Design for extension always; build the extension only when needed** (user decision
   2026-09-13, in these words: *"khi dev luôn luôn phải cân nhắc các trường hợp có thể mở rộng, có
   thể chuyển các design sao cho dễ mở rộng"* — "when developing, always consider the cases that
   could be extended, and shape the design so it is easy to extend"). At every design decision,
   write down the plausible extension cases, and make sure each one is a **local** change behind
   a seam that exists now; do not build the cases themselves. The seam is Open/Closed; the
   unbuilt variant is YAGNI; they are not in conflict. Full procedure and the "closed design" tell:
   `architecture-rule.md` §7.2.1.

### 12.6 Traps when running the gate in the Engine repo

`scripts/ci-local.ps1` on the Engine side can report red for tests **unrelated** to your change: `BUG-006` (two "no QML runtime warnings" tests depend on collection order — even adding a new test file can change the result) and `tests/test_agents_docs_resolve.py` (`grep` not found on `PATH` when run through PowerShell).

**Before concluding you caused the failure, A/B it:** `git stash push -u` → run → `git stash pop` → run. It costs two minutes, and it is the difference between a real regression and an hour chasing the environment.
