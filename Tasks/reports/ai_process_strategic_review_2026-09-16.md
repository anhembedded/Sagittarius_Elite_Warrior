# The AI process as a system — a strategic review

**Dates:** 2026-09-16 (review), 2026-09-17 (recommendations applied; arguments re-anchored to
published sources on the user's instruction) · **Task:** `BOT-134`.

**What was asked.** Strategy, a systems view and the philosophy of the repository's AI-run
process — not a defect list (*"tui ko yêu cầu bạn kiểm tra lỗi, tôi muốn tính chiến lược, góc nhìn
hệ thống, triết lý"*). Then: make the rules short and token-cheap and apply the recommendations
(*"sửa luôn những gì bạn đề xuất"*). Then: ground every argument in established human knowledge
rather than in this review's own reasoning (*"báo cáo lấy lập luận từ kiến thức nhân loại chứ
không phải logic bạn tự nghĩ ra"*).

**How to read the arguments.** Each principle, each case study and each recommendation names the
published idea it rests on — an author, a work and a year, listed in the References at the end.
Where a sentence is this review's own inference from the repository's data, it says *"measured
here"* and gives the number; nothing else is asserted on the review's own authority.

**How this was made.** Every process document was read whole; the git history was unshallowed
and measured; the Routines, the last sixty pull requests, the CI runs and the session records were
read through their APIs; a fresh container was bootstrapped to the point where the local gate
runs, so every claim about the environment was tried rather than assumed. Numbers are in
Appendix A with the command that produced each.

---

## 1. The system as it is

The process is a loop; most of what follows is about which arrows exist and which do not.

```text
                     ┌──────────────────────────────────────────────────────────┐
                     │  THE USER — decides, in chat, in Vietnamese               │
                     │  (every decision is written verbatim, dated, into a rule) │
                     └───────────────┬──────────────────────────────▲───────────┘
                                     │ decisions                    │ reports (report-rule)
                                     ▼                              │ questions (ONBOARDING §11)
   ┌──────────────── the constitution ────────────────┐             │
   │ CLAUDE.md (auto-loaded, navigates only)          │             │
   │  → ONBOARDING.md (the map)                       │             │
   │  → .agents/rules/*.md                            │             │
   │  → .claude/rules/*.md (pointers, load by path)   │             │
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
   │   ~4 900 tests, 80 % coverage, run-log scan)     │──▶│ PR opened and merged │
   │ 35 guards + ratchets that may only fall          │   │ by the same session, │
   │ a registry of guards, a guard for the registry   │   │ median 6 s later     │
   └───────────────┬──────────────────────────────────┘   └──────────┬───────────┘
                   │                                                 ▼
                   │                                      ┌──────────────────────┐
                   │                                      │ GitHub CI, after the │
                   │                                      │ merge (a second gate │
                   ▼                                      │ until 2026-09-17)    │
   ┌──────────────── the memory ──────────────────────┐   └──────────────────────┘
   │ bug reports → case studies → a new guard each    │   ┌──────────────────────┐
   │ → a trap in ONBOARDING §8 → a rule               │   │ 7 scheduled agents,  │
   │ boards: ROADMAP, epics README, per-epic README + │   │ every 2 days, output │
   │ TRACKING + Gantt, bug board — copied by hand     │   │ observed: none since │
   │ (17 of the last 100 commits only record)         │   │ 2026-08-27           │
   └──────────────────────────────────────────────────┘   └──────────────────────┘
```

The left column is strong and unusual: a repository that turns every incident into a machine
check and writes its reasoning into commit bodies good enough to be the primary record. The
right column is where the arrows are weak: review is the author reading itself, the merge is a
formality, and the one component built for independent eyes had produced nothing observable for
twenty days. The memory at the bottom is written five times by hand, in a repository whose own
onboarding says that hand-maintained copies of state *"drift, always"*.

---

## 2. The philosophy, stated once — and where each idea comes from

Every principle below is already in force here, argued in chat and quoted into a rule. None of
them is original to this repository; each is a named idea with a literature, and the fourth
column says which. The last column asks the question the repository asks of every feature —
*what constructs it?* — of the process itself.

| # | Principle as practised here | Its established source | Enforced today by |
| :-- | :--- | :--- | :--- |
| P1 | **Mechanism over memory** — *"wherever remembering is required, it will break"* (`BOT-133`). | Poka-yoke, mistake-proofing: Shingo (1986) — build the check into the process so the error cannot be made, rather than asking the worker to remember. | 35 guards, ratchets, the guard registry; the case-study rule (the check ships with the write-up) |
| P2 | **Verify, don't restate** — a fact that can change is written as the command that answers it. | Single source of truth / DRY: Hunt & Thomas (1999) — every piece of knowledge has one authoritative representation. | the reference checker (paths only); a stale *claim* has no checker |
| P3 | **A copy drifts** — rules point, never restate; hand-written summaries were deleted. | DRY (Hunt & Thomas 1999); ADRs (Nygard 2011) separate the decision record from the current rule. | the navigation and pointer guards; nothing for a rule restating another rule |
| P4 | **Green describes only what the gate checks.** Read the log file, never the console. | Dijkstra (1970): testing shows the presence of bugs, never their absence. | the run-log scan; review row B |
| P5 | **Apply before you invent** — survey named patterns and vetted projects first. | Design patterns as shared vocabulary (Gamma et al. 1994); "Choose Boring Technology" (McKinley 2015). | review row A5 |
| P6 | **Fix the mechanism, general over local** — cost is never the reason to prefer the local fix. | Deming (1986): most defects come from the system, not the individual act; root-cause analysis (Ohno's "five whys", Toyota). | `bug-fix-rule` §2; review row E10 |
| P7 | **Seam now, variant later.** | Open/Closed Principle (Meyer 1988); YAGNI (Beck 1999); seams (Feathers 2004). | review row C9; per-seam locking tests |
| P8 | **Ratchets only fall** — an allowlist may shrink, never grow. | The "strangler fig" migration (Fowler 2004): the old tree may only shrink; Lehman's law of increasing complexity (1980): complexity grows unless work is done to reduce it. | the ratchet tests |
| P9 | **Decide alone; ask with context.** | "Disagree and commit" (Grove 1983; an Amazon leadership principle); the narrative memo — context before the ask. | `report-rule` §7 |
| P10 | **A number has a unit and a target**; answer first. | The Pyramid Principle (Minto 1987); the four key metrics as measured, not narrated, outcomes (Forsgren, Humble & Kim 2018). | review row K6; the commit-body convention |

Four of the ten have a machine behind them; six rest on the agent having read and remembered the
rule — the condition Shingo's poka-yoke exists to remove. That is the central tension: the
process applies mistake-proofing to the application with rigour and to itself only partly.

---

## 3. Dynamics — seven process case studies

The form follows the blameless postmortem (Allspaw 2012; Beyer et al. 2016, "Postmortem
Culture"): what happened, which safeguard was silent and why, what is still open. They are
numbered PCS to keep them out of the CS sequence, whose guard requires a test per entry.

### PCS-1 The super-session monoculture

One interactive session, opened 2026-09-08, authored 164 of the last 216 commits on
`master-warrior` and every pull request from #193 to #220; fourteen of the twenty #201–#220 were
merged within thirty seconds of being opened, by the session that wrote them (measured here). The
`pr-review` skill is thorough and the commit bodies say who ran it: *"The review's own finding on
PR 2.1c-2."* The three case studies (`CS-001`–`003`) were all found after merge.

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| `pr-review` skill | written for a reviewer; run by the author, in the author's context | closed 2026-09-17 (S5) |
| the PR itself | nothing required a second session before merge | closed 2026-09-17 (S5) |

**In the literature.** Fagan's inspections (1976) found a large share of defects before test
precisely because the inspector was not the author; Raymond's "Linus's law" (1999) — *given enough
eyeballs, all bugs are shallow* — is the same claim for open source; IEEE 1012's independent
verification and validation requires that the verifier be organisationally separate from the
developer; Google's code-review practice requires an approver other than the author. The self-
review's own E12 probe found unpinned wiring in four of five pull requests (measured here) — the
process needed a second reading and was getting it from the first reader.

### PCS-2 Boards copied by hand, five times per pull request

A pull request of `EPIC-025` was recorded in `TRACKING.md`, the epic README (header, table,
Gantt), `Tasks/epics/README.md` and `ROADMAP.md`; seventeen of the last hundred commits existed
only to record other commits; eight task files had no row anywhere and three sub-tasks were
unnamed in their epic README (measured here).

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| `test_task_board_is_consistent.py` | checked dangling links, never the reverse | closed 2026-09-16 |
| `ONBOARDING` §12.2 | stated the principle and deleted `Handover.md` for it; the boards multiplied anyway | count table derived 2026-09-17 (S4) |

**In the literature.** DRY (Hunt & Thomas 1999): duplicated knowledge is knowledge that will
disagree with itself; derive what can be derived. Humble & Farley (2010) apply the same rule to
builds — build once, derive everything downstream.

### PCS-3 Seven scheduled agents that succeed at nothing

Seven Routines fired every two days from 2026-08-27; every run reported `SUCCEEDED`; zero pull
requests and zero journal entries came from them, and their brief called an empty run correct
(measured here). The one audit with a defined output (`test-health`) was never scheduled.

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| the Routine's status | measures that the wake was delivered, not what the run did | retired 2026-09-17 (S6) |
| the brief's "empty run is correct" | made *found nothing*, *could not build* and *lost it* one signal | replaced by a dated file per run |

**In the literature.** The SRE monitoring literature (Beyer et al. 2016) alerts on the
*absence* of expected work — a heartbeat, a "dead man's switch" — because a job that reports
success regardless of outcome is indistinguishable from one that never ran.

### PCS-4 The immune system that closes the last hole

`CS-001` produced a guard for engine-port calls, `CS-002` for unconstructed subscribers,
`CS-003` for unbound resolved types — and `CS-003` says of `CS-002`'s guard that it was *written
for this disease and scoped to bus subscribers*. Thirty-five guard files, a registry, a guard for
the registry; `ci-rule` §5.5 had to add a procedure for guards that fail correct code after a
design reversal (measured here).

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| the case-study rule | adds a check per incident; nothing removes or budgets one | retirement rule 2026-09-17 (S9) |

**In the literature.** Reason's Swiss-cheese model (1990): each layer of defence has holes and
accidents pass through aligned holes — so adding one layer per accident, each shaped like the last
hole, is expected to leave the next alignment open. Lehman (1980): a system's complexity grows
unless work is spent reducing it; a test suite is a system. Beck (1999): test what could break,
which implies deleting tests for what no longer can.

### PCS-5 Rules that quote themselves

Seven contradictions inside the constitution — a cadence stated two ways, a number the guard
did not hold, a quotation the cited file never contained, a claim of current state a command
disproved, an install command the CI file itself recorded as failing (measured here).

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| the reference checker | verifies paths, not claims or quotations | yes |
| the navigation guard | verifies listing, not consistency | yes |
| the form of a rule file | norm and history in one file, so a correction is one more paragraph nobody re-reads | closed 2026-09-17 (S1) |

**In the literature.** Diátaxis (Procida): reference material and explanation serve different
readers and rot when mixed; ADRs (Nygard 2011): the *decision and its context* live in an
immutable dated record, the *current rule* elsewhere. A rule file that is also its changelog fails
both.

### PCS-6 Two definitions of green

The GitHub workflow re-listed the local gate's steps by hand and drifted twice; then, from
2026-09-16 14:49 UTC, `master-warrior` was red for twenty consecutive runs (`BUG-129`, measured by
the `EPIC-025` session from the runs themselves) while every local gate was green — the local
checker asked the developer's disk, which still held directories git no longer tracked, and three
merges landed on top of the red runs.

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| `ci-rule` §7's comparison table | a hand-written copy of two files | removed 2026-09-17 (S3) |
| the merge step | nothing looked at CI after merging | S5 puts a second reader before the merge |

**In the literature.** Fowler (2006), "Continuous Integration": *fix broken builds immediately*
and *everyone can see what's happening*; Humble & Farley (2010): one pipeline, one definition of
done; the twelve-factor "dev/prod parity" rule. Merging three times onto a red build is what
Vaughan (1996) called the normalization of deviance in the Challenger launch decision: a signal
that is red often enough stops being read as red.

### PCS-7 Nobody owns the root

Three scratch files sat at the repository root for a month, through roughly 370 commits and
twenty reviewed pull requests, one carrying a trailer the rules recorded as purged; every scan is
scoped to a named tree and the root is in none (measured here).

| Net | Why silent | Still open? |
| :--- | :--- | :--- |
| `commit-rule` §4 | prose | an eye check, by design |
| `pr-review` L4/L6 | reads what a diff adds; the files predated every review | the files are gone; trap 14 |

**In the literature.** Diffusion of responsibility (Darley & Latané 1968): a duty that belongs
to everyone is discharged by no one; Google's `OWNERS` files exist to give every path a named
owner.

---

## 4. Strategy — where to take the process, and the practice each item applies

Ranked by leverage. Each names the established practice it applies, the cost, and what "yes"
commits the user to. **All ten were applied on 2026-09-17** (§5).

| # | Recommendation | Practice applied |
| :-- | :--- | :--- |
| S1 | Split each rule into a short **norm** (current clauses, each tagged with its enforcer) and let **history** live in ADRs, bug reports, case studies and `git log`. | Diátaxis (Procida): reference separate from explanation; ADRs (Nygard 2011). |
| S2 | Load rules by **path** — a pointer per rule with a file scope — instead of by memory. | Progressive disclosure (Nielsen 2006 lists it as a usability heuristic): show what is relevant when it is relevant; cognitive-load theory (Sweller 1988). |
| S3 | **One gate**: GitHub Actions runs `ci-local.ps1 -Full` itself. | Humble & Farley (2010): one deployment pipeline; Fowler (2006): the build is the shared truth. |
| S4 | **Derive the boards**: compute the count table, guard the board against the computation. | DRY (Hunt & Thomas 1999); "derive, don't duplicate". |
| S5 | **Independent review before a code merge**: a different session runs `pr-review`; the author never merges its own code. | Fagan (1976); Google code review; IEEE 1012 IV&V independence. |
| S6 | **Retire the personas; keep two audits** whose every run leaves a dated file. | SRE heartbeat monitoring (Beyer et al. 2016): alert on absence. |
| S7 | **Measure the process** — rule lines, guard count, allowlist size, escapes, share of bookkeeping commits. | Forsgren, Humble & Kim (2018): outcomes measured, not narrated; Goodhart's law (Strathern 1997) as the warning — measures inform, they are not targets. |
| S8 | **Write down the autonomy policy actually practised**: trunk-based with a gate; docs free; code reviewed before merge. | "Ship / Show / Ask" (Wilsenach 2021): documentation ships, code asks. |
| S9 | **A retirement rule for guards** — `Retire when:` in every guard's docstring. | Lehman (1980); Beck (1999): tests are a cost as well as an asset. |
| S10 | **One definition of "documentation-only"**, in `ONBOARDING.md` §7, pointed at by the other two files. | DRY (Hunt & Thomas 1999). |

---

## 5. Applied — what changed, measured

Everything below is on `master-warrior` (pull request #221, merged 2026-09-17 05:14 UTC after
the new workflow's first green run) except the `ruff` pin, which follows in its own pull request.

| Recommendation | What it became |
| :--- | :--- |
| S1 | twelve rules rewritten as tagged norms; `qml-rule.md` and `code-rule.md` deleted; section numbers kept so every `§` citation resolves |
| S2 | six pointers under `.claude/rules/`; `architecture` loads for every `src/` file; the domain and UI pointers cover the `modules/` and `support/` trees |
| S3 | `.github/workflows/ci.yml` runs `scripts/ci-local.ps1 -Full`, uploads `logs/`, accepts `workflow_dispatch`; first runner run green in five minutes |
| S4 | `scripts/render_task_counts.py` is the one computation; the board guard holds `ROADMAP.md` to it and fails on a task file with no row |
| S5 | `ONBOARDING.md` §7: a code change merges only after a different session has run `pr-review`; the author never merges its own code |
| S6 | seven prompts, the Bolt journal and seven Routines retired; `test-health` and `process-drift` scheduled every three days, each run committing a dated file |
| S7 | `scripts/measure_process.py` prints the baseline; the drift audit records it each run |
| S8 | §7 is the one authority table: commit and branch push free after the per-commit checks; docs-only merges free; code merges gated |
| S9 | `testing-rule.md` §2 and principle 12: a new guard states `Retire when:` |
| S10 | §7 defines the documentation-only set; `CLAUDE.md` and `ci-rule.md` point there |
| `ruff` | pinned to the version the green gate ran (`requirements.txt`, and `required-version` in `pyproject.toml` so a mismatched local `ruff` refuses to run rather than report a different answer) |

| Measure | Before | After | Target |
| :--- | :-: | :-: | :-: |
| rule lines, all rule files | 1 976 (14 files) | 453 (12 files) | — |
| lines an agent reads before a `src/` change | 1 567 | 440 | under ~700 |
| all process text (`.agents/`, `CLAUDE.md`, `.claude/`) | 4 263 | 1 409 | — |
| rules loading by path | 6 of 14 | 6 of 12, `architecture` included | every rule with a file scope |
| scheduled Routines / with a durable output | 7 / 0 | 2 / 2 | — |
| task files with no board row | 8 | 0 | 0, guarded |
| definitions of "green" | 2 | 1 | 1 |
| consecutive red runs on `master-warrior` before anyone acted | 20 | — | 0: S5 puts a reader before the merge |

**What the user must still decide:** nothing from this review. The running `EPIC-025` session
reads `ONBOARDING.md` §7 on its next run; the first code pull request it opens after that is the
test of S5.

---

## Appendix A — the baseline, measured 2026-09-16

| Measure | Value | Command |
| :--- | :-: | :--- |
| rule text, all rule files | 1 976 lines | `cat .agents/rules/*.md \| wc -l` |
| text an agent reads before a `src/` change | 1 567 lines | `cat CLAUDE.md .agents/ONBOARDING.md .agents/rules/{code-quality,architecture,ci,commit,testing,logging}-rule.md \| wc -l` |
| all process text | 4 263 lines | `cat CLAUDE.md .agents/*.md .agents/rules/*.md .agents/Skills/*.md .claude/rules/*.md .claude/skills/*/SKILL.md \| wc -l` |
| guard files | 29 + 6 | `ls tests/unit/architecture/test_*.py tests/unit/test_*.py \| wc -l` |
| commits since 2026-09-08 / by the one session | 216 / 164 | `git log --since=2026-09-08 --format=%b \| grep -c session_013VgDR1` |
| commits in the last 100 that only record others | 17 | `git log -100 --format=%s \| grep -c 'record\|boards'` |
| pull requests #201–#220 merged within 30 s of opening | 14 of 20 | GitHub API, `created_at` vs `merged_at` |
| scheduled Routines / pull requests from them / journal entries | 7 / 0 / 0 | `list_triggers`; `list_pull_requests`; `ls .agents/Skills/*.md` |
| consecutive red CI runs on `master-warrior` (runs 371–390) | 20 | GitHub Actions API (`BUG-129`) |
| tests / source files | 456 files, 4 958 tests / 749 | gate log; `find` |

`python3 scripts/measure_process.py` reproduces the tree-derived rows on any checkout.

## Appendix B — a fresh remote container

Python 3.11 on the image, no virtualenv, no engine, no Qt libraries, no `pwsh`. The sequence that
got the gate to `PASS` is in `install-rule.md` §2b, each line as it was run.

## References

- Allspaw, J. (2012). *Blameless PostMortems and a Just Culture.* Etsy engineering blog.
- Beck, K. (1999). *Extreme Programming Explained.* Addison-Wesley. (YAGNI; "test what could break".)
- Beyer, B., Jones, C., Petoff, J. & Murphy, N. R., eds. (2016). *Site Reliability Engineering.* O'Reilly. (Monitoring; postmortem culture.)
- Darley, J. M. & Latané, B. (1968). "Bystander intervention in emergencies: diffusion of responsibility." *Journal of Personality and Social Psychology* 8(4).
- Deming, W. E. (1986). *Out of the Crisis.* MIT Press. (Common-cause variation; the system, not the worker.)
- Dijkstra, E. W. (1970). *Notes on Structured Programming* (EWD249). "Program testing can be used to show the presence of bugs, but never to show their absence."
- Fagan, M. E. (1976). "Design and code inspections to reduce errors in program development." *IBM Systems Journal* 15(3).
- Feathers, M. (2004). *Working Effectively with Legacy Code.* Prentice Hall. (Seams.)
- Forsgren, N., Humble, J. & Kim, G. (2018). *Accelerate.* IT Revolution. (The four key metrics.)
- Fowler, M. (2004). "StranglerFigApplication"; (2006) "Continuous Integration." martinfowler.com.
- Gamma, E., Helm, R., Johnson, R. & Vlissides, J. (1994). *Design Patterns.* Addison-Wesley.
- Grove, A. S. (1983). *High Output Management.* Random House. ("Disagree and commit.")
- Humble, J. & Farley, D. (2010). *Continuous Delivery.* Addison-Wesley.
- Hunt, A. & Thomas, D. (1999). *The Pragmatic Programmer.* Addison-Wesley. (DRY.)
- IEEE Std 1012, *Standard for System, Software, and Hardware Verification and Validation.* (Independence of the verifier.)
- Lehman, M. M. (1980). "Programs, life cycles, and laws of software evolution." *Proceedings of the IEEE* 68(9).
- McKinley, D. (2015). "Choose Boring Technology." mcfunley.com.
- Meyer, B. (1988). *Object-Oriented Software Construction.* Prentice Hall. (Open/Closed Principle.)
- Minto, B. (1987). *The Pyramid Principle.* Pitman.
- Nielsen, J. (2006). "Progressive Disclosure." Nielsen Norman Group.
- Nygard, M. (2011). "Documenting Architecture Decisions." cognitect.com.
- Procida, D. *Diátaxis: a systematic approach to technical documentation authoring.* diataxis.fr.
- Raymond, E. S. (1999). *The Cathedral and the Bazaar.* O'Reilly. (Linus's law.)
- Reason, J. (1990). *Human Error.* Cambridge University Press. (The Swiss-cheese model.)
- Shingo, S. (1986). *Zero Quality Control: Source Inspection and the Poka-yoke System.* Productivity Press.
- Strathern, M. (1997). "'Improving ratings': audit in the British University system." *European Review* 5(3). (The usual statement of Goodhart's law.)
- Sweller, J. (1988). "Cognitive load during problem solving." *Cognitive Science* 12(2).
- Vaughan, D. (1996). *The Challenger Launch Decision.* University of Chicago Press. (Normalization of deviance.)
- Wilsenach, R. (2021). "Ship / Show / Ask." martinfowler.com.
- Google, *Engineering Practices — Code Review Developer Guide.* google.github.io/eng-practices.
