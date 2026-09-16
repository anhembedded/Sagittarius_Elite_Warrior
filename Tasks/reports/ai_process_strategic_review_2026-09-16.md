# The AI process as a system — a strategic review

**Date:** 2026-09-16 · **Task:** `BOT-134` · **Asked for:** strategy, a systems view, the
philosophy — not a defect list (the user's words: *"tui ko yêu cầu bạn kiểm tra lỗi, tôi muốn tính
chiến lược, góc nhìn hệ thống, triết lý"*). Defects found on the way are evidence for the systems
view and were fixed in the same branch; they are listed in §5 and nowhere else.

**How this was made.** Every process document was read whole (`CLAUDE.md`, `ONBOARDING.md`, the
fourteen rule files, the scheduled-agent briefings, both `.claude/` skills, the three case
studies, the boards); the full git history was unshallowed and measured; the seven Routines, the
last sixty pull requests, the CI runs and the session records were read through their APIs; and a
fresh container was bootstrapped to the point where the local gate runs, so that every claim
about the environment below was tried rather than assumed. Numbers are in Appendix A with the
command that produced each.

---

## 1. The system as it is

The process is a loop, and it is worth drawing once, because most of what follows is about which
arrows exist and which do not.

```text
                     ┌──────────────────────────────────────────────────────────┐
                     │  THE USER — decides, in chat, in Vietnamese               │
                     │  (every decision is written verbatim, dated, into a rule) │
                     └───────────────┬──────────────────────────────▲───────────┘
                                     │ decisions                    │ reports (report-rule)
                                     ▼                              │ questions (ONBOARDING §11)
   ┌──────────────── the constitution ────────────────┐             │
   │ CLAUDE.md (auto-loaded, navigates only)          │             │
   │  → ONBOARDING.md (the map, 520 lines)            │             │
   │  → .agents/rules/*.md (14 files, 1 976 lines)    │             │
   │  → .claude/rules/*.md (6 pointers, load by path) │             │
   └───────────────┬──────────────────────────────────┘             │
                   │ read (by choice, in order, from memory)         │
                   ▼                                                 │
   ┌──────────────── the executive ───────────────────┐   ┌──────────┴───────────┐
   │ ONE long interactive session (opened 09-08,      │──▶│ self-review with the  │
   │ 164 of the last 216 commits) + occasional        │   │ pr-review skill       │
   │ fresh sessions (review, audit, hang audit)       │◀──│ ("the review's own    │
   └───────────────┬──────────────────────────────────┘   │  finding on PR …")    │
                   │ builds                               └──────────────────────┘
                   ▼
   ┌──────────────── the immune system ───────────────┐
   │ scripts/ci-local.ps1 -Full  (ruff, mypy, refs,   │   ┌──────────────────────┐
   │   4 900 tests, 80 % coverage, run-log scan)      │──▶│ PR opened and merged │
   │ 35 guards + 5 ratchets that may only fall        │   │ by the same session, │
   │ a registry of guards, a guard for the registry   │   │ median 6 s later     │
   └───────────────┬──────────────────────────────────┘   └──────────┬───────────┘
                   │                                                 ▼
                   │                                      ┌──────────────────────┐
                   │                                      │ GitHub CI, after the │
                   │                                      │ merge (second gate,  │
                   │                                      │ not the same gate)   │
                   ▼                                      └──────────────────────┘
   ┌──────────────── the memory ──────────────────────┐
   │ bug reports (133) → case studies (3) → a new     │   ┌──────────────────────┐
   │ guard each → a trap in ONBOARDING §8 → a rule    │   │ 7 scheduled agents,  │
   │ boards: ROADMAP, epics README, per-epic README + │   │ every 2 days, output │
   │ TRACKING + Gantt, bug board — copied by hand     │   │ observed: none since │
   │ (17 of the last 100 commits only record)         │   │ 2026-08-27           │
   └──────────────────────────────────────────────────┘   └──────────────────────┘
```

Three things about this picture are the subject of this review. The left column is strong and
unusual: a repository that turns every incident into a machine check, and writes its reasoning
into commit bodies good enough to be the primary record. The right column is where the arrows are
weak: review is the author reading itself, the merge is a formality, and the one component built
for independent eyes (the scheduled agents) has produced nothing observable for twenty days. And
the memory at the bottom is written five times by hand, in a repository whose own onboarding says
that hand-maintained copies of state *"drift, always"*.

---

## 2. The philosophy, stated once

The principles below are not new. Every one of them is already in force here — argued in chat,
dated, quoted verbatim into a rule file. What has never existed is one page that names them and
says what enforces each. That last column is the point of the table: it is the same question the
repository asks of every feature (*what constructs it?*), asked of the process.

| # | Principle | Where it came from | What enforces it today |
| :-- | :--- | :--- | :--- |
| P1 | **Mechanism over memory.** *"Chỗ nào còn phải nhớ thì chỗ đó sẽ hỏng"* — wherever remembering is required, it will break. | `BOT-133`, the user, 2026-09-10 | 35 guards, 5 ratchets, a registry of guards; `bug-fix-rule` §6.5 (a case study ships its check in the same commit) |
| P2 | **Verify, don't restate.** A fact that can change is written as the command that answers it; counts and dates as current state are banned. | `EPIC-011`, `.agents/Skills/README.md` §1 | `check_skill_prompt_references.py` — for *paths* only; a stale claim has no checker |
| P3 | **One source of truth; a copy drifts.** `CLAUDE.md` navigates and copies nothing; `Handover.md` was deleted rather than rewritten. | `CLAUDE.md`; `ONBOARDING` §12.2 | the pointer-size guard, the navigation guard; nothing for a rule restating another rule (four found today) |
| P4 | **The gate is the only evidence, and green describes only what the gate checks.** Redirect to a file, grep the file; never `\| tail`. | `BUG-029`/`030`; `CS-001`'s *take* | `ci-local.ps1`'s run-log scan; review row B; the gate's log path cited in every commit body |
| P5 | **Apply before you invent.** Survey named patterns and vetted projects first; adopt, or copy the shape. | the user, 2026-09-13 | review row A5 — an eye check |
| P6 | **Fix the mechanism; general over local.** Cost is never the reason to prefer the local fix. | the user, 2026-09-08 (`BOT-128`) | `bug-fix-rule` §2; review row E10 — eye checks |
| P7 | **Seam now, variant later.** Open/Closed for the seam, YAGNI for the variant; write the extension cases into the docstring. | the user, 2026-09-13 (`architecture-rule` §7.2.1) | eye; `EPIC-025` ADR D15's "second host is one line" tests, per seam |
| P8 | **Ratchets only fall.** An allowlist or baseline may shrink; raising a ceiling to admit new code is forbidden. | `EPIC-025` D11; `ci-rule` §5.5 | the ratchet tests themselves — fully mechanical |
| P9 | **Decide alone; ask with context.** Three categories of question, and every question carries what the code does today and what "yes" commits the user to. | `ONBOARDING` §7, §11 (2026-08-30, 09-13) | nothing mechanical; `report-rule` shapes the answer |
| P10 | **A number has a unit and a target.** Evidence is `file:line` and a measured count; a report ends on the reader's next action. | `report-rule` §4; `ONBOARDING` §10 | eye; the commit-body convention |

Four of the ten have a machine behind them. Six rest on an agent having read the rule and
remembered it — which is exactly the condition P1 says will fail. **That is the central tension of
this process: it applies "mechanism over memory" to the application with rigour, and to itself
only partly.** The strategy in §4 is mostly about closing that gap without adding to the reading
burden that already exists.

---

## 3. Dynamics — seven process case studies

These follow the form of `Docs/CASE_STUDIES/` (what happened · which net was silent and why ·
still open?) but they are about the *process*, so the "check that now exists" is sometimes a
decision rather than a test. They are numbered PCS to keep them out of the CS sequence, whose
guard requires a test to ship with each entry.

### PCS-1 The super-session monoculture

One interactive session, opened 2026-09-08 and still running at the time of writing, authored
164 of the last 216 commits on `master-warrior` and every pull request from #193 to #220. Of the
twenty pull requests #201–#220, fourteen were merged within thirty seconds of being opened, all by
the session that wrote them; the pull request is a ceremony, and the real gate is the local run
the session reports. Review exists — the `pr-review` skill is thorough — but the commit bodies
say who ran it: *"The review's own finding on PR 2.1c-2"*, *"The review of PR 3.1b, on its own
work"*. The three case studies (`CS-001`, `CS-002`, `CS-003`) were all found *after* merge, by the
same lineage, while measuring something else.

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| `pr-review` skill | written for a reviewer; run by the author, in the author's context | yes |
| the PR itself | nothing requires a second session before merge; the user merges what is proposed | yes |
| independent review sessions | happen ad hoc (PR #211, the `EPIC-025` design review, the hang audit) and found real things each time — but are not policy | yes |

A single line of reasoning, however good, has no adversary. Everything the session knows is also
everything it cannot see. The self-review's own E12 probe ("break the line, run the test") found an
unpinned wiring in four of the last five pull requests — evidence that the process *needs* a second
reading and is currently getting it from the first reader.

### PCS-2 Boards copied by hand, five times per pull request

`ONBOARDING` §6 calls bookkeeping *"the most commonly botched part"* and lists "all three places";
`Tasks/epics/README.md` lists three more for an epic; a pull request of `EPIC-025` is recorded in
`TRACKING.md`, the epic's own `README.md` (status header, §3.4 table and a Gantt), `Tasks/epics/README.md`
and `Tasks/ROADMAP.md`. Seventeen of the last hundred commits exist only to record other commits.
Measured today: eight task files had no row on any board (`BOT-092`, `BOT-119`, `BOT-131`;
`BOT-118`, `BOT-130`, `BOLT-001`, `DOCTOR-001`, `DOCTOR-002`), three epic sub-tasks were not named
in their epic's README, and the `EPIC-025` row on the epics board says of itself that it *"said 36
until 2026-09-16; the file has held 23 entries since PR 1.3c-5"*.

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| `test_task_board_is_consistent.py` | checked dangling links (a row with no file), never the reverse (a file with no row) | closed today — the reverse check is in the same file |
| `ONBOARDING` §12.2 | says hand-copied state always drifts, and deleted `Handover.md` for it — then the boards multiplied anyway | yes, structurally |

The count table, the epic status column and the per-PR log are all *derivable* — from `ls` of the
`completed/` directories and from `git log`. They are copied instead. §4 S4.

### PCS-3 Seven scheduled agents that succeed at nothing

Seven Routines (Bolt, Doctor, Janitor, Palette, Scout, Scribe, Sentinel) have fired every two days
since 2026-08-27. Every `last_run` reads `SUCCEEDED`. In the same period: zero pull requests from
any of them (every PR from #161 to #220 came from an interactive session), zero journal entries
(`bolt.md` is the only journal, last entry 2026-08-26), and the two sampled runs ended in a state
the platform labels "review ready" with nothing to review. Their briefing says an empty run is a
correct outcome — so from the outside, *found nothing*, *could not build the environment*, and
*found something and lost it* are the same signal. Meanwhile the one scheduled audit with a defined
output (`test-health`, "every 3 days") has no Routine at all and ran once, on 2026-09-07.

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| the Routine's status | measures that the wake was delivered, not what the run did | yes |
| `.agents/Skills/README.md` §7 | asks an agent with nothing to find to say so in its journal — none has | yes |
| the boards | the two agent tasks that *were* done (`BOLT-001`, `DOCTOR-001`/`002`) never reached them | closed today |

Order of magnitude: about seventy runs at a few dollars each, for no observable change. §4 S6.

### PCS-4 The immune system that closes the last hole

`CS-001` produced a guard for calls on the engine's ports. `CS-002` produced a guard for bus
subscribers nobody constructs. `CS-003` produced a guard for resolved types nobody binds — and says
of `CS-002`'s guard that it *"was written for this disease and scoped to bus subscribers"*. There
are now 29 guard files under `tests/unit/architecture/`, 6 more at the top of `tests/unit/`, a
registry of what each scans, a guard that the registry is complete, and a guard that every root a
guard computes is really the root. `ci-rule` §5.5 had to add a four-step procedure for the case
where a guard fails *correct* code because a later decision (ADR D20–D22) reversed the doctrine
the guard encodes. Each guard is right. The sum is an organism that grows one antibody per
infection, never retires one, and has no measure of its own weight.

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| the case-study rule ("the check ships in the same commit") | correct, and one-directional: it adds guards, and nothing removes or budgets them | yes |
| the registry | knows what each guard scans, not why it exists or when it may go | yes |

This review deliberately adds **no** new guard file (two existing guards were extended by one
parameter each), because the finding is that the marginal guard now costs more reading than it
saves. §4 S9.

### PCS-5 Rules that quote themselves

Found today, all in the constitution: `commit-rule` §1 required the full gate before *every*
commit while `ci-rule` §1 had moved to once per pull request (user decision 2026-09-16);
`commit-rule` §0 said "never commit unless asked" without the two standing exceptions `ONBOARDING`
§7 grants; `bug-fix-rule` §6.5 said a case study over 60 lines fails the guard, and the guard holds
35; `.agents/Skills/README.md` quoted, in quotation marks, a sentence `ci-rule.md` has never
contained; `ONBOARDING` §5 said the repository *always* carries a few `I001` errors, which licenses
ignoring them, and it is lint-clean at every merge; `install-rule` §1's Option 1 was the exact
command that `ci.yml`'s own comment records as having failed every CI run in the repository's
history; `README.md` said "QML embedded per widget" three days after ADR D20 retired QML.

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| `check_skill_prompt_references.py` | verifies that a cited *path* exists; a cited *claim* or *quotation* has no checker | yes |
| the navigation guard | verifies a rule is *listed*; two rules can be listed and contradict each other | yes |
| the reader | rules are written as norm plus history in one file (`ci-rule` 410 lines, `ONBOARDING` 520), so a correction is one more paragraph and the older paragraphs are never re-read | yes, structurally |

The instances are fixed (§5). The cause is a form: a rule file that is also its own changelog.
§4 S1.

### PCS-6 Two definitions of green

`ci-rule` §7 keeps a table of how the local gate and GitHub CI differ and says the difference is
*"deliberately not reconciled"*. Its row for the static checks said "all 3" on both sides while
GitHub's `ruff` ran on one directory fewer than the local gate for two days (`scripts/` was added
locally on 2026-09-14 after four errors surfaced; the workflow did not follow), and the
real-exchange tier was excluded twice locally and once on GitHub. Nothing compared the two.

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| the table in `ci-rule` §7 | a hand-written comparison of two files, which is P3's failure applied to the gate | the two rows are fixed; the table remains a copy |

One gate — GitHub Actions running `scripts/ci-local.ps1 -Full` — removes the table. §4 S3.

### PCS-7 Nobody owns the root

Three scratch files (`pr_body.txt` with a `Co-Authored-By: Antigravity` trailer, `message_for_reviewer.txt`,
`get_file_content.py`) were committed at the repository root on 2026-08-12 and 2026-08-16 by
automated pull requests and stayed for a month: through roughly 370 commits, twenty reviewed pull
requests, the `AGENTS.md` correction that purged that very trailer from the rules, and one
`test-health` audit. Every check in the repository scans a named tree — `src/`, `tests/`,
`scripts/`, `tools/`, `Docs/`, `Tasks/`, `.agents/`, `.claude/` — and the root itself is in none of
them; `ruff` never saw `get_file_content.py` because the gate lints four directories, not the
package they sit in.

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| `commit-rule` §4 ("never commit temporary files") | prose | yes — an eye check by design |
| `pr-review` L4/L6 | reads what the diff adds; the files predate every review that used the skill | closed for these three; the blind spot is P4's "green describes what the gate checks" |

Deleted today, recorded as trap 14 in `ONBOARDING` §8. Not guarded, on purpose (PCS-4).

---

## 4. Strategy — where to take the process

Ranked by leverage. Each says what changes, why it is the general form of the problem rather than
a patch (P6), what it costs, and what a "yes" commits the user to. Items S1–S4 change the
process's own structure; S5–S6 change who does the work; S7–S10 are policy.

### S1 Make the process obey P1: every rule clause names its enforcer, and history leaves the rule

Split each rule file into a short **norm** — the current clauses, each tagged with what enforces
it (`gate`, `guard:<test file>`, `review:<row>`, or `eye`) — and let the **history** live where it
already lives: git log, bug reports, case studies. The `pr-review` skill already holds this mapping
in the other direction (row → rule); invert it into the rules. Then every `eye` tag is a visible
decision: build the check, or accept that the clause is culture.

- **Why general:** PCS-5's seven contradictions all came from history and norm sharing a file; a
  norm-only file is short enough to be re-read whole at every edit, which is what stops drift.
- **Target:** the text an agent must read before a `src/` change, from 1 567 lines today to under
  ~700; every clause with a named enforcer.
- **Cost:** one documentation epic, two to three sessions, documentation-only commits throughout.
- **Commits the user to:** a period during which rule files move and the running session rebases;
  and to deciding, for each `eye` clause, whether it earns a check.

### S2 Load rules by path, not by memory

`.claude/rules/*.md` pointers are the one mechanism that puts a rule in front of an agent without
the agent choosing to read it. Four rules used it; `testing-rule` and `async-ui-action-rule` now
do too (the three case studies are all test-writing failures, and the rule that names them never
loaded when a test was being written). Extend it to every rule with a file scope
(`logging-rule` has none; `bug-fix-rule` is triggered by a report, not a file).

- **Cost:** done for two; the rest is minutes. **Commits the user to:** nothing.

### S3 One gate

Make GitHub Actions run `scripts/ci-local.ps1 -Full` (Ubuntu runners ship `pwsh`) instead of a
hand-copied sequence of its steps. `ci-rule` §7's comparison table then has nothing to compare.

- **Why general:** PCS-6 is P3 applied to the gate; a copy of the gate drifts like any copy.
- **Cost:** one pull request and one twelve-minute CI run to validate; the worker count already
  derives from the runner's core count.
- **Commits the user to:** CI duration may change; a runner-specific failure becomes a gate-script
  fix rather than a workflow fix.

### S4 Derive the boards; stop copying them

A script renders what is derivable — the count table from `ls`, each epic's status column from its
`completed/` directory, the per-PR log from `git log --grep` — and a guard fails when the committed
board differs from the render. Prose stays hand-written; numbers and rows do not.

- **Why general:** PCS-2's eight orphans, three unnamed sub-tasks and one self-confessed wrong
  count are one disease; the orphan check added today catches the next instance, not the cause.
- **Cost:** one to two sessions. **Commits the user to:** the boards becoming generated
  artefacts in their tabular parts; `ONBOARDING` §6 shrinking to one command.

### S5 Independent review before a code merge

The session that wrote a pull request touching `src/` never merges it. A fresh session runs the
`pr-review` skill against the pull request and posts its findings; the author addresses them; the
user (or the reviewer, if the user delegates) merges. Pure moves and documentation stay as they are.

- **Why general:** PCS-1. The ad hoc independent sessions (PR #211, the `EPIC-025` design review,
  the hang audit) each found something the author had not; the policy makes that the rule.
- **Cost:** one reviewer session per code pull request — tens of dollars and an hour of latency,
  against merges that today take six seconds.
- **Commits the user to:** slower merges, and to deciding whether the reviewer may merge on green.

### S6 Retire the seven personas; keep two audits with durable output

Replace Bolt, Doctor, Janitor, Palette, Scout, Scribe and Sentinel with two scheduled audits whose
every run leaves one line in a log file even when it finds nothing: `test-health` (designed,
never scheduled) and a `process-drift` audit (what this review did by hand — rule contradictions,
board orphans, reference rot, stale claims). The personas' concerns are already in the gate
(`ruff`'s `S` rules are Sentinel; `ERA` is Janitor; `mypy` is Scribe) or in `EPIC-025`'s own
measurements (Doctor). Keep the prompt files as on-demand skills if wanted.

- **Why general:** PCS-3; an agent whose silence is indistinguishable from success is not an
  agent, it is a cost.
- **Cost:** deleting seven Routines and creating two; a run log convention.
- **Commits the user to:** the order-of-magnitude saving in Appendix A, and to reading two short
  delta reports a week.

### S7 Measure the process, not only the app

A script computes, and each epic retrospective reports: rule lines an agent must read, guard
count, allowlist entries, escapes (bugs found after merge, per week), the share of commits that
only record other commits, and cost per merged code pull request. Appendix A is the baseline.

- **Cost:** a script. **Commits the user to:** nothing; it makes S1, S4, S6 and S9 checkable.

### S8 Write down the autonomy policy that is actually practised

The rule says commit ask-by-default and push forbidden-by-default; the practice, for the epic that
is all of the current work, is trunk-based: the session pushes after its gate, opens a pull
request, and merges it in seconds. The exceptions have grown to cover the common case. Choose one
of two honest policies and write it once, in `ONBOARDING` §7, with `CLAUDE.md` item 1 and `ci-rule`
§1's exception pointing at it: (a) trunk plus gate plus S5 for code, documentation free; or (b) a
real pull-request review with a human merge. This review recommends (a), because it is what works
now, with S5 as the missing half.

- **Commits the user to:** one rewrite of §7, and to deciding whether `.claude/` and `README.md`
  are in the documentation-only set (today three files define that set and disagree on those two).

### S9 A guard budget and a retirement rule

Every guard's docstring gains a `Retire when:` sentence (for the QML guards: when Phase 4 deletes
the last `.qml`; for the legacy-tree guards: when the tree is gone), and the registry reports the
count. A guard whose condition has arrived is deleted in the pull request that makes it true.

- **Why general:** PCS-4. **Cost:** a sentence per guard. **Commits the user to:** guards being
  allowed to leave.

### S10 One definition of "documentation-only"

`CLAUDE.md` item 1, `ONBOARDING` §7 and `ci-rule` §1 each define the set of paths a
documentation-only change may touch, and they disagree on `README.md` and say nothing about
`.claude/`, which did not exist when the decision was made. Define it once in §7; the other two
point. This is a user decision (it is an authority boundary), so it is proposed, not done.

---

## 5. Applied — what this branch changed

Everything here is in the branch `claude/cool-gauss-dy2n2z`, verified with the static gate, the
architecture and document guards, and the full gate on the final tree (log path in `BOT-134`'s
task file). Nothing was merged.

| Measure | Before | Now | Target |
| :--- | :-: | :-: | :-: |
| rule files that contradict another rule or a guard (found by reading) | 7 places | 0 | 0, kept by S1 |
| rules that load by path when a matching file is opened | 4 of 14 | 6 of 14 | every rule with a file scope (S2) |
| task files with no row on any board | 8 | 0 | 0, kept by the extended guard |
| epic sub-task files unnamed in their epic README | 3 | 0 | 0 |
| navigation files the rule-listing guard covers | 2 | 3 | 3 |
| `ruff` targets, GitHub CI vs local gate | 3 vs 4 | 4 vs 4 | one gate (S3) |
| real-exchange tier excluded on GitHub | once | twice, as locally | one gate (S3) |
| scratch files at the repository root | 3 | 0 | 0 |
| new guard files added by this review | — | 0 | (PCS-4) |
| `install-rule` Option 1 installs the engine | no | yes | — |

Deliberately **not** changed, because each is the user's decision: the seven Routines (S6); the
autonomy policy and the documentation-only set (S8, S10); the unpinned `ruff` in
`requirements.txt` (the fresh environment installed 0.16.7 and the gate was green; an installed
0.15.8 reported 92 `E402` errors on the same tree — the linter's version decides what green means,
and pinning it is a dependency change, which `install-rule` §3 puts in ask-first).

**What the user must decide next, in order of leverage:** S5 (independent review) and S6
(retire the personas) change outcomes soonest and cost least to reverse; S1 and S4 are the
structural work and want an epic each; S8 and S10 are one conversation.

---

## Appendix A — the baseline, measured 2026-09-16

| Measure | Value | Command |
| :--- | :-: | :--- |
| rule text, all fourteen files | 1 976 lines | `cat .agents/rules/*.md \| wc -l` |
| text an agent reads before a `src/` change (`CLAUDE.md`, `ONBOARDING.md`, six rules) | 1 567 lines | `cat CLAUDE.md .agents/ONBOARDING.md .agents/rules/{code-quality,architecture,ci,commit,testing,logging}-rule.md \| wc -l` |
| all process text (`.agents/`, `CLAUDE.md`, `.claude/`) | 4 263 lines | `cat CLAUDE.md .agents/*.md .agents/rules/*.md .agents/Skills/*.md .claude/rules/*.md .claude/skills/*/SKILL.md \| wc -l` |
| guard files, `tests/unit/architecture/` + top of `tests/unit/` | 29 + 6 | `ls tests/unit/architecture/test_*.py tests/unit/test_*.py \| wc -l` |
| ratchet / baseline files | 5 | `ls tests/unit/architecture \| grep -cE '^(baseline_\|allowlist_)'` |
| boundary allowlist entries | 29 | `grep -c '^[a-z]' tests/unit/architecture/allowlist_module_boundaries.txt` |
| commits since 2026-09-08 / by the one session | 216 / 164 | `git log --since=2026-09-08 --format=%b \| grep -c session_013VgDR1` |
| commits in the last 100 whose only purpose is to record others on the boards | 17 | `git log -100 --format=%s \| grep -c 'record\|boards'` |
| pull requests #201–#220 merged within 30 s of opening | 14 of 20 | GitHub API, `created_at` vs `merged_at` |
| scheduled Routines / pull requests from them since 2026-08-27 / journal entries | 7 / 0 / 0 | `list_triggers`; `list_pull_requests`; `ls .agents/Skills/*.md` |
| sampled scheduled-run cost | US$1–5 per run | session records (`get_session`) |
| the one long session's output | 6.5 M output tokens, ~US$2 000 | session record |
| case studies / bug reports closed / open | 3 / 133 / 2 | `ls Docs/CASE_STUDIES Tasks/bug_report/*` |
| tests / source files | 456 test files, 4 958 tests / 749 files | gate log `logs/ci-local-20260916-145211.log`; `find` |

## Appendix B — what a fresh remote container needs before the gate runs

Recorded because every scheduled agent and every remote session starts here, and the briefing says
the environment is not persisted: Python 3.11 on the image (below the 3.12 floor), no virtualenv,
no engine, no Qt libraries, no `pwsh`. The sequence that got the static gate to `PASS` in this
container is now in `install-rule.md` §2b, each line as it was run. The full gate then ran on the
final tree of this branch; its log is cited in `BOT-134`.
